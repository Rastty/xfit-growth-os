"""Real WP #25451 food-first table release must be counted only with apply proof."""
import json
import unittest

from scripts.xfit_status_evidence import inspect_log, real_release_evidence


NAME = "XFIT Protein Table Opt-out One-post Live Release"
RUN = {"name": NAME, "id": 42859345024, "status": "completed", "conclusion": "success"}
RECEIPT = {
    "state": "PUBLIC_VERIFIED",
    "post_id": 25451,
    "slug": "xfit-os-protein-guide",
    "url": "https://xfit.cz/xfit-os-protein-guide/",
    "posts_changed": 1,
    "post_attempts": 1,
    "new_table_rows_inserted": 1,
    "new_posts": 0,
    "deletes": 0,
    "redirects": 0,
    "public_site_modified": True,
}
APPLY = (
    "2026-11-10T16:55:04Z ##[group]Run set -o pipefail\n"
    "2026-11-10T16:55:04Z python -m scripts.xfit_protein_table_optout_release apply | tee -a \"$GITHUB_STEP_SUMMARY\"\n"
    "2026-11-10T16:55:04Z ##[endgroup]\n"
)


def line(data=RECEIPT):
    return "2026-11-10T16:55:08Z " + json.dumps(data) + "\n"


class TableReleaseEvidenceTests(unittest.TestCase):
    def test_real_apply_after_backup_is_one_verified_update(self):
        log = line() + APPLY + line()
        result = real_release_evidence(
            [RUN], "private-token-is-not-displayed",
            fetch_jobs=lambda *_: {"jobs": [{"id": 1, "conclusion": "success"}]},
            fetch_log=lambda *_: log,
        )
        self.assertEqual(result["counts"]["updated"], 1)
        self.assertEqual(result["counts"]["unique_changed_pages"], 1)
        self.assertEqual(result["verified_events"][0]["url"], RECEIPT["url"])
        self.assertEqual(result["unverified_runs"], [])
        self.assertNotIn("private-token", json.dumps(result))

    def test_synthetic_receipts_and_wrong_ids_are_not_evidence(self):
        for fake in (
            line(),
            APPLY,
            line() + APPLY + line({**RECEIPT, "post_id": 25452}),
            line() + APPLY + line({**RECEIPT, "new_table_rows_inserted": 2}),
            line() + APPLY + line({**RECEIPT, "public_site_modified": False}),
            line() + APPLY + line({**RECEIPT, "posts_changed": 2}),
            line() + APPLY + line({**RECEIPT, "url": "https://xfit.cz/other/"}),
        ):
            with self.subTest(probe=fake[-80:]):
                matches, noop = inspect_log(fake, RUN)
                self.assertEqual(matches, [])
                self.assertFalse(noop)

    def test_verified_repeated_run_noop_not_an_additional_edit(self):
        no_op = (APPLY + line({
            "state": "ALREADY_APPLIED_NO_WRITE",
            "post_id": 25451,
            "post_attempts": 0,
            "public_site_modified": False,
        }))
        found, noop = inspect_log(no_op, RUN)
        self.assertEqual(found, [])
        self.assertTrue(noop)


if __name__ == "__main__":
    unittest.main()
