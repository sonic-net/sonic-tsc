# PR Status Report Tool

A Python CLI tool that generates accurate PR status reports for sonic-net
repositories by cross-referencing multiple GitHub API endpoints.

## Why

`gh pr view --json statusCheckRollup` silently drops required checks that never
ran (e.g. `ms_conflict`, `ms_checker`, `Azure.sonic-buildimage`). This tool
cross-references three API endpoints to catch those gaps:

- **Check Runs API** — GitHub Actions, Azure Pipelines, Copilot review
- **Commit Status API** — EasyCLA, legacy integrations
- **Required checks discovery** — branch protection rules, rulesets, or
  heuristic inference from recently merged PRs

## Features

- Discovers required checks via branch protection and rulesets APIs, with a
  heuristic fallback when admin access is unavailable
- Parses CODEOWNERS to identify required reviewers for changed files
- Fetches merge state via GraphQL (conflicts, behind, clean)
- Computes actionable "Best Way to Unblock" per PR with specific people
- Multiple output formats: terminal (colored), markdown tables, WhatsApp, JSON
- Markdown output splits CI details into a separate file for clean summary tables
- Zero external dependencies — uses only Python stdlib (`urllib`, `json`,
  `argparse`, `subprocess`)
- Authenticates via `gh auth token` (requires [GitHub CLI](https://cli.github.com/))

## Usage

```bash
# Default: open PRs by 'rustiqly' across buildimage, sairedis, mgmt
python3 pr_status.py

# Specific author
python3 pr_status.py --author lguohan

# Latest 100 open PRs regardless of author
python3 pr_status.py --latest 100 --repos sonic-net/sonic-buildimage

# Markdown report to file
python3 pr_status.py --md -o report.md
# Also generates report-ci-detail.md

# WhatsApp-formatted output
python3 pr_status.py --whatsapp

# JSON output
python3 pr_status.py --json

# Custom repos
python3 pr_status.py --repos sonic-net/sonic-swss sonic-net/sonic-gnmi
```

## Options

| Flag | Description |
|:-----|:------------|
| `--author NAME` | Filter PRs by author (default: `rustiqly`) |
| `--latest N` | Check the N most recently updated open PRs (ignores `--author`) |
| `--repos REPO [REPO ...]` | Repos to check (default: `sonic-net/sonic-buildimage sonic-net/sonic-sairedis sonic-net/sonic-mgmt`) |
| `--md`, `--markdown` | Markdown table output |
| `--whatsapp` | WhatsApp-formatted output |
| `--json` | JSON output |
| `-o FILE` | Write output to file (markdown mode also writes `*-ci-detail.md`) |
| `-v`, `--verbose` | Show all check details |

## Output Columns

| Column | Description |
|:-------|:------------|
| **PR** | Repo + PR number with link (e.g. `buildimage#25650`) |
| **Title** | PR title (truncated to 55 chars) |
| **Status** | Combined category + merge state (e.g. `❌ CI failing`, `⚠️ CONFLICT`, `🚀 Ready`) |
| **Reviews** | Approvals (✅), changes requested (🔧), CODEOWNERS needed (👤) |
| **CI** | Compact counts: ✅ passed, ❌ failed, ⏳ pending, 🚫 never triggered |
| **Best Way to Unblock** | Actionable next step with specific person (e.g. `**@author:** investigate CI failures; **Ask @lguohan** for review`) |

## Requirements

- Python 3.8+
- [GitHub CLI](https://cli.github.com/) (`gh`) authenticated with repo access

## How It Works

1. Finds open PRs via GitHub Search API
2. For each PR, fetches check runs, commit statuses, and changed files
3. Discovers required checks from branch protection rules or infers them from
   recently merged PRs
4. Matches changed files against CODEOWNERS rules
5. Queries GraphQL for merge state (`CLEAN`, `BEHIND`, `DIRTY`, `BLOCKED`)
6. Categorizes each PR and computes blockers and unblock recommendations
