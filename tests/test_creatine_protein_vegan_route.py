"""Keep an accessible plant choice inside the existing vegan case, not a new article."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import xfit_verified_inlink_release as release
from scripts.wp_publish import PublishError

CFG = release.ALLOWLIST["creatine_protein_vegan_25504"]
READY = Path("content/ready/xfit-os-kreatin-nebo-protein.json")
VEGAN_START = '<details><summary><strong>Jsem vegan nebo nesnáším mléčné bílkoviny'
NEXT_START = '<details><summary><strong>Mám nemocné ledviny'
WHEY = "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/"
CREATINE = "https://xfit.cz/xfit-os-kreatin-poradce/"


def original():
    data = json.loads(READY.read_text(encoding="utf-8"))
    return {
        "id": CFG.post_id, "slug": CFG.slug, "status": "publish",
        "link": CFG.url,
        "title": {"raw": data["title"]},
        "content": {"raw": data["content"]},
        "modified_gmt": "2026-11-22T09:00:00",
    }


class VeganChoiceTests(unittest.TestCase):
    def test_reviewed_source_anchor_is_unique_and_preserves_all_other_content(self):
        old = original()
        body = old["content"]["raw"]
        self.assertEqual(CFG.post_id, 25504)
        self.assertIn("kreatin", CFG.title_term)
        self.assertEqual(body.count(CFG.before_heading), 1)
        self.assertEqual(body.count(VEGAN_START), 1)
        self.assertEqual(body.count(NEXT_START), 1)
        self.assertNotIn(CFG.target, release.real_links(body))
        state = release.prepare(CFG, old)
        self.assertEqual(state["mode"], "update")
        after = state["after"]
        self.assertEqual(after, body.replace(
            CFG.before_heading, CFG.paragraph + "\n" + CFG.before_heading, 1
        ))
        self.assertEqual(after.count(CFG.target), 1)
        self.assertEqual(after.count(CFG.marker), 1)
        self.assertEqual(after.count(WHEY), body.count(WHEY))
        self.assertEqual(after.count(CREATINE), body.count(CREATINE))
        self.assertEqual(release.real_links(after), release.real_links(body) | {CFG.target})

    def test_only_vegan_details_contains_new_link_and_original_warning_survives(self):
        after = release.prepare(CFG, original())["after"]
        start = after.index(VEGAN_START)
        end = after.index("</details>", start)
        vegan = after[start:end]
        self.assertIn(CFG.target, vegan)
        self.assertIn("Kontrolujte složení a alergeny", vegan)
        self.assertIn("běžné jídlo", vegan)
        self.assertNotIn(CFG.target, after[:start])
        self.assertNotIn(CFG.target, after[after.index(NEXT_START):])
        self.assertEqual(after.count("<details>"), after.count("</details>"))
        self.assertIn("tento odkaz není doporučení", vegan)
        self.assertIn("Rostlinný původ není zárukou", vegan)
        self.assertNotIn("a_aid", CFG.paragraph)
        self.assertNotIn("namaximum", CFG.paragraph.casefold())
        self.assertTrue(release.public_verified(CFG, reader=lambda _: CFG.paragraph))

    def test_repeat_is_noop_and_context_drift_fails_closed(self):
        old = original()
        result = release.prepare(CFG, old)
        linked = {**old, "content": {"raw": result["after"]}}
        self.assertEqual(release.prepare(CFG, linked)["mode"], "already_linked")
        drift = {**old, "content": {
            "raw": old["content"]["raw"].replace(
                NEXT_START, '<details><summary><strong>Změněné téma')
        }}
        with self.assertRaisesRegex(PublishError, "heading drifted"):
            release.prepare(CFG, drift)

    def test_original_artifact_and_source_cas_before_single_post(self):
        old = original()
        updated = release.prepare(CFG, old)["after"]
        newer = {**old, "content": {"raw": updated},
                 "modified_gmt": "2026-11-22T10:00:00"}
        with TemporaryDirectory() as temp, patch.object(
            release.Handoff, "backup",
            property(lambda self: Path(temp) / "rollback.json")
        ):
            with patch.object(release, "remote", return_value=old):
                release.snapshot(CFG)
            saved = json.loads(CFG.backup.read_text(encoding="utf-8"))
            self.assertEqual(saved["post_id"], 25504)
            self.assertEqual(saved["original_raw"], old["content"]["raw"])
            self.assertEqual(saved["remote_writes"], 0)
            # If another editor touched the source, never overwrite it.
            drifted = {**old, "modified_gmt": "2026-11-22T09:55:00"}
            with patch.object(release, "remote", return_value=drifted), \
                 patch.object(release, "wp_request") as writer:
                with self.assertRaises(PublishError):
                    release.apply(CFG)
                writer.assert_not_called()
            with patch.object(release, "remote", side_effect=[old, newer]), \
                 patch.object(release, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(release, "wp_request",
                              return_value={"id":25504,"status":"publish"}) as writer, \
                 patch.object(release, "public_verified", return_value=True):
                release.apply(CFG)
                writer.assert_called_once()
                self.assertEqual(writer.call_args.kwargs["payload"],
                                 {"content": updated})


if __name__ == "__main__":
    unittest.main()
