"""Source-only regression for one reviewed, contextual protein-to-lactose guide inlink."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import xfit_verified_inlink_release as release
from scripts.wp_publish import PublishError

CFG = release.ALLOWLIST["protein_lactose_25451"]
OLD_LINK_A = "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/"
OLD_LINK_B = "https://xfit.cz/xfit-os-kreatin-poradce/"


def article(body=None, modified="2026-11-21T19:01:00"):
    if body is None:
        body = (
            "<h2>Výběr proteinů</h2>"
            '<p><a href="' + OLD_LINK_A + '">Srovnání syrovátkového proteinu</a>.</p>'
            + "<p>Počítejte bílkoviny také z běžné stravy a jídla.</p>" * 55
            + "<h3>Syrovátkový izolát (WPI)</h3>"
            + "<p>Izolát mívá méně laktózy, ale nelze předpokládat její úplnou absenci.</p>"
            + "<h3>Hydrolyzát</h3>"
            + '<p><a href="' + OLD_LINK_B + '">Doplňující přehled</a>.</p>'
        )
    return {
        "id":25451,
        "slug":"xfit-os-protein-guide",
        "status":"publish",
        "link":"https://xfit.cz/xfit-os-protein-guide/",
        "title":{"raw":"Jak vybrat protein: praktické rozhodování"},
        "content":{"raw":body},
        "modified_gmt":modified,
    }


class LactoseContextualInlinkTests(unittest.TestCase):
    def test_scope_and_editorial_safety(self):
        self.assertEqual(CFG.post_id, 25451)
        self.assertEqual(CFG.slug, "xfit-os-protein-guide")
        self.assertEqual(CFG.before_heading, "<h3>Hydrolyzát</h3>")
        self.assertEqual(CFG.target, "https://xfit.cz/xfit-os-protein-bez-laktozy/")
        self.assertEqual(CFG.paragraph.count(CFG.target), 1)
        self.assertEqual(CFG.paragraph.count(CFG.marker), 1)
        self.assertIn("alergii", CFG.paragraph)
        self.assertIn("laktózy", CFG.paragraph)
        self.assertIn("tento odkaz není doporučení", CFG.paragraph)
        self.assertNotIn("namaximum.cz", CFG.paragraph.casefold())
        self.assertTrue(release.public_verified(CFG, reader=lambda url: CFG.paragraph))

    def test_contextual_insertion_preserves_all_other_bytes_and_link_order(self):
        old = article()
        result = release.prepare(CFG, old)
        before, after = result["before"], result["after"]
        self.assertEqual(result["mode"], "update")
        self.assertEqual(after, before.replace(
            CFG.before_heading, CFG.paragraph + "\n" + CFG.before_heading, 1))
        self.assertLess(after.index("Syrovátkový izolát"), after.index(CFG.marker))
        self.assertLess(after.index(CFG.marker), after.index(CFG.before_heading))
        self.assertEqual(release.real_links(after), {
            OLD_LINK_A, OLD_LINK_B, CFG.target,
        })
        self.assertEqual(release.prepare(CFG, article(body=after))["mode"], "already_linked")

    def test_drift_and_duplicate_heading_block_before_write(self):
        old = article()
        for bad in (
            {**old, "id":25452},
            {**old, "slug":"not-the-protein-guide"},
            {**old, "title":{"raw":"Different unrelated content"}},
            {**old, "content":{"raw":old["content"]["raw"].replace(
                CFG.before_heading, "<h3>Other heading</h3>")}},
            {**old, "content":{"raw":old["content"]["raw"] + CFG.before_heading}},
            {**old, "content":{"raw":old["content"]["raw"] + CFG.marker}},
        ):
            with self.subTest(bad=bad.get("id")):
                with self.assertRaises(PublishError):
                    release.prepare(CFG, bad)

    def test_backup_race_guard_and_single_post_with_public_readback(self):
        old = article()
        changed_body = release.prepare(CFG, old)["after"]
        updated = article(body=changed_body, modified="2026-11-21T19:02:00")
        with TemporaryDirectory() as folder, patch.object(
                release.Handoff, "backup",
                property(lambda self: Path(folder) / "backup.json")):
            with patch.object(release, "remote", return_value=old):
                release.snapshot(CFG)
            backup = json.loads(CFG.backup.read_text(encoding="utf-8"))
            self.assertEqual(backup["original_raw"], old["content"]["raw"])
            self.assertEqual(backup["remote_writes"], 0)
            with patch.object(release, "remote", return_value=article(
                    body=old["content"]["raw"] + "<p>Concurrent editor change.</p>")), \
                    patch.object(release, "wp_request") as writer:
                with self.assertRaises(PublishError):
                    release.apply(CFG)
                writer.assert_not_called()
            with patch.object(release, "remote", side_effect=[old, updated]), \
                    patch.object(release, "normalized_base", return_value="https://xfit.cz"), \
                    patch.object(release, "wp_request",
                                 return_value={"id":CFG.post_id, "status":"publish"}) as writer, \
                    patch.object(release, "public_verified", return_value=True) as public:
                release.apply(CFG)
                writer.assert_called_once()
                self.assertEqual(writer.call_args.kwargs["payload"],
                                 {"content":changed_body})
                public.assert_called_once_with(CFG)


if __name__ == "__main__":
    unittest.main()
