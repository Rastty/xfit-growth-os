"""One-post first-screen choice insert: review, recovery and readback guards."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.wp_publish import MARKER, PublishError
from scripts import xfit_protein_early_choices_release as release


def original_body():
    source = json.loads(release.SOURCE.read_text(encoding="utf-8"))
    return MARKER + "\n" + source["content"]


def post(raw=None, *, post_id=release.POST_ID, slug=release.SLUG,
         status="publish", link=release.URL,
         modified="2026-11-20T14:00:00"):
    return {"id": post_id, "slug": slug, "status": status, "link": link,
            "content": {"raw": original_body() if raw is None else raw},
            "modified_gmt": modified}


class ProteinEarlyChoicesTests(unittest.TestCase):
    def test_three_exact_whitelisted_first_party_routes_and_no_product_claims(self):
        nav = release.panel()
        self.assertEqual(nav.count(release.MARK), 1)
        self.assertEqual(nav.count("<li "), 3)
        self.assertEqual(nav.count("min-height:48px"), 3)
        self.assertEqual(len(release.TARGETS), 3)
        for destination in release.TARGETS:
            self.assertEqual(nav.count('href="' + destination + '"'), 1)
        for dangerous in ('<script', 'onclick=', '<iframe', 'data-product-id=',
                          'a_aid=', ' Kč', 'nejlevnější na trhu'):
            self.assertNotIn(dangerous, nav)
        self.assertIn("Proteinový prášek není povinný", nav)
        self.assertIn("jednoho prodejce", nav)

    def test_exact_intro_and_preservation_of_all_existing_content(self):
        source = original_body()
        state = release.prepare(post())
        self.assertEqual(state["mode"], "update")
        self.assertEqual(state["after"].count(release.MARK), 1)
        self.assertEqual(state["after"].replace(
            release.intro() + "\n" + release.panel(),
            release.intro(), 1), source)
        self.assertLess(state["after"].index(release.MARK),
                        state["after"].index("Rychlá volba: který typ"))

    def test_existing_later_edits_are_preserved_byte_for_byte(self):
        prior = original_body() + '\n<p data-later-editor="true">New reviewed content</p>'
        state = release.prepare(post(prior))
        self.assertTrue(state["after"].endswith(
            '<p data-later-editor="true">New reviewed content</p>'))
        self.assertEqual(state["after"].replace(
            release.intro() + "\n" + release.panel(),
            release.intro(), 1), prior)

    def test_idempotent_and_partial_panel_fails_closed(self):
        applied = release.prepare(post())["after"]
        self.assertEqual(release.prepare(post(applied))["mode"], "already_applied")
        with self.assertRaises(PublishError):
            release.prepare(post(applied.replace("jednoho prodejce", "jiného prodejce")))

    def test_identity_slug_status_permalink_source_or_modified_drift_rejected(self):
        for change in (
            {"post_id": 25455}, {"slug": "xfit-os-foo"}, {"status": "draft"},
            {"link": "https://xfit.cz/"}, {"link": release.URL + "?bad=1"},
            {"link": "https://evil.test/" + release.SLUG + "/"},
            {"modified": ""},
            {"raw": original_body().replace(MARKER, "", 1)},
            {"raw": original_body().replace(release.intro(), "Changed copy", 1)},
            {"raw": original_body().replace(release.intro(), release.intro() * 2)},
        ):
            with self.subTest(change=str(change)[:70]):
                with self.assertRaises((PublishError, ValueError)):
                    release.prepare(post(**change))

    def test_public_proof_all_three_links_and_early_marker(self):
        good = release.intro() + "\n" + release.panel() + \
            "<h2>Rychlá volba: který typ dává smysl?</h2>"
        self.assertTrue(release.verify_public(reader=lambda _: good))
        for broken in (
            good.replace(release.MARK, "", 1),
            good.replace(release.TARGETS[0], "https://elsewhere.test/"),
            good.replace(release.CHOICES[1][0], "Nesouhlasí", 1),
            good.replace("Rychlá volba: který typ dává smysl?", "Zmizela tabulka"),
            good.replace("Proteinový prášek není povinný", "Kupte každému"),
            good + release.panel(),
        ):
            with self.subTest(broken=broken[:70]):
                self.assertFalse(release.verify_public(reader=lambda _: broken))

    def test_backup_precedes_one_write_and_public_verification(self):
        old = post()
        new = post(release.prepare(old)["after"], modified="2026-11-20T15:01:00")
        with tempfile.TemporaryDirectory() as temp, patch.object(
                release, "BACKUP", Path(temp) / "rollback.json"):
            with patch.object(release, "read_post", return_value=old):
                release.snapshot()
            saved = json.loads(release.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(saved["original_raw"], old["content"]["raw"])
            self.assertEqual(saved["remote_writes"], 0)
            with patch.object(release, "read_post", side_effect=[old, new]), \
                 patch.object(release, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(release, "wp_request", return_value={"id": release.POST_ID}) as write, \
                 patch.object(release, "verify_public", return_value=True) as public:
                release.apply()
            write.assert_called_once_with(
                "https://xfit.cz", "posts/25451",
                payload={"content": new["content"]["raw"]})
            public.assert_called_once_with()

    def test_modified_race_blocks_wordpress_write(self):
        old = post()
        changed = post(modified="2026-11-20T15:00:01")
        with tempfile.TemporaryDirectory() as temp, patch.object(
                release, "BACKUP", Path(temp) / "rollback.json"):
            with patch.object(release, "read_post", return_value=old):
                release.snapshot()
            with patch.object(release, "read_post", return_value=changed), \
                 patch.object(release, "wp_request") as write:
                with self.assertRaises(PublishError):
                    release.apply()
            write.assert_not_called()

    def test_ambiguous_write_is_read_back_but_never_retried(self):
        old = post()
        new = post(release.prepare(old)["after"])
        with tempfile.TemporaryDirectory() as temp, patch.object(
                release, "BACKUP", Path(temp) / "rollback.json"):
            with patch.object(release, "read_post", return_value=old):
                release.snapshot()
            with patch.object(release, "read_post", side_effect=[old, new]), \
                 patch.object(release, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(release, "wp_request", side_effect=PublishError("timeout")) as write, \
                 patch.object(release, "verify_public", return_value=True):
                release.apply()
            self.assertEqual(write.call_count, 1)

    def test_already_published_does_not_write(self):
        done = post(release.prepare(post())["after"])
        with tempfile.TemporaryDirectory() as temp, patch.object(
                release, "BACKUP", Path(temp) / "rollback.json"):
            with patch.object(release, "read_post", return_value=done):
                release.snapshot()
            with patch.object(release, "read_post", return_value=done), \
                 patch.object(release, "wp_request") as write, \
                 patch.object(release, "verify_public", return_value=True):
                release.apply()
            write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
