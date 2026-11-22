"""Keep indexed protein guide source untouched except one plant context handoff."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import xfit_verified_inlink_release as release
from scripts.wp_publish import PublishError

CFG=release.ALLOWLIST["protein_plant_25451"]
LACTOSE=release.ALLOWLIST["protein_lactose_25451"]


def approved_parent(*, modified="2026-11-22T09:00:00", body=None):
    if body is None:
        body=(
            "<h2>1. Kolik bílkovin potřebujete?</h2>"
            "<p>Nejdřív běžné jídlo a rozhodování o skutečné potřebě.</p>"*42
            + LACTOSE.paragraph
            + "\n<h3>Hydrolyzát</h3>"
            + "<p>Syrovátka není vhodná pro každou situaci.</p>"
            + "<h3>Sójové, hrachové a další rostlinné proteiny</h3>"
            + "<p>Etiketa a cena hrají významnou roli. Některé druhy obsahují jiné aminokyseliny.</p>"
            + CFG.before_heading
            + "<p>Výpočty přepočtené ceny a samotných bílkovin.</p>"
            + "<h2>Zdroje</h2><p>Žádné vymyšlené nabídky nebo ceny.</p>"
        )
    return {
        "id":25451, "slug":"xfit-os-protein-guide",
        "status":"publish",
        "link":"https://xfit.cz/xfit-os-protein-guide/",
        "title":{"raw":"Jak vybrat protein: přehled druhů a ceny"},
        "content":{"raw":body},"modified_gmt":modified,
    }


class PlantContextLinkTests(unittest.TestCase):
    def test_only_exact_new_target_and_reader_first_context(self):
        self.assertEqual(CFG.post_id,25451)
        self.assertEqual(CFG.slug,"xfit-os-protein-guide")
        self.assertEqual(CFG.before_heading,
                         "<h2>3. Jak poznat skutečně výhodnou cenu</h2>")
        self.assertEqual(CFG.target,
                         "https://xfit.cz/xfit-os-jak-vybrat-rostlinny-protein/")
        self.assertEqual(CFG.paragraph.count(CFG.target),1)
        self.assertEqual(CFG.paragraph.count(CFG.marker),1)
        self.assertIn("rostlinná směs",CFG.paragraph)
        self.assertIn("alergeny",CFG.paragraph)
        self.assertIn("nemusíte žádný prášek kupovat",CFG.paragraph)
        self.assertIn("Tento odkaz není doporučení k nákupu",CFG.paragraph)
        self.assertNotIn("namaximum.cz",CFG.paragraph.casefold())
        self.assertNotIn("a_aid",CFG.paragraph)
        self.assertTrue(release.public_verified(CFG,reader=lambda _:CFG.paragraph))

    def test_preserves_all_old_links_headings_images_source_bytes_and_lactose(self):
        before=approved_parent()
        state=release.prepare(CFG,before)
        self.assertEqual(state["mode"],"update")
        original=before["content"]["raw"]
        self.assertEqual(state["after"],original.replace(
            CFG.before_heading,CFG.paragraph+"\n"+CFG.before_heading,1))
        self.assertLess(state["after"].index("<h3>Sójové"),
                        state["after"].index(CFG.marker))
        self.assertLess(state["after"].index(CFG.marker),
                        state["after"].index(CFG.before_heading))
        self.assertEqual(state["after"].count(LACTOSE.marker),1)
        self.assertEqual(state["after"].count(CFG.marker),1)
        self.assertIn(LACTOSE.target,release.real_links(state["after"]))
        self.assertIn(CFG.target,release.real_links(state["after"]))
        self.assertEqual(release.prepare(CFG,approved_parent(body=state["after"]))["mode"],
                         "already_linked")

    def test_source_drift_double_heading_and_partial_patch_stop_prewrite(self):
        before=approved_parent()
        for changed in (
            {**before,"id":25452},
            {**before,"slug":"wrong"},
            {**before,"status":"draft"},
            {**before,"title":{"raw":"Unrelated site article"}},
            {**before,"content":{"raw":before["content"]["raw"].replace(
                CFG.before_heading,"<h2>Alternative</h2>")}},
            {**before,"content":{"raw":before["content"]["raw"]+CFG.before_heading}},
            {**before,"content":{"raw":before["content"]["raw"]+CFG.marker}},
        ):
            with self.subTest(changed=changed.get("slug")):
                with self.assertRaises(PublishError):
                    release.prepare(CFG,changed)

    def test_prewrite_full_backup_and_exact_one_wp_post_only_after_source_recheck(self):
        before=approved_parent()
        after=approved_parent(modified="2026-11-22T09:01:00",
                              body=release.prepare(CFG,before)["after"])
        with TemporaryDirectory() as tmp, patch.object(
                release.Handoff,"backup",
                property(lambda self:Path(tmp)/"original.json")):
            with patch.object(release,"remote",return_value=before):
                release.snapshot(CFG)
            saved=json.loads(CFG.backup.read_text(encoding="utf-8"))
            self.assertEqual(saved["original_raw"],before["content"]["raw"])
            self.assertEqual(saved["remote_writes"],0)
            with patch.object(release,"remote",return_value=approved_parent(
                    body=before["content"]["raw"]+"<p>Concurrent editor.</p>")), \
                 patch.object(release,"wp_request") as wp:
                with self.assertRaises(PublishError):
                    release.apply(CFG)
                wp.assert_not_called()
            with patch.object(release,"remote",side_effect=[before,after]), \
                 patch.object(release,"normalized_base",return_value="https://xfit.cz"), \
                 patch.object(release,"wp_request",return_value={
                     "id":CFG.post_id,"status":"publish"}) as wp, \
                 patch.object(release,"public_verified",return_value=True):
                release.apply(CFG)
                wp.assert_called_once()
                self.assertEqual(wp.call_args.kwargs["payload"],
                                 {"content":after["content"]["raw"]})


if __name__=="__main__":
    unittest.main()
