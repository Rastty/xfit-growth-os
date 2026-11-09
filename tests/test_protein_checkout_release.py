"""Guards for one exact protein checkout editorial update and rollback."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.wp_publish import MARKER, PublishError
from scripts import xfit_protein_checkout_release as release


def old_html():
    src=json.loads(release.SOURCE.read_text(encoding="utf-8"))
    return MARKER+"\n"+src["content"]


def post(body=None, *, modified="2026-11-09T18:00:00", slug=release.SLUG,
         status="publish", link=release.URL, post_id=release.POST_ID):
    return {
        "id":post_id,"slug":slug,"status":status,"link":link,
        "content":{"raw":body if body is not None else old_html()},
        "modified_gmt":modified,
    }


class ProteinCheckoutLiveReleaseTests(unittest.TestCase):
    def test_reviewed_source_sha_exact_and_copy_has_no_commercial_links(self):
        rev=release.reviewed_revision()
        self.assertEqual(rev["wp_post_id"],25451)
        self.assertIn("včetně dopravy a povinných poplatků",rev["replacement"])
        self.assertEqual(rev["replacement"].count("<p>"),2)
        self.assertNotIn("<a ",rev["replacement"])
        self.assertNotIn(" Kč",rev["replacement"])

    def test_real_source_copy_reversible_and_preserves_links_and_headers(self):
        rev=release.reviewed_revision()
        result=release.prepare(post(),rev)
        self.assertEqual(result["mode"],"update")
        self.assertTrue(result["after"].startswith(MARKER))
        self.assertEqual(result["after"].count(rev["replacement"]),1)
        self.assertEqual(result["after"].replace(rev["replacement"],
                          rev["original"],1),result["before"])

    def test_idempotent_if_live_contains_exact_reviewed_copy(self):
        rev=release.reviewed_revision()
        after=release.prepare(post(),rev)["after"]
        done=release.prepare(post(after),rev)
        self.assertEqual(done["mode"],"already_applied")
        self.assertEqual(done["after"],after)

    def test_any_unreviewed_identity_or_formula_drift_is_rejected(self):
        rev=release.reviewed_revision()
        base=old_html()
        for args in (
            {"post_id":25455}, {"slug":"not-protein-guide"},
            {"status":"draft"}, {"link":"https://other.example/"+release.SLUG+"/"},
            {"link":release.URL+"?campaign=unknown"},
            {"body":base.replace(MARKER,"")},
            {"body":base.replace(rev["original"],"<p>Different content</p>")},
            {"body":base.replace(rev["original"],rev["original"]*2)},
            {"modified":""},
        ):
            with self.subTest(args=str(args)[:75]):
                with self.assertRaises(PublishError):
                    release.prepare(post(**args),rev)

    def test_public_check_requires_all_actual_unique_checkout_cautions(self):
        rev=release.reviewed_revision()
        self.assertTrue(release.verify_public(reader=lambda _:rev["replacement"]))
        for phrase in release.PUBLIC_MARKERS:
            changed=rev["replacement"].replace(phrase,"Different copy")
            self.assertFalse(release.verify_public(reader=lambda _:changed))

    def test_backup_before_single_post_with_api_and_public_verification(self):
        rev=release.reviewed_revision()
        original=post()
        changed=post(release.prepare(original,rev)["after"],
                     modified="2026-11-09T18:10:00")
        with tempfile.TemporaryDirectory() as root, patch.object(
                release,"BACKUP",Path(root)/"snapshot.json"):
            with patch.object(release,"read_post",return_value=original):
                release.snapshot()
            saved=json.loads(release.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(saved["original_raw"],original["content"]["raw"])
            self.assertEqual(saved["remote_writes"],0)
            self.assertEqual(saved["expected_sha"],release.digest(changed["content"]["raw"]))
            with patch.object(release,"read_post",side_effect=[original,changed]), \
                 patch.object(release,"normalized_base",return_value="https://xfit.cz"), \
                 patch.object(release,"wp_request",return_value={
                     "id":release.POST_ID,"status":"publish"}) as writer, \
                 patch.object(release,"verify_public",return_value=True) as verified:
                release.apply()
            writer.assert_called_once_with(
                "https://xfit.cz","posts/25451",
                payload={"content":changed["content"]["raw"]})
            verified.assert_called_once_with()

    def test_changed_wp_source_after_backup_blocks_all_writes(self):
        original=post()
        drift=post(body=old_html()+"<p>Editor added new information</p>")
        with tempfile.TemporaryDirectory() as root, patch.object(
                release,"BACKUP",Path(root)/"snapshot.json"):
            with patch.object(release,"read_post",return_value=original):
                release.snapshot()
            with patch.object(release,"read_post",return_value=drift), \
                 patch.object(release,"wp_request") as writer:
                with self.assertRaises(PublishError):
                    release.apply()
            writer.assert_not_called()

    def test_ambiguous_post_error_reconciled_once_without_retry(self):
        rev=release.reviewed_revision()
        original=post()
        changed=post(release.prepare(original,rev)["after"])
        with tempfile.TemporaryDirectory() as root, patch.object(
                release,"BACKUP",Path(root)/"snapshot.json"):
            with patch.object(release,"read_post",return_value=original):
                release.snapshot()
            with patch.object(release,"read_post",side_effect=[original,changed]), \
                 patch.object(release,"normalized_base",return_value="https://xfit.cz"), \
                 patch.object(release,"wp_request",side_effect=PublishError(
                     "POST timed out")) as writer, \
                 patch.object(release,"verify_public",return_value=True):
                release.apply()
            self.assertEqual(writer.call_count,1)

    def test_already_applied_never_posts(self):
        rev=release.reviewed_revision()
        changed=post(release.prepare(post(),rev)["after"])
        with tempfile.TemporaryDirectory() as root, patch.object(
                release,"BACKUP",Path(root)/"snapshot.json"):
            with patch.object(release,"read_post",return_value=changed):
                release.snapshot()
            with patch.object(release,"read_post",return_value=changed), \
                 patch.object(release,"wp_request") as writer, \
                 patch.object(release,"verify_public",return_value=True):
                release.apply()
            writer.assert_not_called()


if __name__=="__main__":
    unittest.main()
