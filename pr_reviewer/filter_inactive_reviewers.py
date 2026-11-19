#!/usr/bin/env python3
"""Filter generated reviewer lists using the last 90 days of sonic-net activity."""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import yaml


ORGANIZATION = "sonic-net"
BATCH_SIZE = 25
CONTRIBUTION_FIELDS = (
    "totalCommitContributions",
    "totalIssueContributions",
    "totalPullRequestContributions",
    "totalPullRequestReviewContributions",
)


def gh_api(endpoint, **fields):
    command = ["gh", "api", endpoint, "--include"]
    for name, value in fields.items():
        command.extend(["-f", f"{name}={value}"])
    for attempt in range(4):
        result = subprocess.run(command, capture_output=True, text=True)
        header_text, separator, body = result.stdout.partition("\n\n")
        headers = {}
        if separator and header_text.startswith("HTTP/"):
            for line in header_text.splitlines()[1:]:
                name, colon, value = line.partition(":")
                if colon:
                    headers[name.lower()] = value.strip()
            status = int(header_text.split()[1])
        else:
            body = result.stdout
            status = None
        errors = ""
        if result.returncode == 0:
            data = json.loads(body)
            errors = data.get("errors", "") if isinstance(data, dict) else ""
            if not errors:
                return data
        message = f"{errors} {result.stderr} {body}".lower()
        retryable = (
            status == 429 or (status is not None and 500 <= status < 600)
            or "rate limit" in message or "rate_limit" in message
            or "secondary rate" in message
        )
        if not retryable or attempt == 3:
            if result.returncode:
                raise subprocess.CalledProcessError(
                    result.returncode, command, output=body, stderr=result.stderr,
                )
            raise ValueError(f"GitHub API errors: {errors}")
        delay = 15 * (2 ** attempt)
        if status in (403, 429) or "rate" in str(errors).lower():
            delay = max(delay, 60)
        if "retry-after" in headers:
            delay = max(delay, int(headers["retry-after"]))
        if headers.get("x-ratelimit-remaining") == "0" and "x-ratelimit-reset" in headers:
            delay = max(delay, int(headers["x-ratelimit-reset"]) - time.time() + 1)
        print(f"GitHub request failed; retrying in {delay:.0f}s ({attempt + 1}/3)", file=sys.stderr)
        time.sleep(delay)


def pages(endpoint):
    separator = "&" if "?" in endpoint else "?"
    page = 1
    while True:
        items = gh_api(f"{endpoint}{separator}per_page=100&page={page}")
        if not isinstance(items, list):
            raise ValueError(f"Expected a list from {endpoint}")
        yield from items
        if len(items) < 100:
            return
        page += 1


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def isoformat(value):
    return value.isoformat().replace("+00:00", "Z")


def load_cache(path, now):
    if path is None or not path.exists():
        return {}
    with path.open() as stream:
        cache = json.load(stream)
    if (
        not isinstance(cache, dict) or cache.get("version") != 1
        or cache.get("organization") != ORGANIZATION
        or not isinstance(cache.get("viewer"), str)
        or not isinstance(cache.get("repos"), dict)
    ):
        raise ValueError(f"{path}: invalid activity cache; delete it to rebuild")
    for repo, endpoints in cache["repos"].items():
        if not isinstance(repo, str) or not repo.startswith(f"{ORGANIZATION}/"):
            raise ValueError(f"{path}: invalid cached repository")
        if not isinstance(endpoints, dict):
            raise ValueError(f"{path}: invalid cached endpoints")
        for kind, entry in endpoints.items():
            if kind not in ("issues", "pulls") or not isinstance(entry, dict):
                raise ValueError(f"{path}: invalid cached comment endpoint")
            through = timestamp(entry["through"])
            if through > now or not isinstance(entry["latest"], dict):
                raise ValueError(f"{path}: invalid cached scan timestamp or authors")
            for login, value in entry["latest"].items():
                if not isinstance(login, str) or not login or timestamp(value) > through:
                    raise ValueError(f"{path}: invalid cached author activity")
    return cache


def save_cache(path, cache):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(cache, stream, indent=2, sort_keys=True)
            stream.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def active_reviewers(logins, now, cache=None):
    bots = {login for login in logins if login.casefold().endswith("[bot]")}
    if bots:
        print(f"Excluding bot reviewer accounts: {', '.join(sorted(bots))}", file=sys.stderr)
        logins = logins - bots
    if not logins:
        return set()
    if cache is None:
        cache = {}
    since = now - timedelta(days=90)
    metadata = gh_api(
        "graphql",
        query="query($login: String!) { organization(login: $login) { id } viewer { login } }",
        login=ORGANIZATION,
    )["data"]
    organization = metadata["organization"]
    if organization is None:
        raise ValueError(f"GitHub organization {ORGANIZATION} was not found")
    viewer = metadata["viewer"]["login"]
    if cache and cache["viewer"] != viewer:
        print("GitHub account changed; rebuilding comment activity cache", file=sys.stderr)
        cache.clear()
    cache.update(version=1, organization=ORGANIZATION, viewer=viewer)
    repositories = list(pages(f"orgs/{ORGANIZATION}/repos"))
    visible = {repo["full_name"] for repo in repositories}
    cache["repos"] = {
        name: entries for name, entries in cache.get("repos", {}).items() if name in visible
    }

    active = set()
    for endpoints in cache["repos"].values():
        for entry in endpoints.values():
            entry["latest"] = {
                login: value for login, value in entry["latest"].items()
                if since <= timestamp(value) <= now
            }
            active.update(logins.intersection(entry["latest"]))

    pending = sorted(logins - active)
    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start:start + BATCH_SIZE]
        selections = []
        for index, login in enumerate(batch):
            selections.append("""
          u%d: user(login: %s) {
            contributionsCollection(organizationID: $organization, from: $from, to: $to) {
              totalCommitContributions
              totalIssueContributions
              totalPullRequestContributions
              totalPullRequestReviewContributions
            }
          }
            """ % (index, json.dumps(login)))
        query = (
            "query($organization: ID!, $from: DateTime!, $to: DateTime!) {"
            + "".join(selections) + "}"
        )
        users = gh_api(
            "graphql", query=query, organization=organization["id"],
            **{"from": isoformat(since), "to": isoformat(now)},
        )["data"]
        for index, login in enumerate(batch):
            user = users[f"u{index}"]
            if user is None:
                raise ValueError(f"GitHub user {login} was not found")
            contributions = user["contributionsCollection"]
            if any(contributions[field] > 0 for field in CONTRIBUTION_FIELDS):
                active.add(login)

    if active == logins:
        return active

    # These endpoints include comments on old issues/PRs and inline review comments.
    # The user events feed is capped, so it cannot establish 90-day inactivity.
    for repo in repositories:
        endpoints = cache["repos"].setdefault(repo["full_name"], {})
        for kind in ("issues", "pulls"):
            entry = endpoints.get(kind)
            latest = dict(entry["latest"]) if entry else {}
            # Overlap incremental scans to tolerate indexing delays and page changes.
            scan_since = max(since, timestamp(entry["through"]) - timedelta(days=1)) if entry else since
            endpoint = f"repos/{repo['full_name']}/{kind}/comments?since={isoformat(scan_since)}"
            for comment in pages(endpoint):
                author = comment["user"]
                if author is None:
                    continue
                login = author["login"].casefold()
                at = timestamp(comment["updated_at"])
                if since <= at <= now:
                    if login not in latest or timestamp(latest[login]) < at:
                        latest[login] = isoformat(at)
                    if login in logins:
                        active.add(login)
            endpoints[kind] = {"through": isoformat(now), "latest": latest}
            if active == logins:
                return active
    return active


def filter_files(paths, now, cache_path=None):
    documents = {}
    logins = set()
    for path in paths:
        with path.open() as stream:
            data = yaml.safe_load(stream)
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a folder-to-reviewer mapping")
        for folder, owners in data.items():
            if not isinstance(folder, str) or not isinstance(owners, dict):
                raise ValueError(f"{path}: invalid folder-to-reviewer mapping")
            for login in owners:
                if not isinstance(login, str) or not login:
                    raise ValueError(f"{path}: invalid reviewer login")
                logins.add(login.casefold())
        documents[path] = data

    # Finish every lookup before changing any files. Failure must not mean inactivity.
    cache = load_cache(cache_path, now)
    active = active_reviewers(logins, now, cache)
    if cache_path is not None and cache:
        save_cache(cache_path, cache)
    for path, data in documents.items():
        filtered = {}
        for folder, owners in data.items():
            kept = {login: score for login, score in owners.items() if login.casefold() in active}
            if kept:
                filtered[folder] = kept
        with path.open("w") as stream:
            yaml.safe_dump(filtered, stream, indent=2, allow_unicode=True, default_flow_style=False)
    removed = sorted(logins - active)
    print(
        f"90-day {ORGANIZATION} activity filter: kept {len(active)} reviewers; "
        f"removed {len(removed)} inactive or ineligible reviewers"
        + (f": {', '.join(removed)}" if removed else ""),
        file=sys.stderr,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, help="Persistent incremental comment activity cache")
    parser.add_argument("files", nargs="+", type=Path, help="Generated YAML files to filter in place")
    args = parser.parse_args()
    try:
        filter_files(args.files, datetime.now(timezone.utc), args.cache)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f"Reviewer activity filtering failed: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
