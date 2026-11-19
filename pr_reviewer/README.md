# Code owners data

Per-repo code owner data generated with
[sonic-pipelines/scripts/code-owners](https://github.com/sonic-net/sonic-pipelines/tree/main/scripts/code-owners).

For each repo listed in `repos`, `<repo>/` contains:

- `pr_reviewer-by-files.yml`: folder -> {contributor: score} for qualified contributors: only owners with score >= 0.1 and raw decayed change weight >= 50 in the folder (`-s`, `-w`; raw files keep everyone), and activity in `sonic-net` in the last 90 days. Score = 0.6 x change score + 0.4 x approval score, each the decayed weight divided by the top contributor's weight in that folder (0-1). Approvals only; PR author and bots excluded; PR history comes from `dump_reviews.sh`, fetched each run. Used for reviewer assignment and approver qualification (generated)
- `raw_change_weights.yml`: same layout with raw decayed changed-line counts, for tuning thresholds and applying a minimum-weight floor at qualification time (generated)
- `raw_review_weights.yml`: raw decayed approval counts per folder (generated, `-R` skips review history)
- `contributors.yaml`: contributor cache, reused between runs (generated)
- `folder_presets.yaml`: optional manual presets (not generated, edit by hand)

Updated weekly by `update_pr_reviewer_score.yml` (Azure pipeline), which opens an automerge PR.
Run manually: `GITHUB_API_TOKENS=... ./generate_pr_reviewer.sh [-r "sonic-net/sonic-swss"]`.
Each `codeowners-cli` invocation is retried up to four times with exponential backoff when GitHub API or other transient failures occur.

On every run, [filter_inactive_reviewers.py](filter_inactive_reviewers.py) excludes
users without activity during the rolling 90-day UTC window, across **all
`sonic-net` repositories**, not just the repositories enabled in `repos`.
Activity means a GitHub-counted commit contribution, opened issue or PR, submitted
PR review, or an issue/PR comment (including inline review comments) created or
edited during the window. Commit contributions follow GitHub's contribution
attribution and branch rules. Reactions are not counted. Activity is limited to
repositories and contributions visible to the authenticated `gh` account.
Bot logins ending in `[bot]` are excluded from reviewer eligibility before any
activity lookup, even if they have recent cached activity. GitHub's GraphQL
`user(login:)` lookup cannot resolve these bot accounts. Other unresolved users
and API errors still fail the run rather than being treated as inactivity.

The filter uses GitHub's organization-scoped contributions API and paginated
repository comment APIs, not the capped user events feed. `gh` must be
authenticated (as it already is for review history). Activity is checked once per
run for the combined candidates from all generated repositories, including when
`-R` is used. Lookup errors fail the run before publishing any generated score or
weight files, rather than treating an API failure as inactivity.

To reduce API traffic, contribution lookups are batched in groups of 25 users.
The generator persists `activity_cache.json` alongside this README; the existing
weekly pipeline includes it in the generated-data PR so it survives clean
checkouts. The cache stores the latest comment timestamp per author and a scan
watermark for each repository/comment endpoint, not comment bodies. All comment
authors are cached so newly qualified reviewers can reuse previous scans.
Previously scanned endpoints fetch only updates since their watermark, with a
one-day overlap; new repositories and gaps longer than 90 days use the full
90-day window. Cached activity expires at the original timestamp, never 90 days
after a lookup. Recent cached commenters need no contribution query.

For 204 uncached candidates and 55 repositories, a full scan starts at 121 API
requests (one organization/account query, nine contribution batches, one
repository-list page, and 110 comment endpoint pages), plus extra comment pages
and retries. Warm runs avoid rereading 90 days of comments but still need at
least one request per scanned comment endpoint. If contributions or cached
comments establish that every candidate is active, comment scanning is skipped.

The cache is refreshed atomically only after successful lookups, is scoped to
the authenticated GitHub account, and drops repositories no longer visible to
that account. Delete it to force a full rebuild (including after changing token
permissions for the same account). Standalone filter invocations can use
`--cache <path>`; without it, nothing is persisted. Transient HTTP 5xx and rate
limit errors are retried up to three times, honoring GitHub's retry/reset
headers. Authentication and other permanent errors fail immediately.

Only the qualified reviewer lists are filtered; raw weights and contributor
availability settings are preserved. Scores are not recalculated, folders with
no remaining reviewers are omitted, and the activity check also applies to
manually preset owners. Users become eligible again automatically when activity
resumes, subject to existing qualification and availability rules.

Run the filter tests with `python3 -m unittest discover -s pr_reviewer -p 'test_*.py'`
from the repository root (requires PyYAML, also provided by `codeowners-cli`).

Rollout: only `sonic-net/sonic-mgmt` is enabled in `repos` (pilot); uncomment other repos to roll out.
Weights are changed lines (additions + deletions) over the last 730 days, decayed by commit age with a 180-day half-life (`-l` to change, `0` to disable).
