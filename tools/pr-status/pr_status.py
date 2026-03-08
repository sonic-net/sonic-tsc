#!/usr/bin/env python3
"""PR Status Report Tool for sonic-net repos.

Accurately reports PR status by cross-referencing:
- Check Runs API (GitHub Actions, Copilot review)
- Commit Status API (EasyCLA, Azure Pipelines)
- Required status checks (branch protection / rulesets)
- Review status + CODEOWNERS analysis
"""

import argparse
import json
import subprocess
import sys
import re
from pathlib import PurePosixPath
from fnmatch import fnmatch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

def get_gh_token():
    """Get auth token from gh CLI."""
    r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    if r.returncode != 0:
        print("Error: gh auth token failed. Run 'gh auth login' first.", file=sys.stderr)
        sys.exit(1)
    return r.stdout.strip()


def api_get(url, token, params=None, max_pages=None):
    """GET from GitHub API with pagination support."""
    if params:
        url = f"{url}?{urlencode(params)}"
    results = []
    page = 0
    while url:
        page += 1
        if max_pages and page > max_pages:
            break
        req = Request(url, headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        try:
            resp = urlopen(req, timeout=30)
        except HTTPError as e:
            if e.code == 404:
                return None
            raise
        data = json.loads(resp.read())
        # Check rate limit
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining and int(remaining) < 10:
            print(f"⚠ GitHub rate limit low: {remaining} remaining", file=sys.stderr)
        # Handle pagination
        link = resp.headers.get("Link", "")
        next_url = None
        for part in link.split(","):
            if 'rel="next"' in part:
                next_url = part.split("<")[1].split(">")[0]
        if isinstance(data, list):
            results.extend(data)
            url = next_url
        else:
            return data
    return results


def graphql(query, token):
    """Execute a GraphQL query."""
    body = json.dumps({"query": query}).encode()
    req = Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
    })
    resp = urlopen(req, timeout=30)
    return json.loads(resp.read())


# ---------------------------------------------------------------------------
# CODEOWNERS parsing
# ---------------------------------------------------------------------------

def fetch_codeowners(owner, repo, token):
    """Fetch and parse CODEOWNERS file."""
    for path in [".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"]:
        data = api_get(f"https://api.github.com/repos/{owner}/{repo}/contents/{path}", token)
        if data and "download_url" in data:
            req = Request(data["download_url"])
            content = urlopen(req, timeout=15).read().decode()
            return parse_codeowners(content)
    return []


def parse_codeowners(content):
    """Parse CODEOWNERS into list of (pattern, [owners])."""
    rules = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            pattern = parts[0]
            owners = [o for o in parts[1:] if o.startswith("@")]
            rules.append((pattern, owners))
    return rules


def match_codeowners(changed_files, rules):
    """Find required reviewers for changed files. Last matching rule wins per file."""
    required = set()
    for fpath in changed_files:
        matched_owners = None
        for pattern, owners in rules:
            if _codeowners_match(fpath, pattern):
                matched_owners = owners
        if matched_owners:
            required.update(matched_owners)
    return required


def _codeowners_match(filepath, pattern):
    """Match a filepath against a CODEOWNERS pattern."""
    # Normalize
    filepath = filepath.lstrip("/")
    pattern_clean = pattern.lstrip("/")

    # Directory pattern (ends with /)
    if pattern_clean.endswith("/"):
        return filepath.startswith(pattern_clean) or filepath.startswith(pattern_clean.rstrip("/"))

    # Wildcard at root: *
    if pattern_clean == "*":
        return True

    # Contains path separator → match from root
    if "/" in pattern_clean.rstrip("/"):
        return fnmatch(filepath, pattern_clean) or filepath.startswith(pattern_clean)

    # No separator → match basename anywhere
    return fnmatch(PurePosixPath(filepath).name, pattern_clean)


# ---------------------------------------------------------------------------
# Required status checks
# ---------------------------------------------------------------------------

def get_required_checks(owner, repo, branch, token):
    """Try to discover required status checks."""
    # Method 1: Branch protection
    data = api_get(
        f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}/protection/required_status_checks",
        token)
    if data and "contexts" in data:
        return set(data["contexts"])
    if data and "checks" in data:
        return {c["context"] for c in data["checks"]}

    # Method 2: Rulesets
    rulesets = api_get(f"https://api.github.com/repos/{owner}/{repo}/rulesets", token)
    if rulesets:
        required = set()
        for rs in rulesets:
            if rs.get("enforcement") != "active":
                continue
            detail = api_get(f"https://api.github.com/repos/{owner}/{repo}/rulesets/{rs['id']}", token)
            if detail and "rules" in detail:
                for rule in detail["rules"]:
                    if rule["type"] == "required_status_checks":
                        for check in rule.get("parameters", {}).get("required_status_checks", []):
                            required.add(check.get("context", ""))
                required.discard("")
        if required:
            return required

    return None  # Unknown — can't determine


_typical_cache = {}

def get_typical_checks(owner, repo, token):
    """Heuristic: look at recently merged PRs to find what checks typically run."""
    cache_key = f"{owner}/{repo}"
    if cache_key in _typical_cache:
        return _typical_cache[cache_key]

    # Use search API to find recently merged PRs (faster than listing all closed)
    query = f"is:pr is:merged repo:{owner}/{repo} sort:updated-desc"
    search = api_get("https://api.github.com/search/issues", token,
                     {"q": query, "per_page": "5"}, max_pages=1)
    if not search or not search.get("items"):
        _typical_cache[cache_key] = set()
        return set()

    check_counts = {}
    count = 0
    for item in search["items"][:3]:  # Only check 3 recent merged PRs
        pr_data = api_get(f"https://api.github.com/repos/{owner}/{repo}/pulls/{item['number']}", token)
        if not pr_data:
            continue
        sha = pr_data["head"]["sha"]
        count += 1
        # Check runs
        cr = api_get(f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}/check-runs", token)
        if cr and "check_runs" in cr:
            for c in cr["check_runs"]:
                check_counts[c["name"]] = check_counts.get(c["name"], 0) + 1
        # Statuses
        st = api_get(f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}/status", token)
        if st and "statuses" in st:
            for s in st["statuses"]:
                check_counts[s["context"]] = check_counts.get(s["context"], 0) + 1

    threshold = max(1, count * 0.6)
    result = {name for name, c in check_counts.items() if c >= threshold}

    # Exclude checks that only run post-merge (not PR gates)
    POST_MERGE_PATTERNS = {"pre_cherry_pick", "cherry_pick", "cherry-pick", "backport"}
    # Exclude pipeline infrastructure jobs (not gates)
    INFRA_PATTERNS = {"cleanup", "upload results", "agent", "prepare"}
    result = {name for name in result
              if not any(p in name.lower() for p in POST_MERGE_PATTERNS)
              and not any(p in name.lower() for p in INFRA_PATTERNS)}

    _typical_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# PR analysis
# ---------------------------------------------------------------------------

def analyze_pr(pr, owner, repo, token, codeowners_rules, required_checks, typical_checks):
    """Analyze a single PR's status."""
    number = pr["number"]
    title = pr["title"]
    sha = pr["head"]["sha"]
    base_branch = pr["base"]["ref"]
    url = pr["html_url"]

    result = {
        "number": number,
        "title": title,
        "url": url,
        "sha": sha[:7],
        "base": base_branch,
        "created_at": pr.get("created_at", ""),
        "updated_at": pr.get("updated_at", ""),
        "user": pr["user"]["login"],
        "additions": pr.get("additions", 0),
        "deletions": pr.get("deletions", 0),
        "changed_files": pr.get("changed_files", 0),
        "labels": [l["name"] for l in pr.get("labels", [])],
        "draft": pr.get("draft", False),
        "checks": {},       # name → {source, status, conclusion, url}
        "required_checks": None,
        "missing_checks": [],
        "reviews": [],
        "codeowners_needed": [],
        "merge_state": None,
        "mergeable": None,
        "blockers": [],      # human-readable list of what's blocking merge
        "category": None,    # ready, blocked_ci, blocked_review, blocked_missing, failing
    }

    # --- Checks ---
    # 1. Check Runs
    cr_data = api_get(f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}/check-runs", token)
    if cr_data and "check_runs" in cr_data:
        for c in cr_data["check_runs"]:
            result["checks"][c["name"]] = {
                "source": "check_run",
                "status": c["status"],
                "conclusion": c["conclusion"],
                "url": c.get("html_url", ""),
            }

    # 2. Commit Statuses
    st_data = api_get(f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}/status", token)
    if st_data and "statuses" in st_data:
        # Deduplicate: keep latest per context
        seen = {}
        for s in st_data["statuses"]:
            ctx = s["context"]
            if ctx not in seen:
                seen[ctx] = s
        for ctx, s in seen.items():
            result["checks"][ctx] = {
                "source": "status",
                "status": "completed" if s["state"] in ("success", "failure", "error") else s["state"],
                "conclusion": s["state"],
                "url": s.get("target_url", ""),
            }

    # 3. Required checks analysis
    if required_checks is not None:
        result["required_checks"] = list(required_checks)
        reported = set(result["checks"].keys())
        for rc in required_checks:
            if rc not in reported:
                # Check partial matches (Azure.sonic-buildimage might appear as different name)
                if not any(rc.lower() in r.lower() or r.lower() in rc.lower() for r in reported):
                    result["missing_checks"].append(rc)
    elif typical_checks:
        # Heuristic: compare against typical
        reported = set(result["checks"].keys())
        missing_typical = []
        for tc in typical_checks:
            if tc not in reported:
                if not any(tc.lower() in r.lower() or r.lower() in tc.lower() for r in reported):
                    missing_typical.append(tc)
        if missing_typical:
            result["missing_checks"] = missing_typical
            result["required_checks"] = [f"(typical) {t}" for t in typical_checks]

    # --- Reviews ---
    reviews_data = api_get(f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/reviews", token)
    if reviews_data:
        # Latest review per user
        latest = {}
        for r in reviews_data:
            user = r["user"]["login"]
            latest[user] = {"user": user, "state": r["state"]}
        result["reviews"] = list(latest.values())

    # --- CODEOWNERS ---
    if codeowners_rules:
        files_data = api_get(f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/files", token)
        if files_data:
            changed_files = [f["filename"] for f in files_data]
            needed = match_codeowners(changed_files, codeowners_rules)
            approved_users = {r["user"].lstrip("@") for r in result["reviews"]
                            if r["state"] == "APPROVED"}
            # Resolve team mentions to individual approvers (can't resolve team membership via API easily)
            still_needed = []
            for owner_str in needed:
                clean = owner_str.lstrip("@")
                # If it's a team (org/team), we can't easily resolve members
                if "/" in clean:
                    # Check if any team member approved (we can't know, so flag it)
                    still_needed.append(owner_str)
                elif clean not in approved_users:
                    still_needed.append(owner_str)
            result["codeowners_needed"] = still_needed

    # --- Merge state (GraphQL) ---
    gql = graphql(f'''{{
      repository(owner: "{owner}", name: "{repo}") {{
        pullRequest(number: {number}) {{
          mergeStateStatus
          mergeable
        }}
      }}
    }}''', token)
    pr_gql = gql.get("data", {}).get("repository", {}).get("pullRequest", {})
    result["merge_state"] = pr_gql.get("mergeStateStatus")
    result["mergeable"] = pr_gql.get("mergeable")

    # --- Categorize ---
    all_checks_pass = all(
        c["conclusion"] in ("success", "neutral", "skipped")
        for c in result["checks"].values()
        if c["status"] == "completed"
    )
    any_pending = any(c["status"] in ("queued", "in_progress", "pending")
                      for c in result["checks"].values())
    any_failed = any(c["conclusion"] in ("failure", "error", "cancelled", "timed_out")
                     for c in result["checks"].values())
    has_approval = any(r["state"] == "APPROVED" for r in result["reviews"])
    has_changes_requested = any(r["state"] == "CHANGES_REQUESTED" for r in result["reviews"])

    # --- Compute blockers ---
    blockers = []

    if result["draft"]:
        blockers.append("PR is still in draft")

    if result["missing_checks"]:
        blockers.append(f"Required CI never triggered: {', '.join(result['missing_checks'])}")

    failed_checks = [name for name, c in result["checks"].items()
                     if c["conclusion"] in ("failure", "error", "cancelled", "timed_out")]
    if failed_checks:
        blockers.append(f"CI failures: {', '.join(failed_checks)}")

    pending_checks = [name for name, c in result["checks"].items()
                      if c["status"] in ("queued", "in_progress", "pending")]
    if pending_checks:
        blockers.append(f"CI pending: {', '.join(pending_checks)}")

    if has_changes_requested:
        requesters = [r["user"] for r in result["reviews"] if r["state"] == "CHANGES_REQUESTED"]
        blockers.append(f"Changes requested by: {', '.join(requesters)}")

    if not has_approval:
        blockers.append("No approving review yet")

    if result["codeowners_needed"]:
        blockers.append(f"CODEOWNERS review needed: {', '.join(result['codeowners_needed'])}")

    if result["mergeable"] == "CONFLICTING":
        blockers.append("Merge conflict — needs rebase")

    result["blockers"] = blockers

    if result["missing_checks"]:
        result["category"] = "blocked_missing"
    elif any_failed:
        result["category"] = "failing"
    elif any_pending:
        result["category"] = "pending"
    elif has_changes_requested:
        result["category"] = "changes_requested"
    elif not has_approval:
        result["category"] = "needs_review"
    elif result["merge_state"] == "BLOCKED":
        # Approved + all green but still blocked → likely missing required check or CODEOWNERS
        if result["codeowners_needed"]:
            result["category"] = "blocked_codeowners"
        else:
            result["category"] = "blocked_unknown"
    elif result["merge_state"] == "BEHIND":
        result["category"] = "behind"
    else:
        result["category"] = "ready"

    return result


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

CATEGORY_ORDER = [
    "ready", "behind", "blocked_missing", "blocked_codeowners", "blocked_unknown",
    "failing", "pending", "changes_requested", "needs_review",
]

CATEGORY_LABELS = {
    "ready": "✅ READY TO MERGE",
    "behind": "🔄 BEHIND BASE BRANCH",
    "blocked_missing": "🚫 BLOCKED — CI NEVER RAN",
    "blocked_codeowners": "👤 BLOCKED — CODEOWNERS REVIEW NEEDED",
    "blocked_unknown": "🔒 BLOCKED — UNKNOWN REASON",
    "failing": "❌ CI FAILING",
    "pending": "⏳ CI PENDING",
    "changes_requested": "🔧 CHANGES REQUESTED",
    "needs_review": "👀 WAITING ON REVIEW",
}


def format_whatsapp(results):
    """Format for WhatsApp — detailed per-PR breakdown."""
    by_category = {}
    for r in results:
        by_category.setdefault(r["category"], []).append(r)

    lines = [f"🎵 *PR Status Report* ({len(results)} open PRs)", ""]

    for cat in CATEGORY_ORDER:
        prs = by_category.get(cat, [])
        if not prs:
            continue
        lines.append(f"━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"*{CATEGORY_LABELS[cat]}* ({len(prs)})")
        lines.append("")

        for r in sorted(prs, key=lambda x: x["number"]):
            # Header: number + title
            repo_short = r.get("repo", "").split("/")[-1]
            lines.append(f"*#{r['number']}* ({repo_short})")
            lines.append(f"_{r['title']}_")
            lines.append(r["url"])

            # Stats line
            lines.append(f"  +{r.get('additions', 0)}/−{r.get('deletions', 0)} across {r.get('changed_files', 0)} files | sha: {r['sha']}")
            if r.get("labels"):
                lines.append(f"  Labels: {', '.join(r['labels'])}")
            if r.get("draft"):
                lines.append(f"  ⚠️ DRAFT")

            # Reviews detail
            approvals = [rv["user"] for rv in r["reviews"] if rv["state"] == "APPROVED"]
            comments = [rv["user"] for rv in r["reviews"] if rv["state"] == "COMMENTED"]
            changes_req = [rv["user"] for rv in r["reviews"] if rv["state"] == "CHANGES_REQUESTED"]
            dismissed = [rv["user"] for rv in r["reviews"] if rv["state"] == "DISMISSED"]

            review_lines = []
            if approvals:
                review_lines.append(f"    ✅ Approved: {', '.join(approvals)}")
            if changes_req:
                review_lines.append(f"    🔧 Changes requested: {', '.join(changes_req)}")
            if comments:
                review_lines.append(f"    💬 Commented: {', '.join(comments)}")
            if dismissed:
                review_lines.append(f"    ⚪ Dismissed: {', '.join(dismissed)}")
            if r["codeowners_needed"]:
                review_lines.append(f"    👤 CODEOWNERS needed: {', '.join(r['codeowners_needed'])}")
            if not review_lines:
                review_lines.append("    ⚪ No reviews yet")
            lines.append("  *Reviews:*")
            lines.extend(review_lines)

            # CI detail
            passed = [(n, c) for n, c in r["checks"].items()
                      if c["conclusion"] in ("success", "neutral", "skipped")]
            failed = [(n, c) for n, c in r["checks"].items()
                      if c["conclusion"] in ("failure", "error", "cancelled", "timed_out")]
            pending = [(n, c) for n, c in r["checks"].items()
                       if c["status"] in ("queued", "in_progress", "pending")]
            missing = r["missing_checks"]

            lines.append("  *CI Status:*")
            if passed:
                lines.append(f"    ✅ Passed ({len(passed)}): {', '.join(n for n, _ in passed)}")
            if failed:
                for name, c in failed:
                    lines.append(f"    ❌ {name}")
            if pending:
                for name, c in pending:
                    lines.append(f"    ⏳ {name}")
            if missing:
                for m in missing:
                    lines.append(f"    🚫 {m} — never triggered")
            if not passed and not failed and not pending and not missing:
                lines.append("    ⚪ No CI checks found")

            # Merge state
            merge_icon = {"CLEAN": "✅", "BLOCKED": "🔒", "BEHIND": "🔄",
                         "DIRTY": "⚠️", "UNKNOWN": "❓", "UNSTABLE": "⚠️"
                         }.get(r["merge_state"] or "", "❓")
            mergeable_str = ""
            if r["mergeable"] == "CONFLICTING":
                mergeable_str = " (has conflicts)"
            elif r["mergeable"] == "MERGEABLE":
                mergeable_str = " (no conflicts)"
            lines.append(f"  *Merge:* {merge_icon} {r['merge_state'] or 'unknown'}{mergeable_str}")

            # Blockers summary
            if r["blockers"]:
                lines.append("  *Blockers:*")
                for b in r["blockers"]:
                    lines.append(f"    🔸 {b}")
            elif r["category"] == "ready":
                lines.append("  *No blockers — ready to merge!* 🚀")

            lines.append("")  # blank line between PRs

    # Summary footer
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("*Summary:*")
    for cat in CATEGORY_ORDER:
        count = len(by_category.get(cat, []))
        if count:
            lines.append(f"  {CATEGORY_LABELS[cat]}: {count}")

    return "\n".join(lines).strip()


def format_terminal(results):
    """Format for terminal with colors."""
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"

    CAT_COLORS = {
        "ready": GREEN,
        "behind": BLUE,
        "blocked_missing": MAGENTA,
        "blocked_codeowners": YELLOW,
        "blocked_unknown": RED,
        "failing": RED,
        "pending": YELLOW,
        "changes_requested": YELLOW,
        "needs_review": BLUE,
    }

    by_category = {}
    for r in results:
        by_category.setdefault(r["category"], []).append(r)

    lines = [f"{BOLD}PR Status Report ({len(results)} open PRs){RESET}", ""]

    for cat in CATEGORY_ORDER:
        prs = by_category.get(cat, [])
        if not prs:
            continue
        color = CAT_COLORS.get(cat, "")
        lines.append(f"{color}{BOLD}{CATEGORY_LABELS[cat]}{RESET}")
        for r in sorted(prs, key=lambda x: x["number"]):
            lines.append(f"  #{r['number']} {r['title']}")
            lines.append(f"    {r['url']}")

            # Compact review + CI
            approvals = [rv["user"] for rv in r["reviews"] if rv["state"] == "APPROVED"]
            failed = [n for n, c in r["checks"].items()
                      if c["conclusion"] in ("failure", "error", "cancelled", "timed_out")]
            missing = r["missing_checks"]
            passed = sum(1 for c in r["checks"].values()
                        if c["conclusion"] in ("success", "neutral", "skipped"))
            total = len(r["checks"])

            parts = []
            if approvals:
                parts.append(f"{GREEN}approved: {', '.join(approvals)}{RESET}")
            if r["codeowners_needed"]:
                parts.append(f"{YELLOW}needs: {', '.join(r['codeowners_needed'])}{RESET}")
            if missing:
                parts.append(f"{MAGENTA}never ran: {', '.join(missing)}{RESET}")
            if failed:
                parts.append(f"{RED}failed: {', '.join(failed)}{RESET}")
            if total > 0 and not missing and not failed:
                parts.append(f"{GREEN}CI: {passed}/{total}{RESET}")
            parts.append(f"merge: {r['merge_state'] or '?'}")
            lines.append(f"    {' | '.join(parts)}")
            lines.append("")
        lines.append("")

    return "\n".join(lines).strip()


def format_markdown(results):
    """Format as clean markdown with a single flat table + separate CI detail file."""
    import datetime as dt

    timestamp = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    # --- Main report ---
    lines = [
        f"# PR Status Report",
        "",
        f"> **Author:** rustiqly | **Generated:** {timestamp} | **Open PRs:** {len(results)}",
        "",
        "| PR | Title | Status | Reviews | CI | Best Way to Unblock |",
        "|:---|:------|:-------|:--------|:---|:--------------------|",
    ]

    for r in sorted(results, key=lambda x: (CATEGORY_ORDER.index(x["category"])
                                             if x["category"] in CATEGORY_ORDER else 99,
                                             x["number"])):
        repo_short = r.get("repo", "").split("/")[-1]
        if repo_short.startswith("sonic-"):
            repo_short = repo_short[6:]
        pr_link = f"[{repo_short}#{r['number']}]({r['url']})"

        title = r["title"]
        if len(title) > 55:
            title = title[:52] + "..."

        # Merged status: combine category + merge state into one cell
        cat_label = CATEGORY_LABELS.get(r["category"], "❓ Unknown")
        merge_state = r.get("merge_state") or "?"
        if r.get("mergeable") == "CONFLICTING":
            status_str = f"⚠️ CONFLICT"
        elif merge_state == "CLEAN" and r["category"] == "ready":
            status_str = "🚀 Ready"
        elif merge_state == "BEHIND":
            status_str = f"🔄 BEHIND"
        elif r["category"] in ("blocked_missing",):
            status_str = "🚫 CI never ran"
        elif r["category"] == "failing":
            status_str = "❌ CI failing"
        elif r["category"] == "pending":
            status_str = "⏳ CI pending"
        elif r["category"] == "needs_review":
            status_str = "👀 Needs review"
        elif r["category"] == "changes_requested":
            status_str = "🔧 Changes req"
        else:
            status_str = cat_label

        # Reviews
        approvals = [rv["user"] for rv in r["reviews"] if rv["state"] == "APPROVED"]
        changes_req = [rv["user"] for rv in r["reviews"] if rv["state"] == "CHANGES_REQUESTED"]
        review_parts = []
        if approvals:
            review_parts.append(f"✅ {', '.join(approvals)}")
        if changes_req:
            review_parts.append(f"🔧 {', '.join(changes_req)}")
        if r["codeowners_needed"]:
            review_parts.append(f"👤 {', '.join(r['codeowners_needed'])}")
        if not review_parts:
            review_parts.append("⚪ None")
        review_str = " ".join(review_parts)

        # CI (compact summary only)
        passed_count = sum(1 for c in r["checks"].values()
                          if c["conclusion"] in ("success", "neutral", "skipped"))
        failed_count = sum(1 for c in r["checks"].values()
                          if c["conclusion"] in ("failure", "error", "cancelled", "timed_out"))
        pending_count = sum(1 for c in r["checks"].values()
                           if c["status"] in ("queued", "in_progress", "pending"))
        missing = r["missing_checks"]

        ci_parts = []
        if passed_count:
            ci_parts.append(f"✅{passed_count}")
        if failed_count:
            ci_parts.append(f"❌{failed_count}")
        if pending_count:
            ci_parts.append(f"⏳{pending_count}")
        if missing:
            ci_parts.append(f"🚫{len(missing)}")
        ci_str = " ".join(ci_parts) if ci_parts else "—"

        unblock = _compute_unblock(r)

        lines.append(f"| {pr_link} | {title} | {status_str} | {review_str} | {ci_str} | {unblock} |")

    lines.append("")
    lines.append(f"*CI details: [pr-status-ci-detail.md](pr-status-ci-detail.md)*")
    lines.append("")

    main_report = "\n".join(lines)

    # --- CI detail file ---
    ci_lines = [
        f"# CI Detail — PR Status Report",
        "",
        f"> **Generated:** {timestamp}",
        "",
    ]

    for r in sorted(results, key=lambda x: x["number"]):
        repo_short = r.get("repo", "").split("/")[-1]
        if repo_short.startswith("sonic-"):
            repo_short = repo_short[6:]
        ci_lines.append(f"## [{repo_short}#{r['number']}]({r['url']}) — {r['title']}")
        ci_lines.append("")

        failed = [(n, c) for n, c in r["checks"].items()
                  if c["conclusion"] in ("failure", "error", "cancelled", "timed_out")]
        pending = [(n, c) for n, c in r["checks"].items()
                   if c["status"] in ("queued", "in_progress", "pending")]
        passed = [(n, c) for n, c in r["checks"].items()
                  if c["conclusion"] in ("success", "neutral", "skipped")]

        if failed:
            ci_lines.append("**Failed:**")
            for name, c in failed:
                url_str = f" ([log]({c['url']}))" if c.get("url") else ""
                ci_lines.append(f"- ❌ {name}{url_str}")
            ci_lines.append("")
        if pending:
            ci_lines.append("**Pending:**")
            for name, c in pending:
                ci_lines.append(f"- ⏳ {name}")
            ci_lines.append("")
        if r["missing_checks"]:
            ci_lines.append("**Never triggered:**")
            for m in r["missing_checks"]:
                ci_lines.append(f"- 🚫 {m}")
            ci_lines.append("")
        if passed:
            ci_lines.append(f"**Passed ({len(passed)}):** {', '.join(n for n, _ in passed)}")
            ci_lines.append("")

    ci_detail = "\n".join(ci_lines)

    return main_report, ci_detail


def _compute_unblock(r):
    """Determine the best actionable step to unblock a PR, with specific people."""
    category = r["category"]
    codeowners = r.get("codeowners_needed", [])
    missing = r.get("missing_checks", [])
    approvals = [rv["user"] for rv in r["reviews"] if rv["state"] == "APPROVED"]
    changes_req = [rv["user"] for rv in r["reviews"] if rv["state"] == "CHANGES_REQUESTED"]
    failed = [n for n, c in r["checks"].items()
              if c["conclusion"] in ("failure", "error", "cancelled", "timed_out")]
    has_conflict = r.get("mergeable") == "CONFLICTING"
    author = r.get("user", "author")

    # Check if only optional failures
    only_optional_failures = failed and all("[opt]" in _shorten_check(f) or "OPTIONAL" in f for f in failed)

    steps = []

    if has_conflict:
        steps.append(f"**@{author}:** rebase to fix conflict")

    if missing:
        steps.append(f"**Maintainer:** trigger {', '.join(missing)}")

    real_failures = [f for f in failed if "OPTIONAL" not in f]
    if real_failures:
        ms_only = all("ms_conflict" in f for f in real_failures)
        if ms_only:
            steps.append("**Maintainer:** resolve ms_conflict")
        else:
            steps.append(f"**@{author}:** investigate CI failures")

    if changes_req:
        steps.append(f"**@{author}:** address feedback from {', '.join(changes_req)}")

    if not approvals:
        if codeowners:
            people = _format_people(codeowners)
            steps.append(f"**Ask {people}** for review")
        else:
            steps.append("**Find reviewer**")
    elif codeowners:
        people = _format_people(codeowners)
        steps.append(f"**Ask {people}** (CODEOWNERS)")

    if not steps:
        if category == "ready":
            return "🚀 Ready — merge it!"
        if category == "behind":
            return f"**@{author}:** rebase to latest master"
        return "Waiting on CI"

    return "; ".join(steps)


def _format_people(owners):
    """Format CODEOWNERS list into readable names."""
    people = []
    for o in owners:
        clean = o.lstrip("@")
        # Strip org prefix for teams
        if "/" in clean:
            clean = "@" + clean
        else:
            clean = f"@{clean}"
        people.append(clean)
    return ", ".join(people)


def _shorten_check(name):
    """Shorten long Azure check names for table display."""
    name = name.replace("Azure.sonic-buildimage ", "").replace("Azure.sonic-mgmt ", "").replace("Azure.sonic-sairedis ", "")
    name = name.replace("(Test ", "(").replace("by Elastictest ", "").replace("[OPTIONAL]", "[opt]")
    name = name.replace("impacted-area-", "")
    if len(name) > 30:
        name = name[:27] + "..."
    return name


def _shorten_blocker(text):
    """Shorten blocker text for table display."""
    text = text.replace("Required CI never triggered: ", "🚫 ")
    text = text.replace("CI failures: ", "❌ CI: ")
    text = text.replace("CI pending: ", "⏳ ")
    text = text.replace("Changes requested by: ", "🔧 ")
    text = text.replace("No approving review yet", "No review")
    text = text.replace("CODEOWNERS review needed: ", "👤 ")
    text = text.replace("Merge conflict — needs rebase", "⚠️ Conflict")
    # Shorten long Azure names in blockers too
    text = text.replace("Azure.sonic-buildimage ", "").replace("Azure.sonic-mgmt ", "")
    text = text.replace("(Test ", "(").replace("by Elastictest ", "").replace("[OPTIONAL]", "[opt]")
    text = text.replace("impacted-area-", "")
    if len(text) > 80:
        text = text[:77] + "..."
    return text


def format_json(results):
    """JSON output."""
    return json.dumps(results, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

DEFAULT_REPOS = [
    "sonic-net/sonic-buildimage",
    "sonic-net/sonic-sairedis",
    "sonic-net/sonic-mgmt",
]


def main():
    parser = argparse.ArgumentParser(description="PR Status Report for sonic-net repos")
    parser.add_argument("--author", default="rustiqly", help="PR author (default: rustiqly)")
    parser.add_argument("--latest", type=int, metavar="N",
                        help="Check the N most recently updated open PRs (ignores --author)")
    parser.add_argument("--repos", nargs="+", default=DEFAULT_REPOS,
                        help="Repos to check (default: sonic-buildimage, sonic-sairedis, sonic-mgmt)")
    parser.add_argument("--json", dest="json_output", action="store_true", help="JSON output")
    parser.add_argument("--whatsapp", action="store_true", help="WhatsApp-formatted output")
    parser.add_argument("--markdown", "--md", action="store_true", help="Markdown table output")
    parser.add_argument("--output", "-o", help="Write output to file instead of stdout")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all check details")
    args = parser.parse_args()

    token = get_gh_token()
    all_results = []

    for full_repo in args.repos:
        owner, repo = full_repo.split("/")
        print(f"Checking {full_repo}...", file=sys.stderr)

        if args.latest:
            # Fetch N most recently updated open PRs (any author)
            query = f"is:pr is:open repo:{owner}/{repo} sort:updated-desc"
            per_page = min(args.latest, 100)
            max_pages = (args.latest + 99) // 100  # ceil division
            search = api_get("https://api.github.com/search/issues", token,
                            {"q": query, "per_page": str(per_page), "sort": "updated", "order": "desc"},
                            max_pages=max_pages)
            if not search or not search.get("items"):
                continue
            items = search["items"][:args.latest]
        else:
            # Get open PRs by author using search API
            query = f"is:pr is:open author:{args.author} repo:{owner}/{repo}"
            search = api_get("https://api.github.com/search/issues", token,
                            {"q": query, "per_page": "100"}, max_pages=1)
            if not search or not search.get("items"):
                continue
            items = search["items"]

        # Fetch full PR objects for the found issues
        prs = []
        for item in items:
            pr_data = api_get(f"https://api.github.com/repos/{owner}/{repo}/pulls/{item['number']}", token)
            if pr_data:
                prs.append(pr_data)
        if not prs:
            continue

        # Discover required checks + typical checks
        base_branch = prs[0]["base"]["ref"]
        required_checks = get_required_checks(owner, repo, base_branch, token)
        typical_checks = get_typical_checks(owner, repo, token) if required_checks is None else set()

        # CODEOWNERS
        codeowners_rules = fetch_codeowners(owner, repo, token)

        # Analyze each PR
        for pr in prs:
            print(f"  Analyzing #{pr['number']}...", file=sys.stderr)
            result = analyze_pr(pr, owner, repo, token, codeowners_rules, required_checks, typical_checks)
            result["repo"] = full_repo
            all_results.append(result)

    # Sort by category priority
    cat_order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    all_results.sort(key=lambda r: (cat_order.get(r["category"], 99), r["number"]))

    if args.json_output:
        output = format_json(all_results)
    elif args.whatsapp:
        output = format_whatsapp(all_results)
    elif args.markdown:
        main_report, ci_detail = format_markdown(all_results)
        if args.output:
            import os
            base, ext = os.path.splitext(args.output)
            ci_path = f"{base}-ci-detail{ext}"
            with open(args.output, "w") as f:
                f.write(main_report)
                if not main_report.endswith("\n"):
                    f.write("\n")
            with open(ci_path, "w") as f:
                f.write(ci_detail)
                if not ci_detail.endswith("\n"):
                    f.write("\n")
            print(f"Report written to {args.output}", file=sys.stderr)
            print(f"CI detail written to {ci_path}", file=sys.stderr)
        else:
            print(main_report)
            print("\n---\n")
            print(ci_detail)
        return
    else:
        output = format_terminal(all_results)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
            if not output.endswith("\n"):
                f.write("\n")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
