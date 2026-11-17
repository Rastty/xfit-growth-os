"""Exact-one-post safety tests for correcting the indexed creatine advice."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.wp_publish import PublishError
from scripts import xfit_creatine_beginners_7468 as r


OLD = ("<h2>Kreatin pro začátečníky v fitness</h2>"
       "<p>Začněte s 20-30g, potom 5-10g."
       "Užívejte 30 minut před tréninkem; pauza po 8 týdnů.</p>" * 12)
MODIFIED = "2023-05-15T08:23:01"


def post(body=OLD, modified=MODIFIED, **overrides):
    value = {"id": r.POST_ID, "slug": r.SLUG, "status": "publish",
             "link": r.URL, "modified_gmt": modified, "content": {"raw": body}}
    value.update(overrides)
    return value


class LegacyCreatine7468Tests(unittest.TestCase):
    def test_revision_fixes_conflicting_claims_and_passes_editorial_gate(self):
        body = r.new_body()
        self.assertTrue(r.clean_revision(body))
        self.assertIn("není povinnost", body)
        self.assertIn("Je v pořádku nekupovat nic", body)
        self.assertIn("kreatinu monohydrátu", body)
        self.assertNotIn("20-30g", body)
        self.assertNotIn("5-10g", body)
        self.assertNotIn("<script", body)
        self.assertNotIn("namaximum.cz", body)

    def test_pinned_identity_and_original_misinformation_must_both_match(self):
        self.assertEqual(r.legacy(post()), (OLD, MODIFIED))
        for bad in (
            post(id=123), post(slug="another"), post(status="draft"),
            post(link="https://xfit.cz/"), post(modified="today"),
            post(body="<p>new concise guidance</p>" * 70),
        ):
            with self.subTest(bad=str(bad.get("id"))):
                with self.assertRaises(PublishError):
                    r.legacy(bad)

    def test_snapshot_contains_complete_rollback_without_any_write(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(r, "BACKUP", Path(directory) / "before.json"), \
                 patch.object(r, "get_post", return_value=post()), \
                 patch.object(r, "wp_request") as writer:
                r.snapshot()
                saved = json.loads(r.BACKUP.read_text(encoding="utf-8"))
                self.assertEqual(saved["original_raw"], OLD)
                self.assertEqual(saved["modified_gmt"], MODIFIED)
                self.assertEqual(saved["remote_writes"], 0)
                writer.assert_not_called()
                with self.assertRaises(PublishError):
                    r.snapshot()

    def test_single_post_only_after_unchanged_source_and_backup(self):
        body = r.new_body()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(r, "BACKUP", Path(directory) / "before.json"), \
                 patch.object(r, "get_post", side_effect=[post(), post(), post(body)]), \
                 patch.object(r, "wp_request", return_value={"id": 7468}) as writer, \
                 patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(r, "public_verified", return_value=True) as public:
                r.snapshot()
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    r.deploy()
                self.assertIn("PUBLIC_VERIFIED", output.getvalue())
                writer.assert_called_once_with("https://xfit.cz", "posts/7468", payload={"content": body})
                public.assert_called_once()

    def test_post_snapshot_drift_aborts_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(r, "BACKUP", Path(directory) / "before.json"), \
                 patch.object(r, "get_post", side_effect=[post(), post(modified="2026-11-17T10:00:00")]), \
                 patch.object(r, "wp_request") as writer:
                r.snapshot()
                with self.assertRaises(PublishError):
                    r.deploy()
                writer.assert_not_called()

    def test_ambiguous_post_reconciles_once_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(r, "BACKUP", Path(directory) / "before.json"), \
                 patch.object(r, "get_post", side_effect=[post(), post(), post(r.new_body())]), \
                 patch.object(r, "wp_request", side_effect=PublishError("timeout")) as writer, \
                 patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(r, "public_verified", return_value=True):
                r.snapshot()
                r.deploy()
                self.assertEqual(writer.call_count, 1)

    def test_unchanged_readback_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(r, "BACKUP", Path(directory) / "before.json"), \
                 patch.object(r, "get_post", side_effect=[post(), post(), post()]), \
                 patch.object(r, "wp_request", return_value={"id": 7468}) as writer, \
                 patch.object(r, "normalized_base", return_value="https://xfit.cz"):
                r.snapshot()
                with self.assertRaises(PublishError):
                    r.deploy()
                self.assertEqual(writer.call_count, 1)

    def test_readonly_reconciliation_has_no_post(self):
        with patch.object(r, "get_post", return_value=post(r.new_body())), \
             patch.object(r, "wp_request") as writer, \
             patch.object(r, "public_verified", return_value=True) as public:
            r.verify_only()
            writer.assert_not_called()
            public.assert_called_once()


if __name__ == "__main__":
    unittest.main()
