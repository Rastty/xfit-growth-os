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
        self.base = MARKER + "\n" + "<p>" + ("Original article must stay absolutely unchanged. " * 22) + "</p>"
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
        self.assertEqual(len(self.policy), 7)
        self.assertEqual(e.digest(self.base), self.target["source_sha256"])

    def test_distinct_home_fitness_buying_targets_have_official_safety_source(self):
        slugs = [x["slug"] for x in self.policy]
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertEqual(slugs[-2:], [
            "xfit-os-vyber-odporove-gumy",
            "xfit-os-vyber-jednorucek-na-doma",
        ])
        for item in self.policy[-2:]:
            self.assertEqual(item["kind"], "create")
            self.assertGreaterEqual(item["min_words"], 550)
            self.assertIn(
                "https://commission.europa.eu/topics/business-and-industry/product-safety_en",
                item["allowed_links"],
            )

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

    def test_completed_existing_guides_advance_to_first_original_ai_article(self):
        first = dict(self.existing)
        first["content"] = {"raw": self.base + self.html}
        legacy = {
            "id": 3660, "slug": "jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates",
            "status": "publish", "modified_gmt": "2026-11-01T08:50:00",
            "link": "https://xfit.cz/jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates/",
            "content": {"raw": '<section data-xfit-ai-edit="xfit-ai-pilates-choice-table-v1">done</section>'},
        }
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(e, "TARGET", Path(temp) / "selected.json"), \
                 patch.object(e, "read_wp_post", side_effect=[first, legacy]), \
                 patch.object(e, "list_by_slug", return_value=[]) as lookup, \
                 patch.object(e, "public_proof", return_value=True) as readback:
                result = e.select_target()
                self.assertEqual(result["status"], "TARGET_SELECTED")
                self.assertEqual(result["kind"], "create")
                self.assertEqual(result["slug"], "xfit-os-jak-porovnat-proteinovou-tycinku")
                self.assertEqual(readback.call_count, 2)
                lookup.assert_called_once_with(result["slug"])

    def test_stale_public_html_on_prior_article_blocks_next_create(self):
        first = dict(self.existing)
        first["content"] = {"raw": self.base + self.html}
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(e, "TARGET", Path(temp) / "selected.json"), \
                 patch.object(e, "read_wp_post", return_value=first), \
                 patch.object(e, "public_proof", side_effect=PublishError("stale public cache")), \
                 patch.object(e, "list_by_slug") as lookup:
                with self.assertRaisesRegex(PublishError, "stale public cache"):
                    e.select_target()
                lookup.assert_not_called()

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


class AIOriginalArticleTests(unittest.TestCase):
    def setUp(self):
        self.target = dict(e.config_targets()[2], status="READY_FOR_RESTRICTED_AI_AUTHOR")
        marker = 'data-xfit-ai-create="' + self.target["marker"] + '"'
        paragraphs = []
        for i in range(1, 7):
            paragraphs.append(
                f'<h2>{i}. Kontrola porovnání tyčinek v konkrétní situaci</h2>'
                '<p>Základní porovnání výrobků musí vycházet z konkrétní etikety,'
                ' nikoli ze sloganu na krabici. Rozdílné velikosti balení'
                ' mohou vyvolat mylný dojem o ceně skutečně deklarovaných'
                ' bílkovin. Nejprve je potřeba přepočítat jednotku'
                ' a pak porovnat přesně stejnou veličinu. Když údaje'
                ' chybějí, čísla neodhadujeme a raději nevyvozujeme'
                ' výhodnost jedné nebo druhé varianty. U obou tyčinek'
                ' ověřte, že tabulka patří ke stejné hmotnosti a příchuti.'
                f' Tento kontrolní krok má v situaci {i} zvláštní význam'
                ' pro srovnání čitelné etikety a konečné ceny.</p>'
            )
        content = (
            '<section ' + marker + '>'
            '<p>Nejdříve porovnejte skutečné údaje o bílkovinách'
            ' na sto gramů a cenu celé tyčinky. Jde o práci s čísly'
            ' uvedenými výrobcem, nikoli o automatické doporučení nákupu.'
            ' Pokud žádnou takovou svačinu nepotřebujete, nekupujte ji.</p>'
            + "".join(paragraphs)
            + '<ul><li>Zapište gramáž tyčinky.</li>'
            '<li>Zkontrolujte množství bílkovin na sto gramů.</li>'
            '<li>Přepočítejte jednotkovou cenu.</li>'
            '<li>Vezměte v úvahu alergeny a deklarované složení.</li>'
            '<li>Nákup je volitelný, ne povinný.</li></ul>'
            '<p>Legislativní rámec informací na obalu poskytuje'
            ' <a href="' + self.target["allowed_links"][0] + '">'
            'Evropská komise</a>. Doplňující metodiku pro jiné'
            ' proteinové výrobky najdete ve'
            ' <a href="' + self.target["allowed_links"][1] + '">'
            'vzdělávacím průvodci XFIT</a>.</p>'
            '</section>'
        )
        self.proposal = {
            "kind": "create", "slug": self.target["slug"],
            "marker": self.target["marker"],
            "title": "Jak porovnat proteinové tyčinky podle etikety a ceny",
            "excerpt": ("Srovnání proteinových tyčinek podle údajů na etiketě, "
                        "gramáže balení a jednotkové ceny v praktických krocích."),
            "content": content,
        }

    def _artifacts(self, proposal=None):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        target_path = root / "target.json"
        proposal_path = root / "proposal.json"
        target_path.write_text(json.dumps(self.target, ensure_ascii=False), encoding="utf-8")
        proposal_path.write_text(json.dumps(self.proposal if proposal is None else proposal,
                                            ensure_ascii=False), encoding="utf-8")
        return temp, target_path, proposal_path

    def test_new_article_passes_strict_independent_editorial_review(self):
        temp, target_path, proposal_path = self._artifacts()
        with temp, patch.object(e, "TARGET", target_path), \
             patch.object(e, "PROPOSAL", proposal_path):
            result = e.validate_proposal()
            self.assertEqual(result["kind"], "create")
            self.assertEqual(result["slug"], self.target["slug"])

    def test_brand_new_article_can_publish_once_with_public_proof(self):
        temp, target_path, proposal_path = self._artifacts()
        with temp, patch.object(e, "TARGET", target_path), \
             patch.object(e, "PROPOSAL", proposal_path), \
             patch.object(e, "list_by_slug", return_value=[]), \
             patch.object(e, "publish", return_value={
                 "state": "live_verified", "slug": self.target["slug"],
                 "post_id": 90001, "url": "https://xfit.cz/" + self.target["slug"] + "/",
             }) as writer, \
             patch.object(e, "public_proof", return_value=True) as proof:
            receipt = e.publish_target()
            self.assertEqual(receipt["status"], "PUBLIC_VERIFIED_NEW_AI_ARTICLE")
            self.assertEqual(receipt["writes"], 1)
            writer.assert_called_once()
            self.assertTrue(writer.call_args.kwargs["live"])
            proof.assert_called_once()

    def test_slug_collision_stops_without_any_new_post(self):
        temp, target_path, proposal_path = self._artifacts()
        with temp, patch.object(e, "TARGET", target_path), \
             patch.object(e, "PROPOSAL", proposal_path), \
             patch.object(e, "list_by_slug", return_value=[{"id": 1}]), \
             patch.object(e, "publish") as writer:
            with self.assertRaisesRegex(PublishError, "no duplicate publish"):
                e.publish_target()
            writer.assert_not_called()

    def test_title_and_excerpt_cannot_contain_markup_or_untrusted_urls(self):
        for field, attack in [
            ("title", "<script>alert(1)</script> Jak vybrat tyčinku"),
            ("excerpt", "https://untrusted.example/sales " + "Než koupíte, zvažte možnosti. " * 3),
            ("title", "Jak předepsat léčbu podle tyčinky každému čtenáři"),
        ]:
            with self.subTest(field=field):
                proposal = dict(self.proposal, **{field: attack})
                temp, target_path, proposal_path = self._artifacts(proposal)
                with temp, patch.object(e, "TARGET", target_path), \
                     patch.object(e, "PROPOSAL", proposal_path):
                    with self.assertRaises(PublishError):
                        e.validate_proposal()


if __name__ == "__main__":
    unittest.main()
