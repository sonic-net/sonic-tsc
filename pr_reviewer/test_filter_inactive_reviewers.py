from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

import filter_inactive_reviewers as activity


NOW = datetime(2026, 11, 17, 6, tzinfo=timezone.utc)


class ActivityTests(unittest.TestCase):
    def contribution_api(self, totals, now=NOW):
        def api(endpoint, **fields):
            self.assertEqual(endpoint, "graphql")
            if "organization" not in fields:
                return {"data": {"organization": {"id": "org-id"}, "viewer": {"login": "automation"}}}
            self.assertEqual(fields["organization"], "org-id")
            self.assertEqual(fields["from"], activity.isoformat(now - timedelta(days=90)))
            self.assertEqual(fields["to"], activity.isoformat(now))
            users = {}
            for alias, login in re.findall(r'(u\d+): user\(login: "([^"]+)"\)', fields["query"]):
                contributions = dict.fromkeys(activity.CONTRIBUTION_FIELDS, 0)
                contributions.update(totals.get(login, {}))
                users[alias] = {"contributionsCollection": contributions}
            return {"data": users}
        return api

    def test_each_contribution_type_keeps_user_without_comment_scan(self):
        totals = {
            f"user-{index}": {field: 1}
            for index, field in enumerate(activity.CONTRIBUTION_FIELDS)
        }
        with patch.object(activity, "gh_api", side_effect=self.contribution_api(totals)), \
                patch.object(activity, "pages", return_value=iter([])) as pages:
            self.assertEqual(activity.active_reviewers(set(totals), NOW), set(totals))
        pages.assert_called_once_with("orgs/sonic-net/repos")

    def test_comments_across_repositories_and_exact_window(self):
        since = NOW - timedelta(days=90)

        def comment(login, at):
            return {"user": {"login": login}, "updated_at": activity.isoformat(at)}

        def pages(endpoint):
            if endpoint == "orgs/sonic-net/repos":
                return iter([
                    {"full_name": "sonic-net/sonic-mgmt"},
                    {"full_name": "sonic-net/another-repo"},
                ])
            if "/sonic-mgmt/" in endpoint:
                return iter([])
            if "/issues/comments" in endpoint:
                return iter([
                    comment("Issue-Author", since),
                    comment("edited-author", NOW),
                    comment("old-author", since - timedelta(seconds=1)),
                    comment("future-author", NOW + timedelta(seconds=1)),
                    {"user": None},
                ])
            return iter([comment("inline-author", NOW - timedelta(days=1))])

        candidates = {"issue-author", "edited-author", "inline-author", "old-author", "future-author"}
        with patch.object(activity, "gh_api", side_effect=self.contribution_api({})), \
                patch.object(activity, "pages", side_effect=pages):
            self.assertEqual(
                activity.active_reviewers(candidates, NOW),
                {"issue-author", "edited-author", "inline-author"},
            )

    def test_pagination_fetches_every_page(self):
        first = [{"number": number} for number in range(100)]
        with patch.object(activity, "gh_api", side_effect=[first, [{"number": 100}]]) as api:
            self.assertEqual(len(list(activity.pages("comments?since=date"))), 101)
        self.assertEqual(
            [call.args[0] for call in api.call_args_list],
            ["comments?since=date&per_page=100&page=1", "comments?since=date&per_page=100&page=2"],
        )

    def test_pagination_rejects_error_shaped_response(self):
        with patch.object(activity, "gh_api", return_value={"message": "failure"}):
            with self.assertRaises(ValueError):
                list(activity.pages("comments"))

    def test_graphql_errors_are_not_inactivity(self):
        result = subprocess.CompletedProcess([], 0, '{"errors": [{"message": "invalid query"}]}', "")
        with patch.object(activity.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(ValueError, "invalid query"):
                activity.gh_api("graphql", query="query {}")

    def test_http_failure_propagates(self):
        error = subprocess.CalledProcessError(1, ["gh"], stderr="HTTP 503")
        with patch.object(activity.subprocess, "run", side_effect=error):
            with self.assertRaises(subprocess.CalledProcessError):
                activity.active_reviewers({"user"}, NOW)

    def test_empty_candidates_need_no_api(self):
        with patch.object(activity, "gh_api") as api:
            self.assertEqual(activity.active_reviewers(set(), NOW), set())
        api.assert_not_called()

    def test_bot_only_candidates_need_no_api(self):
        with patch.object(activity, "gh_api") as api, patch.object(activity, "pages") as pages:
            self.assertEqual(activity.active_reviewers({"dependabot[bot]", "APP[BOT]"}, NOW), set())
        api.assert_not_called()
        pages.assert_not_called()

    def test_cached_bots_are_excluded_before_batch_lookup_and_file_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviewers.yaml"
            path.write_text("/: {Active: 0.6, 'dependabot[bot]': 0.9}\n/bot-only/: {'app[bot]': .inf}\n")
            cache_path = Path(directory) / "cache.json"
            cache = {
                "version": 1, "organization": "sonic-net", "viewer": "automation",
                "repos": {"sonic-net/example": {"issues": {
                    "through": activity.isoformat(NOW),
                    "latest": {"dependabot[bot]": activity.isoformat(NOW)},
                }}},
            }
            activity.save_cache(cache_path, cache)
            with patch.object(
                activity, "gh_api",
                side_effect=self.contribution_api({"active": {"totalCommitContributions": 1}}),
            ) as api, patch.object(
                activity, "pages", return_value=iter([{"full_name": "sonic-net/example"}]),
            ):
                activity.filter_files([path], NOW, cache_path)
            self.assertEqual(yaml.safe_load(path.read_text()), {"/": {"Active": 0.6}})
            self.assertEqual(api.call_count, 2)
            query = api.call_args_list[1].kwargs["query"]
            self.assertIn('user(login: "active")', query)
            self.assertNotIn("[bot]", query)

    def test_unresolved_human_user_still_fails(self):
        api = self.contribution_api({})

        def unresolved(endpoint, **fields):
            data = api(endpoint, **fields)
            if "organization" in fields:
                data["data"]["u0"] = None
            return data

        with patch.object(activity, "gh_api", side_effect=unresolved), \
                patch.object(activity, "pages", return_value=iter([])):
            with self.assertRaisesRegex(ValueError, "GitHub user missing-user was not found"):
                activity.active_reviewers({"missing-user"}, NOW)

    def test_filters_combined_candidates_without_changing_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / "one.yaml", Path(directory) / "two.yaml"]
            paths[0].write_text("/: {Active: 0.6, inactive: 0.4}\n/empty/: {inactive: 1}\n")
            paths[1].write_text("/: {ACTIVE: .inf, other: 0.8}\n")
            with patch.object(activity, "active_reviewers", return_value={"active"}) as lookup:
                activity.filter_files(paths, NOW)
            lookup.assert_called_once_with({"active", "inactive", "other"}, NOW, {})
            self.assertEqual(yaml.safe_load(paths[0].read_text()), {"/": {"Active": 0.6}})
            self.assertEqual(yaml.safe_load(paths[1].read_text()), {"/": {"ACTIVE": float("inf")}})

    def test_failed_lookup_leaves_all_files_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / "one.yaml", Path(directory) / "two.yaml"]
            original = "/: {user: 0.6}\n"
            for path in paths:
                path.write_text(original)
            with patch.object(activity, "active_reviewers", side_effect=ValueError("API failure")):
                with self.assertRaisesRegex(ValueError, "API failure"):
                    activity.filter_files(paths, NOW)
            for path in paths:
                self.assertEqual(path.read_text(), original)

    def test_no_active_users_produces_empty_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviewers.yaml"
            path.write_text("/: {inactive: 0.6}\n")
            with patch.object(activity, "active_reviewers", return_value=set()):
                activity.filter_files([path], NOW)
            self.assertEqual(yaml.safe_load(path.read_text()), {})

    def test_invalid_input_fails_before_lookup_or_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviewers.yaml"
            path.write_text("- not a mapping\n")
            with patch.object(activity, "active_reviewers") as lookup:
                with self.assertRaises(ValueError):
                    activity.filter_files([path], NOW)
            lookup.assert_not_called()
            self.assertEqual(path.read_text(), "- not a mapping\n")

    def test_generator_publishes_only_after_successful_filter(self):
        source = Path(__file__).parent
        for fail in (False, True):
            with self.subTest(activity_lookup_fails=fail), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for name in ("generate_pr_reviewer.sh", "filter_inactive_reviewers.py"):
                    shutil.copyfile(source / name, root / name)
                (root / "repos").write_text("sonic-net/example\n")
                output = root / "example"
                output.mkdir()
                (output / "contributors.yaml").write_text("[]\n")
                original = "/: {existing: 1}\n"
                for name in ("pr_reviewer-by-files.yml", "raw_change_weights.yml", "raw_review_weights.yml"):
                    (output / name).write_text(original)

                bin_dir = root / "bin"
                bin_dir.mkdir()
                scripts = {
                    "uv": """#!/bin/bash
if [ "$1" = venv ]; then
    mkdir -p "$3/bin"
    ln -s "$TEST_PYTHON" "$3/bin/python"
    cp "$TEST_CODEOWNERS" "$3/bin/codeowners-cli"
fi
""",
                    "git": """#!/bin/bash
mkdir -p "${@: -1}"
""",
                    "codeowners-cli": """#!/bin/bash
printf '/: {Active: 0.6, inactive: 0.4}\\n'
""",
                    "gh": f"""#!{sys.executable}
import json
import os
import re
import sys
if os.environ["TEST_ACTIVITY_FAIL"] == "1":
    print("activity API unavailable", file=sys.stderr)
    sys.exit(1)
if sys.argv[2] != "graphql":
    print("[]")
elif "login=sonic-net" in sys.argv:
    print(json.dumps({{"data": {{"organization": {{"id": "org-id"}}, "viewer": {{"login": "automation"}}}}}}))
else:
    query = next(arg for arg in sys.argv if arg.startswith("query="))
    users = {{}}
    for alias, login in re.findall(r'(u\\d+): user\\(login: "([^"]+)"\\)', query):
        fields = {dict.fromkeys(activity.CONTRIBUTION_FIELDS, 0)!r}
        fields["totalCommitContributions"] = int(login == "active")
        users[alias] = {{"contributionsCollection": fields}}
    print(json.dumps({{"data": users}}))
""",
                }
                for name, script in scripts.items():
                    path = bin_dir / name
                    path.write_text(script)
                    path.chmod(0o755)
                env = {
                    **os.environ,
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "TEST_PYTHON": sys.executable,
                    "TEST_CODEOWNERS": str(bin_dir / "codeowners-cli"),
                    "TEST_ACTIVITY_FAIL": str(int(fail)),
                    "PYTHONDONTWRITEBYTECODE": "1",
                }
                result = subprocess.run(
                    ["bash", str(root / "generate_pr_reviewer.sh"), "-t", str(root), "-R"],
                    env=env, capture_output=True, text=True,
                )
                if fail:
                    self.assertNotEqual(result.returncode, 0, result.stderr)
                    self.assertIn("activity API unavailable", result.stderr)
                    for name in ("pr_reviewer-by-files.yml", "raw_change_weights.yml", "raw_review_weights.yml"):
                        self.assertEqual((output / name).read_text(), original)
                    self.assertFalse((root / "activity_cache.json").exists())
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(
                        yaml.safe_load((output / "pr_reviewer-by-files.yml").read_text()),
                        {"/": {"Active": 0.6}},
                    )
                    self.assertEqual(
                        yaml.safe_load((output / "raw_change_weights.yml").read_text()),
                        {"/": {"Active": 0.6, "inactive": 0.4}},
                    )
                    self.assertEqual((output / "raw_review_weights.yml").read_text(), original)
                    self.assertEqual(
                        activity.load_cache(root / "activity_cache.json", datetime.now(timezone.utc))["viewer"],
                        "automation",
                    )

    def test_contributions_are_batched_in_groups_of_25(self):
        totals = {f"user-{index}": {"totalCommitContributions": 1} for index in range(204)}
        with patch.object(activity, "gh_api", side_effect=self.contribution_api(totals)) as api, \
                patch.object(activity, "pages", return_value=iter([])):
            self.assertEqual(activity.active_reviewers(set(totals), NOW), set(totals))
        self.assertEqual(api.call_count, 10)  # Organization/viewer + nine contribution batches.
        for call in api.call_args_list[1:]:
            self.assertLessEqual(call.kwargs["query"].count("user(login:"), 25)

    def test_full_scan_request_floor_is_121_for_204_users_and_55_repos(self):
        graphql = self.contribution_api({})

        def api(endpoint, **fields):
            if endpoint == "graphql":
                return graphql(endpoint, **fields)
            if endpoint.startswith("orgs/"):
                return [{"full_name": f"sonic-net/repo-{index}"} for index in range(55)]
            return []

        cache = {}
        with patch.object(activity, "gh_api", side_effect=api) as requests:
            self.assertEqual(
                activity.active_reviewers({f"user-{index}" for index in range(204)}, NOW, cache),
                set(),
            )
        self.assertEqual(requests.call_count, 121)
        self.assertEqual(len(cache["repos"]), 55)

    def test_incremental_scan_caches_all_authors_and_expires_old_activity(self):
        cache = {}
        initial = NOW - timedelta(days=7)
        requests = []

        def pages(endpoint):
            requests.append(endpoint)
            if endpoint == "orgs/sonic-net/repos":
                return iter([{"full_name": "sonic-net/example"}])
            if "/issues/comments" in endpoint:
                return iter([{
                    "user": {"login": "future-candidate"},
                    "updated_at": activity.isoformat(initial - timedelta(days=1)),
                }])
            return iter([])

        with patch.object(activity, "gh_api", side_effect=self.contribution_api({}, initial)), \
                patch.object(activity, "pages", side_effect=pages):
            self.assertEqual(activity.active_reviewers({"inactive"}, initial, cache), set())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            activity.save_cache(path, cache)
            cache = activity.load_cache(path, NOW)

        with patch.object(activity, "gh_api", side_effect=self.contribution_api({})) as api, \
                patch.object(activity, "pages", side_effect=pages):
            self.assertEqual(
                activity.active_reviewers({"inactive", "future-candidate"}, NOW, cache),
                {"future-candidate"},
            )
        query = api.call_args_list[1].kwargs["query"]
        self.assertNotIn("future-candidate", query)
        self.assertTrue(any("since=2026-11-09T06:00:00Z" in endpoint for endpoint in requests))

        # A repository that is no longer visible cannot provide cached eligibility.
        with patch.object(activity, "gh_api", side_effect=self.contribution_api({})), \
                patch.object(activity, "pages", return_value=iter([])):
            self.assertEqual(activity.active_reviewers({"future-candidate"}, NOW, cache), set())
        self.assertEqual(cache["repos"], {})

    def test_expired_cached_activity_uses_full_window_after_long_gap(self):
        since = NOW - timedelta(days=90)
        cache = {
            "version": 1, "organization": "sonic-net", "viewer": "automation",
            "repos": {"sonic-net/example": {"issues": {
                "through": activity.isoformat(since - timedelta(days=1)),
                "latest": {"old": activity.isoformat(since - timedelta(days=2))},
            }}},
        }
        endpoints = []

        def pages(endpoint):
            endpoints.append(endpoint)
            return iter([{"full_name": "sonic-net/example"}]) if endpoint.startswith("orgs/") else iter([])

        with patch.object(activity, "gh_api", side_effect=self.contribution_api({})), \
                patch.object(activity, "pages", side_effect=pages):
            self.assertEqual(activity.active_reviewers({"old"}, NOW, cache), set())
        self.assertEqual(cache["repos"]["sonic-net/example"]["issues"]["latest"], {})
        self.assertTrue(all("since=2026-08-19T06:00:00Z" in endpoint for endpoint in endpoints[1:]))

    def test_cache_is_atomic_and_invalid_cache_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            cache = {"version": 1, "organization": "sonic-net", "viewer": "automation", "repos": {}}
            activity.save_cache(path, cache)
            self.assertEqual(activity.load_cache(path, NOW), cache)
            with patch.object(activity.json, "dump", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    activity.save_cache(path, cache)
            self.assertEqual(activity.load_cache(path, NOW), cache)
            self.assertEqual(list(Path(directory).iterdir()), [path])
            path.write_text('{"version": 99}')
            with self.assertRaisesRegex(ValueError, "invalid activity cache"):
                activity.load_cache(path, NOW)

    def test_failed_scan_does_not_update_persistent_cache_or_reviewers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviewers.yaml"
            path.write_text("/: {inactive: 0.6}\n")
            cache_path = Path(directory) / "cache.json"
            original = '{"version": 1, "organization": "sonic-net", "viewer": "automation", "repos": {}}\n'
            cache_path.write_text(original)

            def pages(endpoint):
                if endpoint.startswith("orgs/"):
                    return iter([{"full_name": "sonic-net/example"}])
                if "/issues/comments" in endpoint:
                    return iter([{"user": {"login": "another"}, "updated_at": activity.isoformat(NOW)}])
                raise ValueError("comment scan failed")

            with patch.object(activity, "gh_api", side_effect=self.contribution_api({})), \
                    patch.object(activity, "pages", side_effect=pages):
                with self.assertRaisesRegex(ValueError, "comment scan failed"):
                    activity.filter_files([path], NOW, cache_path)
            self.assertEqual(path.read_text(), "/: {inactive: 0.6}\n")
            self.assertEqual(cache_path.read_text(), original)

    def test_transient_http_error_retries_and_reads_headers(self):
        failure = subprocess.CompletedProcess(
            [], 1, 'HTTP/2.0 503 Service Unavailable\nRetry-After: 30\n\nunavailable', "HTTP 503",
        )
        success = subprocess.CompletedProcess([], 0, 'HTTP/2.0 200 OK\nContent-Type: application/json\n\n[]', "")
        with patch.object(activity.subprocess, "run", side_effect=[failure, success]) as run, \
                patch.object(activity.time, "sleep") as sleep:
            self.assertEqual(activity.gh_api("comments"), [])
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(30)

    def test_graphql_rate_limit_retries_but_exhaustion_fails(self):
        failure = subprocess.CompletedProcess(
            [], 0, '{"errors": [{"type": "RATE_LIMITED", "message": "API rate limit exceeded"}]}', "",
        )
        with patch.object(activity.subprocess, "run", return_value=failure) as run, \
                patch.object(activity.time, "sleep") as sleep:
            with self.assertRaisesRegex(ValueError, "rate limit"):
                activity.gh_api("graphql", query="query {}")
        self.assertEqual(run.call_count, 4)
        self.assertEqual(sleep.call_count, 3)
        self.assertTrue(all(call.args[0] >= 60 for call in sleep.call_args_list))

    def test_account_change_rebuilds_cache(self):
        cache = {
            "version": 1, "organization": "sonic-net", "viewer": "old-account",
            "repos": {"sonic-net/example": {"issues": {
                "through": activity.isoformat(NOW),
                "latest": {"old": activity.isoformat(NOW)},
            }}},
        }
        endpoints = []

        def pages(endpoint):
            endpoints.append(endpoint)
            return iter([{"full_name": "sonic-net/example"}]) if endpoint.startswith("orgs/") else iter([])

        with patch.object(activity, "gh_api", side_effect=self.contribution_api({})), \
                patch.object(activity, "pages", side_effect=pages):
            self.assertEqual(activity.active_reviewers({"old"}, NOW, cache), set())
        self.assertEqual(cache["viewer"], "automation")
        self.assertTrue(all("since=2026-08-19T06:00:00Z" in endpoint for endpoint in endpoints[1:]))

    def test_new_repository_and_comment_endpoint_get_full_window(self):
        cache = {
            "version": 1, "organization": "sonic-net", "viewer": "automation",
            "repos": {"sonic-net/example": {"issues": {
                "through": activity.isoformat(NOW - timedelta(days=7)), "latest": {},
            }}},
        }
        endpoints = []

        def pages(endpoint):
            endpoints.append(endpoint)
            if endpoint.startswith("orgs/"):
                return iter([
                    {"full_name": "sonic-net/example"}, {"full_name": "sonic-net/new"},
                ])
            return iter([])

        with patch.object(activity, "gh_api", side_effect=self.contribution_api({})), \
                patch.object(activity, "pages", side_effect=pages):
            self.assertEqual(activity.active_reviewers({"inactive"}, NOW, cache), set())
        self.assertIn("since=2026-11-09T06:00:00Z", endpoints[1])
        self.assertTrue(all("since=2026-08-19T06:00:00Z" in endpoint for endpoint in endpoints[2:]))

    def test_primary_rate_limit_waits_for_reset(self):
        failure = subprocess.CompletedProcess(
            [], 1, 'HTTP/2.0 403 Forbidden\nX-RateLimit-Remaining: 0\nX-RateLimit-Reset: 1100\n\n{}',
            "API rate limit exceeded",
        )
        success = subprocess.CompletedProcess([], 0, "[]", "")
        with patch.object(activity.subprocess, "run", side_effect=[failure, success]), \
                patch.object(activity.time, "time", return_value=1000), \
                patch.object(activity.time, "sleep") as sleep:
            self.assertEqual(activity.gh_api("comments"), [])
        sleep.assert_called_once_with(101)

    def test_authentication_error_is_not_retried(self):
        failure = subprocess.CompletedProcess([], 1, "HTTP/2.0 401 Unauthorized\n\n{}", "Bad credentials")
        with patch.object(activity.subprocess, "run", return_value=failure) as run, \
                patch.object(activity.time, "sleep") as sleep:
            with self.assertRaises(subprocess.CalledProcessError):
                activity.gh_api("comments")
        self.assertEqual(run.call_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
