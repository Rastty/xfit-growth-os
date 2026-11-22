"""One existing beginner-hub link; preserve choices, originals and rollback."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import xfit_verified_inlink_release as release
from scripts.wp_publish import PublishError

CFG = release.ALLOWLIST["beginner_plant_25458"]
HEADING = '<h2 id="zacatecnik-rozhodnuti">'
EXISTING_WHEY = "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/"
EXISTING_CREATINE = "https://xfit.cz/xfit-os-kreatin-poradce/"


def source(body=None, *, modified="2026-11-22T09:00:00"):
    if body is None:
        body = (
            '<section id="xfit-rychla-volba-20261121">'
            '<h2>Co potřebujete právě teď?</h2>'
            '<p><a href="#zacatecnik-rozhodnuti">Bez nákupu</a></p>'
            '<p><a href="' + EXISTING_WHEY + '">Hledám protein</a></p>'
            '<p><a href="' + EXISTING_CREATINE + '">Hledám kreatin</a></p>'
            '</section>'
            + HEADING
            + '<p>Silový trénink, běžná strava a spánek mají přednost.</p>' * 55
            + '<h2>Jak vybrat bez nákupu?</h2><p>Podle konkrétní potřeby.</p>'
        )
    return {
        "id": 25458,
        "slug": "xfit-os-doplnky-pro-zacatecniky",
        "status": "publish",
        "link": CFG.url,
        "title": {"raw": "Doplňky stravy pro začátečníky: co má smysl"},
        "content": {"raw": body},
        "modified_gmt": modified,
    }


class BeginnerPlantChoiceTests(unittest.TestCase):
    def test_approved_scope_and_customer_message(self):
        self.assertEqual(CFG.post_id, 25458)
        self.assertEqual(CFG.before_heading, HEADING)
        self.assertEqual(CFG.target,
                         "https://xfit.cz/xfit-os-jak-vybrat-rostlinny-protein/")
        self.assertEqual(CFG.paragraph.count(CFG.target), 1)
        self.assertIn("mléčná bílkovina", CFG.paragraph)
        self.assertIn("nezaručuje nepřítomnost alergenů", CFG.paragraph)
        self.assertIn("prášek nepotřebujete", CFG.paragraph)
        self.assertNotIn("namaximum", CFG.paragraph.casefold())
        self.assertNotIn("affil", CFG.paragraph.casefold())
        self.assertIn("tento odkaz není doporučení", CFG.paragraph)

    def test_preserve_original_content_and_all_existing_choices_exactly(self):
        old = source()
        state = release.prepare(CFG, old)
        self.assertEqual(state["mode"], "update")
        self.assertEqual(state["after"],
                         state["before"].replace(HEADING,
                           CFG.paragraph + "\n" + HEADING, 1))
        self.assertEqual(state["after"].count(CFG.marker), 1)
        self.assertLess(state["after"].index(CFG.paragraph),
                        state["after"].index(HEADING))
        self.assertTrue(state["after"].startswith(state["before"].split(HEADING)[0]))
        for url in (EXISTING_WHEY, EXISTING_CREATINE):
            self.assertEqual(state["before"].count(url), state["after"].count(url))
        self.assertEqual(release.real_links(state["after"]),
                         release.real_links(state["before"]) | {CFG.target})
        self.assertTrue(release.public_verified(CFG, reader=lambda _: CFG.paragraph))

    def test_prevent_repeated_links_and_heading_or_source_drift(self):
        new = release.prepare(CFG, source())["after"]
        self.assertEqual(release.prepare(CFG, source(new))["mode"],
                         "already_linked")
        with self.assertRaisesRegex(PublishError, "heading drifted"):
            release.prepare(CFG, source(body=new.replace(
                CFG.paragraph + "\n", "", 1).replace(HEADING,
                                                      "<h2>Other</h2>", 1)))
        with self.assertRaises(PublishError):
            release.prepare(CFG, source(modified=""))

    def test_full_source_backup_and_single_post_only_after_cas(self):
        original = source()
        revised = release.prepare(CFG, original)["after"]
        after = source(revised, modified="2026-11-22T09:02:00")
        with TemporaryDirectory() as tmp, patch.object(
            release.Handoff, "backup",
            property(lambda self: Path(tmp) / "before.json")
        ):
            with patch.object(release, "remote", return_value=original):
                release.snapshot(CFG)
            saved = json.loads(CFG.backup.read_text(encoding="utf8"))
            self.assertEqual(saved["original_raw"], original["content"]["raw"])
            self.assertEqual(saved["remote_writes"], 0)
            self.assertEqual(saved["post_id"], 25458)
            # A simultaneous editor change invalidates the exact original source.
            with patch.object(release, "remote", return_value=source(
                original["content"]["raw"] + "<p>Concurrent edit</p>")), \
                 patch.object(release, "wp_request") as writer:
                with self.assertRaises(PublishError):
                    release.apply(CFG)
                writer.assert_not_called()
            with patch.object(release, "remote", side_effect=[original, after]), \
                 patch.object(release, "normalized_base",
                              return_value="https://xfit.cz"), \
                 patch.object(release, "wp_request",
                              return_value={"id": 25458, "status": "publish"}) as writer, \
                 patch.object(release, "public_verified", return_value=True):
                release.apply(CFG)
                writer.assert_called_once()
                self.assertEqual(writer.call_args.kwargs["payload"], {"content": revised})


if __name__ == "__main__":
    unittest.main()
