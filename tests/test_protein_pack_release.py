"""Release tests: preserve published WP body, change only one verified paragraph."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.wp_publish import MARKER, PublishError
from scripts import xfit_protein_pack_release as pack


def live_body():
    ready=json.loads(Path("content/ready/xfit-os-protein-guide.json").read_text(encoding="utf-8"))
    return MARKER + "\n" + ready["content"] + "\n<section><h2>Schválené doplnění</h2>" + (
        "<p>Důležité upozornění pro čtenáře: prášek není nutný při "
        "dostatečném příjmu bílkovin z běžné stravy.</p></section>"
    )


def wp(raw, *, status="publish", modified="2026-11-08T07:45:00", slug=pack.SLUG,
       link=pack.PUBLIC_URL):
    return {"id": pack.POST_ID, "slug": slug, "status": status,
            "link": link, "modified_gmt": modified,
            "content": {"raw": raw}}


class ProteinPackReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rev=pack.revision()
        cls.old=live_body()
        cls.new=cls.old.replace(cls.rev["original"],cls.rev["replacement"],1)

    def test_revision_preview_has_exact_replacement_and_no_clinical_claim(self):
        self.assertEqual(self.old.count(self.rev["original"]),1)
        self.assertEqual(self.new.count(self.rev["replacement"]),1)
        self.assertNotIn(self.rev["original"],self.new)
        self.assertIn("20 týdnů",self.new)
        self.assertIn("Nejde o doporučenou dávku",self.new)
        self.assertEqual(self.new.replace(
            self.rev["replacement"],self.rev["original"],1),self.old)
        self.assertEqual(pack.inspect(wp(self.old),self.rev)["after"],self.new)

    def test_snapshot_before_any_write_and_one_exact_post(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(pack,"BACKUP",Path(d)/"backup.json"), \
                 patch.object(pack,"post",side_effect=[
                     wp(self.old),wp(self.old),wp(self.new)]), \
                 patch.object(pack,"normalized_base",return_value="https://xfit.cz"), \
                 patch.object(pack,"wp_request",return_value={
                     "id":pack.POST_ID,"status":"publish"}) as writer, \
                 patch.object(pack,"public_verified",return_value=True) as reader:
                pack.snapshot()
                saved=json.loads(pack.BACKUP.read_text(encoding="utf-8"))
                self.assertEqual(saved["original_raw"],self.old)
                self.assertEqual(saved["remote_writes"],0)
                self.assertEqual(saved["expected_hash"],pack.digest(self.new))
                pack.apply()
                writer.assert_called_once_with(
                    "https://xfit.cz","posts/"+str(pack.POST_ID),
                    payload={"content":self.new})
                reader.assert_called_once_with()
                self.assertTrue(pack.BACKUP.exists())

    def test_explicit_post_timeout_reconciles_without_retry(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(pack,"BACKUP",Path(d)/"rollback.json"), \
                 patch.object(pack,"post",side_effect=[
                     wp(self.old),wp(self.old),wp(self.new)]), \
                 patch.object(pack,"normalized_base",return_value="https://xfit.cz"), \
                 patch.object(pack,"wp_request",
                              side_effect=PublishError("POST timed out")) as writer, \
                 patch.object(pack,"public_verified",return_value=True):
                pack.snapshot()
                pack.apply()
                self.assertEqual(writer.call_count,1)

    def test_drift_after_backup_means_no_post(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(pack,"BACKUP",Path(d)/"rollback.json"), \
                 patch.object(pack,"post",side_effect=[
                     wp(self.old),wp(self.old,modified="2026-11-08T07:45:01")]), \
                 patch.object(pack,"wp_request") as writer:
                pack.snapshot()
                with self.assertRaises(PublishError):
                    pack.apply()
                writer.assert_not_called()

    def test_after_failed_post_unchanged_remains_failure(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(pack,"BACKUP",Path(d)/"rollback.json"), \
                 patch.object(pack,"post",side_effect=[
                     wp(self.old),wp(self.old),wp(self.old)]), \
                 patch.object(pack,"normalized_base",return_value="https://xfit.cz"), \
                 patch.object(pack,"wp_request",
                              side_effect=PublishError("HTTP 503")) as writer:
                pack.snapshot()
                with self.assertRaises(PublishError):
                    pack.apply()
                self.assertEqual(writer.call_count,1)

    def test_already_applied_has_zero_write_and_public_proof(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(pack,"BACKUP",Path(d)/"rollback.json"), \
                 patch.object(pack,"post",return_value=wp(self.new)), \
                 patch.object(pack,"wp_request") as writer, \
                 patch.object(pack,"public_verified",return_value=True):
                pack.snapshot()
                pack.apply()
                writer.assert_not_called()

    def test_strict_identity_marker_and_original_phrase(self):
        for bad in (
            wp(self.old,status="draft"),
            wp(self.old,slug="other-slug"),
            wp(self.old,link="https://other.example/"+pack.SLUG+"/"),
            wp(self.old,link=pack.PUBLIC_URL+"?tracking=bad"),
            wp(self.old.replace(MARKER,"")),
            wp(self.old.replace(self.rev["original"],"A changed phrase")),
            wp(self.old.replace(self.rev["original"],self.rev["original"]*2)),
        ):
            with self.subTest(status=bad["status"],link=bad["link"]):
                with self.assertRaises(PublishError):
                    pack.inspect(bad,self.rev)

    def test_public_verification_requires_visible_specific_advice(self):
        good=('<article><li>Koupit velké balení jen kvůli nižší '
              'jednotkové ceně. 1 000 g / 25 g = 40 porcí. '
              'Při dvou použitích týdně vystačí na 20 týdnů. '
              'Protein nemusíte kupovat.</li></article>')
        self.assertTrue(pack.public_verified(reader=lambda _:good))
        self.assertFalse(pack.public_verified(reader=lambda _:
            '<article><li>Obecná reklama na protein.</li></article>'))
        self.assertFalse(pack.public_verified(reader=lambda _:
            good+'<li>Nakoupit obří balení neznámé příchutě</li>'))


if __name__ == "__main__":
    unittest.main()
