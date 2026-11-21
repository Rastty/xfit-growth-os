"""Deterministic offline checks for the real-publication mobile QA gate."""
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.xfit_release_gate import (ReleaseGateError, LIVE_WORKFLOWS,
                                       workflow_push_paths, expected_releases,
                                       check_release_runs, wait_for_releases)


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.sources = {name: Path(path).read_text(encoding="utf-8")
                        for name, path in LIVE_WORKFLOWS.items()}
        self.sha = "a" * 40

    def test_shared_chooser_changes_refresh_both_live_guides(self):
        for change in ("scripts/xfit_quick_pick.py", "tests/test_quick_pick.py"):
            self.assertEqual(expected_releases({change}, self.sources), set(LIVE_WORKFLOWS))

    def test_one_page_edits_select_correct_live_workflows(self):
        self.assertEqual(expected_releases({"scripts/xfit_whey_guide.py"}, self.sources),
                         {"XFIT Whey Advisor Live"})
        self.assertEqual(expected_releases({"scripts/xfit_creatine_guide.py"}, self.sources),
                         set(LIVE_WORKFLOWS))  # whey imports creatine's link builder
        self.assertEqual(expected_releases({"tests/test_whey_guide.py"}, self.sources),
                         {"XFIT Whey Advisor Live"})
        self.assertEqual(expected_releases({"tests/live_page_qa.cjs"}, self.sources), set())

    def test_publisher_only_maintenance_never_triggers_product_releases(self):
        # The 2026-11-21 publisher safety-only merge unexpectedly triggered
        # both live writers; those writes do not validate publisher code.
        for path in (
            "scripts/wp_publish.py", "tests/test_publisher.py",
            ".github/workflows/xfit-creatine-live.yml",
            ".github/workflows/xfit-whey-live.yml",
        ):
            with self.subTest(file=path):
                self.assertEqual(expected_releases({path}, self.sources), set())

        mobile = Path(".github/workflows/xfit-mobile-qa.yml").read_text(encoding="utf-8")
        watched = set(workflow_push_paths(mobile))
        for file in (
            "scripts/wp_publish.py", "tests/test_publisher.py",
            ".github/workflows/xfit-creatine-live.yml",
            ".github/workflows/xfit-whey-live.yml",
        ):
            self.assertNotIn(file, watched)

        # Daily scheduled feed updates and manual dispatch remain untouched.
        for source in self.sources.values():
            self.assertIn("  schedule:", source)
            self.assertIn("  workflow_dispatch:", source)
            self.assertIn("scripts/xfit_feed_ingest.py", workflow_push_paths(source))

    def test_mobile_qa_watches_all_release_inputs(self):
        mobile = Path(".github/workflows/xfit-mobile-qa.yml").read_text(encoding="utf-8")
        watched = set(workflow_push_paths(mobile))
        for source in self.sources.values():
            self.assertTrue(set(workflow_push_paths(source)) <= watched,
                            "Mobile QA must trigger for all files that can publish advisers")
        self.assertIn("actions: read", mobile)
        self.assertIn("scripts.xfit_release_gate", mobile)

    def test_good_expected_runs_are_exact_commit_successes(self):
        good = [dict(name=name, status="completed", conclusion="success",
                     event="push", head_sha=self.sha, id=i)
                for i, name in enumerate(LIVE_WORKFLOWS, 1)]
        self.assertTrue(check_release_runs(set(LIVE_WORKFLOWS), good, self.sha))
        self.assertFalse(check_release_runs(set(LIVE_WORKFLOWS), good[:1], self.sha))
        self.assertFalse(check_release_runs(set(LIVE_WORKFLOWS),
                                            [dict(good[0], status="in_progress"), good[1]], self.sha))
        self.assertFalse(check_release_runs(set(LIVE_WORKFLOWS),
                                            [dict(good[0], head_sha="b" * 40), good[1]], self.sha))
        with self.assertRaises(ReleaseGateError):
            check_release_runs(set(LIVE_WORKFLOWS),
                               [dict(good[0], conclusion="failure"), good[1]], self.sha)
        with self.assertRaises(ReleaseGateError):
            check_release_runs(set(LIVE_WORKFLOWS),
                               [dict(good[0], conclusion="skipped"), good[1]], self.sha)

    def test_polling_waits_for_completion_and_fails_closed_on_timeout(self):
        name = "XFIT Whey Advisor Live"
        run = dict(name=name, status="completed", conclusion="success",
                   event="push", head_sha=self.sha, id=11)
        with patch("scripts.xfit_release_gate.github_json", side_effect=[
            {"workflow_runs": []}, {"workflow_runs": [run]}]) as fetch, \
             patch("scripts.xfit_release_gate.time.sleep"):
            wait_for_releases({name}, sha=self.sha, repo="owner/repo", token="fake",
                              timeout_seconds=10, interval_seconds=1)
            self.assertEqual(fetch.call_count, 2)
        with patch("scripts.xfit_release_gate.github_json", return_value={"workflow_runs": []}), \
             patch("scripts.xfit_release_gate.time.monotonic", side_effect=[0, 3]), \
             patch("scripts.xfit_release_gate.time.sleep"):
            with self.assertRaises(ReleaseGateError):
                wait_for_releases({name}, sha=self.sha, repo="owner/repo", token="fake",
                                  timeout_seconds=1, interval_seconds=1)


if __name__ == "__main__":
    unittest.main()
