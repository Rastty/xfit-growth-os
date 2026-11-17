"""Exact article identity, prewrite backup and postoperative editorial safety."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.wp_publish import PublishError
from scripts import xfit_pilates_after_surgery_5929 as r


OLD = (
    "<h2>Jak pilates pro záda může pomoci při rehabilitaci</h2>"
    "<p>Pilates pro záda je skvělou volbou. Nenechte se omezovat bolestivými zády. "
    "S naším Pilates instruktorem vás provedeme cviky. "
    "Ihned vyzkoušejte Plank Superman Bridge po operaci.</p>" * 14
)
MODIFIED = "2023-05-08T07:44:01"


def post(body=OLD, modified=MODIFIED, **overrides):
    item = {"id": r.POST_ID, "slug": r.SLUG, "status": "publish",
            "link": r.URL, "modified_gmt": modified,
            "content": {"raw": body}}
    item.update(overrides)
    return item


class Pilates5929Tests(unittest.TestCase):
    def test_revision_is_useful_and_does_not_prescribe_rehabilitation(self):
        body = r.new_body()
        self.assertTrue(r.clean_revision(body))
        for marker in ("nezačínejte podle obecného internetového návodu",
                       "skupinovou lekci odložit", "155 nebo 112",
                       "Cambridge University Hospitals", "NICE"):
            self.assertIn(marker, body)
        self.assertNotIn("TOP KETO", body)
        self.assertNotIn("<script", body)

    def test_only_exact_legacy_post_is_eligible(self):
        with patch.object(r, "get_post", return_value=post()):
            self.assertEqual(r.old_body(), (OLD, MODIFIED))
        cases = [post(id=42), post(slug="other"), post(status="draft"),
                 post(link="https://xfit.cz/"), post(modified="today"),
                 post(body="<p>Jiný aktualizovaný text</p>" * 65)]
        for bad in cases:
            with self.subTest(bad=bad.get("slug")):
                with patch.object(r, "get_post", return_value=bad):
                    with self.assertRaises(PublishError):
                        r.old_body()

    def test_original_body_is_saved_completely_before_any_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(r, "BACKUP", Path(tmp) / "saved.json"), \
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

    def test_one_content_only_post_and_public_verification(self):
        body = r.new_body()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(r, "BACKUP", Path(tmp) / "saved.json"), \
                 patch.object(r, "get_post", side_effect=[post(), post(), post(body)]), \
                 patch.object(r, "wp_request", return_value={"id": 5929}) as writer, \
                 patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(r, "public_verified", return_value=True) as readback:
                r.snapshot()
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    r.deploy()
                self.assertIn("PUBLIC_VERIFIED", output.getvalue())
                writer.assert_called_once_with("https://xfit.cz", "posts/5929",
                                               payload={"content": body})
                readback.assert_called_once()

    def test_source_changed_since_backup_never_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(r, "BACKUP", Path(tmp) / "saved.json"), \
                 patch.object(r, "get_post", side_effect=[post(), post(modified="2026-11-17T14:00:00")]), \
                 patch.object(r, "wp_request") as writer:
                r.snapshot()
                with self.assertRaises(PublishError):
                    r.deploy()
                writer.assert_not_called()

    def test_ambiguous_write_is_reconciled_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(r, "BACKUP", Path(tmp) / "saved.json"), \
                 patch.object(r, "get_post", side_effect=[post(), post(), post(r.new_body())]), \
                 patch.object(r, "wp_request", side_effect=PublishError("timeout")) as writer, \
                 patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(r, "public_verified", return_value=True):
                r.snapshot()
                r.deploy()
                self.assertEqual(writer.call_count, 1)

    def test_original_content_readback_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(r, "BACKUP", Path(tmp) / "saved.json"), \
                 patch.object(r, "get_post", side_effect=[post(), post(), post()]), \
                 patch.object(r, "wp_request", return_value={"id": 5929}) as writer, \
                 patch.object(r, "normalized_base", return_value="https://xfit.cz"):
                r.snapshot()
                with self.assertRaises(PublishError):
                    r.deploy()
                self.assertEqual(writer.call_count, 1)

    def test_verify_only_does_not_write(self):
        with patch.object(r, "get_post", return_value=post(r.new_body())), \
             patch.object(r, "wp_request") as writer, \
             patch.object(r, "public_verified", return_value=True):
            r.verify_only()
            writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
