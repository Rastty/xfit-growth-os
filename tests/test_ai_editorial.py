"""Independent offline tests of AI content source selection, validation and WP writes.

No website fetches, model calls or real WordPress writes in this suite.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import xfit_ai_editorial as e
from scripts.wp_publish import MARKER, PublishError


class EditorialEngineTests(unittest.TestCase):
    def setUp(self):
        self.policy = e.config_targets()
        self.assertEqual(self.policy[0]["kind"], "enhance")
        self.base = MARKER + "\n" + "<p>Original article must stay absolutely unchanged.</p>"
        self.existing = {
            "id": 25541, "slug": self.policy[0]["slug"],
            "status": "publish", "modified_gmt": "2026-11-01T08:33:47",
            "link": "https://xfit.cz/" + self.policy[0]["slug"] + "/",
            "title": {"raw": "Original title"},
            "content": {"raw": self.base},
        }
        self.target = dict(self.policy[0])
        self.target.update({
            "status": "READY_FOR_RESTRICTED_AI_AUTHOR",
            "source_sha256": e.digest(self.base),
            "source_modified_gmt": self.existing["modified_gmt"],
            "source_title": "Original title",
            "source_excerpt": "Original article must stay absolutely unchanged.",
        })
        self.links = self.policy[0]["allowed_links"]
        self.html = (
            '<section data-xfit-ai-edit="' + self.target["marker"] + '">'
            '<h2>Co znamená cena za 25 g skutečných bílkovin?</h2>'
            '<p>Tento příklad slouží pouze k přepočtu údajů z obalu a'
            ' není aktuální komerční nabídka. Balení s hmotností'
            ' 900 g obsahuje podle modelové etikety 75 g bílkovin'
            ' na 100 g prášku. V balení tedy vychází 675 g bílkovin.'
            ' Při hypotetické ceně 899 Kč stojí 25 g bílkovin'
            ' přibližně 33,30 Kč. To není cena za 25 g prášku.</p>'
            '<p>Než porovnáváte dvě balení, přečtěte si'
            ' jejich etikety. Čísla na porci bez jasně uvedené'
            ' velikosti porce neposkytují společnou jednotku.'
            ' Výpočet podle skutečné etikety vám umožní vyhnout'
            ' se záměně celkové hmotnosti prášku a deklarovaného'
            ' množství bílkovin v produktu. Žádný konkrétní'
            ' výrobek zde netestujeme ani nedoporučujeme.</p>'
            '<ul><li>Najděte gramáž konkrétního balení.</li>'
            '<li>Opište bílkoviny uvedené na 100 g výrobku.</li>'
            '<li>Vydělte cenu skutečným množstvím bílkovin.</li>'
            '<li>Porovnejte dvě balení až po přepočtu na stejnou jednotku.</li>'
            '</ul>'
            '<p>Další vysvětlení najdete v'
            ' <a href="' + self.links[0] + '">průvodci proteinem</a>'
            ' a v pravidlech'
            ' <a href="' + self.links[1] + '">spotřebitelského označování</a>.'
            ' Nevybírejte výrobek pouze podle reklamního slibu.</p>'
            '</section>'
        )
        self.proposal = {
            "kind": "enhance", "slug": self.target["slug"],
            "marker": self.target["marker"], "section_html": self.html,
        }

    def with_artifacts(self, proposal=None):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        target = root / "target.json"
        content = root / "proposal.json"
        target.write_text(json.dumps(self.target), encoding="utf-8")
        content.write_text(json.dumps(self.proposal if proposal is None else proposal),
                           encoding="utf-8")
        return temp, target, content

    def test_exact_policy_and_existing_source_identity(self):
        self.assertEqual(len(self.policy), 5)
        self.assertEqual(e.digest(self.base), self.target["source_sha256"])

    def test_read_only_selects_existing_article_before_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(e, "TARGET", Path(tmp) / "selected.json"), \
                 patch.object(e, "read_wp_post", return_value=self.existing):
                result = e.select_target()
                self.assertEqual(result["status"], "TARGET_SELECTED")
                self.assertEqual(result["slug"], self.existing["slug"])
                chosen = json.loads((Path(tmp) / "selected.json").read_text())
                self.assertEqual(chosen["source_sha256"], e.digest(self.base))

    def test_current_existing_marker_skips_and_selects_following_target(self):
        post = dict(self.existing)
        post["content"] = {"raw": self.base + self.html}
        other = dict(post)
        other["id"] = 3660
        other["slug"] = "jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates"
        other["content"] = {"raw": "<p>" + "Example content " * 80 + "</p>"}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(e, "TARGET", Path(tmp) / "selected.json"), \
                 patch.object(e, "read_wp_post", side_effect=[post, other]), \
                 patch.object(e, "public_proof", return_value=True):
                result = e.select_target()
                self.assertEqual(result["slug"], other["slug"])

    def test_strict_existing_section_validated(self):
        temp, path, prop = self.with_artifacts()
        with temp, patch.object(e, "TARGET", path), patch.object(e, "PROPOSAL", prop):
            result = e.validate_proposal()
            self.assertEqual(result["marker"], self.target["marker"])

    def test_unapproved_affiliate_or_script_refused(self):
        cases = [
            self.html.replace(self.links[0], "https://namaximum.cz/buy"),
            self.html.replace("<h2>", "<script>alert(1)</script><h2>"),
            self.html.replace("<h2>", '<h2 onclick="track()">'),
            self.html.replace("<p>", '<p style="display:none">'),
        ]
        for body in cases:
            with self.subTest(body=body[:70]):
                p = dict(self.proposal, section_html=body)
                temp, path, prop = self.with_artifacts(p)
                with temp, patch.object(e, "TARGET", path), patch.object(e, "PROPOSAL", prop):
                    with self.assertRaises(PublishError):
                        e.validate_proposal()

    def test_exact_source_existing_update_and_public_readback(self):
        state = json.loads(json.dumps(self.existing))
        writes = []

        def fake_wp(base, path, *, payload=None):
            self.assertEqual(path, "posts/25541")
            self.assertIsNotNone(payload)
            writes.append(payload["content"])
            state["content"] = {"raw": payload["content"]}
            return {"id": 25541}

        temp, path, prop = self.with_artifacts()
        with temp, patch.object(e, "TARGET", path), patch.object(e, "PROPOSAL", prop), \
             patch.object(e, "read_wp_post", side_effect=lambda _: state), \
             patch.object(e, "wp_request", side_effect=fake_wp), \
             patch.object(e, "normalized_base", return_value="https://xfit.cz"), \
             patch.object(e, "public_proof", return_value=True) as public:
            result = e.publish_target()
            self.assertEqual(result["status"], "PUBLIC_VERIFIED_AI_EXISTING_ARTICLE_UPDATE")
            self.assertEqual(len(writes), 1)
            self.assertTrue(writes[0].startswith(MARKER + "\n"))
            self.assertEqual(writes[0].replace(self.html + "\n", "", 1), self.base)
            public.assert_called_once()

    def test_changed_source_preflight_does_not_write(self):
        state = json.loads(json.dumps(self.existing))
        state["content"]["raw"] += " another editor changed it"
        temp, path, prop = self.with_artifacts()
        with temp, patch.object(e, "TARGET", path), patch.object(e, "PROPOSAL", prop), \
             patch.object(e, "read_wp_post", return_value=state), \
             patch.object(e, "wp_request") as write:
            with self.assertRaisesRegex(PublishError, "source changed"):
                e.publish_target()
            write.assert_not_called()

    def test_public_failure_rolls_back_exact_self_owned_write(self):
        state = json.loads(json.dumps(self.existing))
        writes = []

        def fake_wp(base, path, *, payload=None):
            writes.append(payload["content"])
            state["content"]["raw"] = payload["content"]
            return {"id": 25541}

        temp, path, prop = self.with_artifacts()
        with temp, patch.object(e, "TARGET", path), patch.object(e, "PROPOSAL", prop), \
             patch.object(e, "read_wp_post", side_effect=lambda _: state), \
             patch.object(e, "wp_request", side_effect=fake_wp), \
             patch.object(e, "normalized_base", return_value="https://xfit.cz"), \
             patch.object(e, "public_proof", side_effect=PublishError("Cache stale")):
            with self.assertRaisesRegex(PublishError, "ROLLBACK_VERIFIED"):
                e.publish_target()
            self.assertEqual(len(writes), 2)
            self.assertEqual(state["content"]["raw"], self.base)

    def test_unknown_source_does_not_roll_back_other_editors(self):
        state = json.loads(json.dumps(self.existing))
        writes = []

        def fake_wp(base, path, *, payload=None):
            writes.append(payload["content"])
            state["content"]["raw"] = payload["content"] + "<p>someone else edited</p>"
            return {"id":25541}

        temp, path, prop = self.with_artifacts()
        with temp, patch.object(e, "TARGET", path), patch.object(e, "PROPOSAL", prop), \
             patch.object(e, "read_wp_post", side_effect=lambda _: state), \
             patch.object(e, "wp_request", side_effect=fake_wp), \
             patch.object(e, "normalized_base", return_value="https://xfit.cz"):
            with self.assertRaisesRegex(PublishError, "ROLLBACK_BLOCKED_CONCURRENT_EDIT"):
                e.publish_target()
            self.assertEqual(len(writes), 1)

    def test_no_new_post_overwrites_colliding_slug(self):
        target = dict(self.policy[2], status="READY_FOR_RESTRICTED_AI_AUTHOR")
        with patch.object(e, "list_by_slug", return_value=[{"slug":target["slug"]}]):
            self.assertTrue(e.list_by_slug(target["slug"]))


if __name__ == "__main__":
    unittest.main()
