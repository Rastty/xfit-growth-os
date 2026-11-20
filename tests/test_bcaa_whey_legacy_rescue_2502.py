"""Fail-closed one-post migration; never infer WordPress deployment from tests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.wp_publish import PublishError
from scripts import xfit_bcaa_whey_legacy_rescue_2502 as r


def legacy():
    return ("<h2>BCAA vs. whey</h2><p>" + "hlavní rozsáhlý historický text " * 180
            + "</p><p>What are BCAAs and whey protein?</p>"
            + "<p>BCAA zvyšují anabolické hormony</p>"
            + "<p>ketleiové aminokyseliny</p>"
            + "".join('<p><a href="https://example.test/promo">slevový kód: 5NM2022</a></p>'
                      for _ in range(3)))


def post(body=None, *, post_id=r.POST_ID, slug=r.SLUG, status="publish",
         url=r.URL, modified="2023-04-16T12:00:00", title=r.TITLE, rendered=False):
    return {"id": post_id, "slug": slug, "status": status, "link": url,
            "modified_gmt": modified, "title": {"raw": title},
            "content": {"rendered" if rendered else "raw": legacy() if body is None else body}}


class BcaaWheyLegacyTests(unittest.TestCase):
    def test_editorial_quality_sources_and_safe_routes(self):
        body = r.revision()
        self.assertIn("Nekupujte ani BCAA", body)
        self.assertIn("22,5 g bílkovin", body)
        self.assertEqual(body.count(r.MARK), 1)
        self.assertEqual(body.count("min-height:48px"), 3)
        for destination in r.TARGETS:
            self.assertIn('href="' + destination + '"', body)
        for source in r.SOURCE_LINKS:
            self.assertIn(source, body)
        for term in ("5NM2022", "anabolické hormony\"", "<script", "onclick=", "nejlevnější na trhu"):
            self.assertNotIn(term, body)

    def test_reviewed_legacy_single_post_is_eligible(self):
        state = r.classify(post())
        self.assertEqual(state["mode"], "update")
        self.assertNotEqual(state["raw_sha"], state["after_sha"])
        # Actual public source includes the extra word "také".
        self.assertEqual(r.classify(post(legacy().replace(
            "BCAA zvyšují anabolické hormony", "BCAA také zvyšují anabolické hormony")))[
                "mode"], "update")

    def test_only_exact_post_permitted(self):
        for invalid in (
            {"post_id": 2503}, {"slug": "bcaa-vs-whey"},
            {"url": "https://evil.test/" + r.SLUG + "/"},
            {"url": r.URL + "?refer=1"}, {"status": "draft"},
            {"title": "BCAA reklamní článek"}, {"modified": ""},
            {"body": legacy().replace("5NM2022", "nový-kód", 1)},
            {"body": legacy().replace("ketleiové aminokyseliny", "nová redakce")},
            {"body": legacy() + r.MARK},
        ):
            with self.subTest(invalid=list(invalid)):
                with self.assertRaises(PublishError):
                    r.classify(post(**invalid))

    def test_source_change_or_smaller_body_fails(self):
        self.assertFalse(r.old_source("5NM2022" * 3))
        self.assertFalse(r.old_source(legacy().replace("BCAA zvyšují anabolické hormony", "podloženo")))
        self.assertFalse(r.old_source(legacy() + "5NM2022"))
        with patch.object(r, "SOURCE", Path("/nonexistent")):
            with self.assertRaises(OSError):
                r.revision()

    def test_already_rewritten_body_is_no_write(self):
        done = post(r.revision(), modified="2026-11-20T12:00:00")
        self.assertEqual(r.classify(done)["mode"], "already_applied")
        with tempfile.TemporaryDirectory() as temp, patch.object(
                r, "BACKUP", Path(temp) / "old.json"), \
                patch.object(r, "remote", return_value=done), \
                patch.object(r, "verify_public", return_value=True), \
                patch.object(r, "wp_request") as write:
            r.snapshot()
            r.apply()
            write.assert_not_called()

    def test_public_fingerprint_guard_and_final_public_proof(self):
        with patch.object(r, "public_rest", return_value=post(legacy(), rendered=True)), \
                patch.object(r, "public_page", return_value="<h1>Článek</h1>" + legacy()):
            self.assertTrue(r.public_old_fingerprint()["rendered_sha"])
        with patch.object(r, "public_rest", return_value=post(r.revision(), rendered=True)), \
                patch.object(r, "public_page", return_value="<h1>Článek</h1>" + r.revision()):
            self.assertTrue(r.verify_public())
        with patch.object(r, "public_rest", return_value=post(r.revision(), rendered=True)), \
                patch.object(r, "public_page", return_value="<h1>Článek</h1>" + r.revision() + "5NM2022"), \
                patch.object(r.time, "sleep"):
            self.assertFalse(r.verify_public())

    def test_rollback_artifact_before_single_post_and_readbacks(self):
        before = post()
        after = post(r.revision(), modified="2026-11-20T14:00:00")
        snapshot = {"rendered_sha": r.sha(legacy()), "modified_gmt": before["modified_gmt"]}
        with tempfile.TemporaryDirectory() as temp, patch.object(
                r, "BACKUP", Path(temp) / "original.json"), \
                patch.object(r, "public_old_fingerprint", return_value=snapshot):
            with patch.object(r, "remote", return_value=before):
                r.snapshot()
            backup = json.loads(r.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(backup["original_authenticated_post"], before)
            self.assertEqual(backup["remote_writes"], 0)
            with patch.object(r, "remote", side_effect=[before, after]), \
                    patch.object(r, "wp_request", return_value={"id": r.POST_ID}) as write, \
                    patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
                    patch.object(r, "verify_public", return_value=True):
                r.apply()
            write.assert_called_once_with(
                "https://xfit.cz", "posts/2502", payload={"content": r.revision()})

    def test_concurrent_edit_cannot_be_overwritten(self):
        before = post()
        snapshot = {"rendered_sha": r.sha(legacy()), "modified_gmt": before["modified_gmt"]}
        with tempfile.TemporaryDirectory() as temp, patch.object(
                r, "BACKUP", Path(temp) / "original.json"), \
                patch.object(r, "public_old_fingerprint", return_value=snapshot):
            with patch.object(r, "remote", return_value=before):
                r.snapshot()
            changed = post(modified="2026-11-20T13:21:00")
            with patch.object(r, "remote", return_value=changed), \
                    patch.object(r, "wp_request") as write:
                with self.assertRaises(PublishError):
                    r.apply()
            write.assert_not_called()

    def test_ambiguous_http_failure_never_retries_wordpress_post(self):
        before = post()
        after = post(r.revision())
        snapshot = {"rendered_sha": r.sha(legacy()), "modified_gmt": before["modified_gmt"]}
        with tempfile.TemporaryDirectory() as temp, patch.object(
                r, "BACKUP", Path(temp) / "original.json"), \
                patch.object(r, "public_old_fingerprint", return_value=snapshot):
            with patch.object(r, "remote", return_value=before):
                r.snapshot()
            with patch.object(r, "remote", side_effect=[before, after]), \
                    patch.object(r, "wp_request", side_effect=PublishError("timeout")) as write, \
                    patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
                    patch.object(r, "verify_public", return_value=True):
                r.apply()
            self.assertEqual(write.call_count, 1)

    def test_backup_immutable_and_public_drift_blocks_release(self):
        before = post()
        snapshot = {"rendered_sha": r.sha(legacy()), "modified_gmt": before["modified_gmt"]}
        with tempfile.TemporaryDirectory() as temp, patch.object(
                r, "BACKUP", Path(temp) / "original.json"), \
                patch.object(r, "public_old_fingerprint", side_effect=[snapshot, {"rendered_sha": "drift"}]), \
                patch.object(r, "remote", return_value=before), \
                patch.object(r, "wp_request") as write:
            r.snapshot()
            with self.assertRaises(PublishError):
                r.snapshot()
            with self.assertRaises(PublishError):
                r.apply()
            write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
