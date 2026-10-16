# Code owners data

Per-repo code owner data generated with
[sonic-pipelines/scripts/code-owners](https://github.com/sonic-net/sonic-pipelines/tree/main/scripts/code-owners).

For each repo listed in `repos`, `<repo>/` contains:

- `pr_reviewer-by-files.yml`: folder -> {contributor: score} for qualified contributors (not just the top 3): only owners with score >= 0.6 and raw decayed change weight >= 50 in the folder (`-s`, `-w`; raw files keep everyone). Score = 0.6 x change score + 0.4 x approval score, each the decayed weight divided by the top contributor's weight in that folder (0-1). Approvals only; PR author and bots excluded; PR history comes from `dump_reviews.sh`, fetched each run. Used for reviewer assignment and approver qualification (generated)
- `raw_change_weights.yml`: same layout with raw decayed changed-line counts, for tuning thresholds and applying a minimum-weight floor at qualification time (generated, not committed)
- `raw_review_weights.yml`: raw decayed approval counts per folder (generated, not committed; `-R` skips review history)
- `contributors.yaml`: contributor cache, reused between runs (generated)
- `folder_presets.yaml`: optional manual presets (not generated, edit by hand)

Updated weekly by `update_pr_reviewer_score.yml` (Azure pipeline), which opens an automerge PR.
Run manually: `GITHUB_API_TOKENS=... ./generate_pr_reviewer.sh [-r "sonic-net/sonic-swss"]`.
Each `codeowners-cli` invocation is retried up to four times with exponential backoff when GitHub API or other transient failures occur.

Rollout: only `sonic-net/sonic-mgmt` is enabled in `repos` (pilot); uncomment other repos to roll out.
Weights are changed lines (additions + deletions) over the last 730 days, decayed by commit age with a 180-day half-life (`-l` to change, `0` to disable).
