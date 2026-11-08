"""Owner status must describe ACTUAL open Codex PRs, not issue assignee guesses."""
import unittest
from unittest.mock import patch

from scripts.xfit_status import (
    CODEX_BRANCH, EXPECTED_REPO, github_lanes, github_open_agent_prs,
)


def pr(n, lane, *, repo=EXPECTED_REPO, ref=None, state="open"):
    return {
        "number": n, "state": state,
        "head": {
            "repo": {"full_name": repo},
            "ref": ref or "xfit/codex-" + lane + "-42458902572-1",
        },
    }


def fake_get(url, token):
    if "/pulls?state=open" in url:
        return [
            pr(63, "editor"), pr(60, "revenue"),
            pr(999, "editor", repo="other/project"),
            pr(1001, "ux", ref="xfit/codex-ux-malicious"),
        ]
    for number in (2, 3, 4, 5):
        if url.endswith("/issues/" + str(number)):
            return {
                "number":number,
                "assignees":[],
                "html_url":"https://github.com/" + EXPECTED_REPO +
                           "/issues/" + str(number),
            }
    raise AssertionError("Unexpected status API: " + url)


class StatusLanesTests(unittest.TestCase):
    def test_only_actual_reviewable_codex_prs_are_reported(self):
        with patch("scripts.xfit_status.get_json", side_effect=fake_get):
            lanes=github_lanes("fake-token")
        by_id={x[0]:x for x in lanes}
        self.assertEqual(len(lanes), 4)
        self.assertIn("PR #63",by_id[4][2])
        self.assertIn("PR #60",by_id[5][2])
        self.assertIn("ještě nepublikováno",by_id[4][2])
        self.assertIn("bez otevřeného Codex PR",by_id[2][2])
        self.assertIn("bez otevřeného Codex PR",by_id[3][2])
        self.assertNotIn("PR #999",str(lanes))
        self.assertNotIn("PR #1001",str(lanes))
        self.assertNotIn("žádný AI agent není přiřazen",str(lanes))

    def test_open_only_and_stable_safe_link(self):
        with patch("scripts.xfit_status.get_json", side_effect=fake_get):
            found=github_open_agent_prs("fake-token")
        self.assertEqual(found, {
            "ux":[], "archive":[], "editor":[63], "revenue":[60],
        })
        self.assertEqual(
            CODEX_BRANCH.fullmatch("xfit/codex-ux-42458902572-1").group(1),
            "ux",
        )
        self.assertIsNone(CODEX_BRANCH.fullmatch(
            "xfit/codex-revenue-42458902572-1-other"))

    def test_expired_or_inaccessible_pr_listing_is_unknown_not_empty(self):
        for returned in (None, {}, [pr(10+i,"ux") for i in range(100)]):
            with self.subTest(count=len(returned) if isinstance(returned,list) else "invalid"):
                with patch("scripts.xfit_status.get_json", return_value=returned):
                    self.assertIsNone(github_open_agent_prs("fake-token"))
        with patch("scripts.xfit_status.get_json", side_effect=lambda url,token:
                   None if "/pulls?" in url else {
                       "html_url":"https://github.com/" + EXPECTED_REPO +
                                  "/issues/" + url.rsplit("/",1)[-1]}):
            lanes=github_lanes("fake-token")
        self.assertEqual(len(lanes),4)
        self.assertTrue(all("NEOVĚŘENO" in row[2] for row in lanes))

    def test_status_workflow_has_pr_read_only_not_new_wordpress_permission(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parents[1]/
                ".github/workflows/xfit-status.yml").read_text(encoding="utf-8")
        self.assertIn("  pull-requests: read",source)
        self.assertIn("  issues: write",source)
        self.assertNotIn("secrets.WP_APP_PASSWORD",source)
        self.assertIn("tests.test_status_lanes",source)


if __name__=="__main__":
    unittest.main()
