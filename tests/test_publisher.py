import json
import unittest
from pathlib import Path
from scripts.wp_publish import MARKER, PublishError, validate_document

SAMPLE = {
    "slug": "xfit-os-protein-guide",
    "title": "Jak vybrat protein: přehledný průvodce",
    "content": "<h2>Úvod</h2>" + ("Praktický kontrolovaný obsah. " * 18),
    "excerpt": "Výběr proteinu podle složení."
}

class PublisherValidationTests(unittest.TestCase):
    def test_valid_document_and_ownership_marker(self):
        doc = validate_document(SAMPLE)
        self.assertTrue(doc["content"].startswith(MARKER))
        self.assertEqual(doc["slug"], SAMPLE["slug"])

    def test_reject_non_namespaced_slug(self):
        doc = dict(SAMPLE, slug="vyziva")
        with self.assertRaises(PublishError):
            validate_document(doc)

    def test_reject_javascript(self):
        doc = dict(SAMPLE, content=SAMPLE["content"] + "<script>alert(1)</script>")
        with self.assertRaises(PublishError):
            validate_document(doc)

    def test_reject_short_content(self):
        doc = dict(SAMPLE, content="Krátký text")
        with self.assertRaises(PublishError):
            validate_document(doc)


    def test_pinned_post_id(self):
        doc = dict(SAMPLE, wp_post_id=25451)
        self.assertEqual(validate_document(doc)["wp_post_id"], 25451)

    def test_invalid_post_id_rejected(self):
        doc = dict(SAMPLE, wp_post_id="25451")
        with self.assertRaises(PublishError):
            validate_document(doc)


    def test_public_body_requires_actual_revised_content(self):
        from scripts.wp_publish import verify_public
        from unittest.mock import patch
        import io

        title = "Jak vybrat protein – návod"
        body = ("<h2>Jak srovnat cenu ze skutečné etikety</h2>"
                "<p>Nejdřív si přečtěte etiketu a přepočítejte množství skutečných bílkovin v balení.</p>"
                "<p>Nová kontrolní věta o srovnání proteinů je důležitá při každém nákupu.</p>"
                "<p>Rozhodnutí nekoupit žádný doplněk je také rozumnou možností.</p>")
        old = "<html><h1>" + title + "</h1><p>Nejdřív si přečtěte etiketu.</p></html>"
        fresh = "<html><h1>" + title + "</h1><main>" + body + "</main></html>"

        class Response(io.BytesIO):
            status = 200
            def geturl(self):
                return "https://xfit.cz/xfit-os-protein-guide/"

        with patch("scripts.wp_publish.urllib.request.urlopen",
                   side_effect=[Response(old.encode()), Response(fresh.encode())]) as load, \
             patch("scripts.wp_publish.time.sleep") as pause:
            self.assertTrue(verify_public("https://xfit.cz/xfit-os-protein-guide/", title, body))
        self.assertEqual(load.call_count, 2)
        pause.assert_called_once_with(2)

    def test_public_stale_body_fails_closed_even_when_title_matches(self):
        from scripts.wp_publish import verify_public
        from unittest.mock import patch
        import io
        title = "Přehled proteinu"
        body = ("<h2>Úplně nový srovnávací blok</h2>"
                "<p>Porovnejte stejný počet gramů bílkovin podle údajů na skutečném obalu.</p>"
                "<p>Nikdy nesrovnávejte jen objem jedné odměrky, protože se složení liší.</p>"
                "<p>Vysvětlete si cenu za stejné množství bílkovin dříve než nakoupíte.</p>")
        stale = ("<html><h1>" + title + "</h1>"
                 "<p>Porovnejte jen cenu balení bez dalšího výpočtu.</p></html>")
        class Response(io.BytesIO):
            status = 200
            def geturl(self):
                return "https://xfit.cz/xfit-os-protein-guide/"
        with patch("scripts.wp_publish.urllib.request.urlopen",
                   side_effect=lambda *args, **kwargs: Response(stale.encode())) as load, \
             patch("scripts.wp_publish.time.sleep") as pause:
            with self.assertRaisesRegex(PublishError, "old/incomplete"):
                verify_public("https://xfit.cz/xfit-os-protein-guide/", title, body)
        self.assertEqual(load.call_count, 3)
        self.assertEqual(pause.call_count, 2)

    def test_readback_rejects_old_wordpress_body_after_post(self):
        from scripts.wp_publish import publish, validate_document
        from unittest.mock import patch
        doc = validate_document(SAMPLE)
        existing = {"id": 25451, "slug": doc["slug"], "status": "publish",
                    "content": {"raw": doc["content"]}, "link": "https://xfit.cz/xfit-os-protein-guide/"}
        saved = {"id": 25451}
        old = {"id": 25451, "slug": doc["slug"], "status": "publish",
               "content": {"raw": MARKER + "\\n<p>Stará verze bez nejnovějších odstavců.</p>"},
               "link": "https://xfit.cz/xfit-os-protein-guide/"}
        with patch("scripts.xfit_editorial_gate.check_document", return_value={"passed": True}), \
             patch("scripts.wp_publish.normalized_base", return_value="https://xfit.cz"), \
             patch("scripts.wp_publish.wp_request", side_effect=[existing, saved, old]) as write, \
             patch("scripts.wp_publish.verify_public") as public:
            with self.assertRaisesRegex(PublishError, "raw body differs"):
                publish(doc, live=True)
        self.assertEqual(write.call_count, 3)
        public.assert_not_called()

    def test_html_normalization_tolerates_inline_tags_and_entities(self):
        from scripts.wp_publish import article_visible
        a = "<p>Cena za &nbsp; 25 g bílkovin je <strong>stejná</strong> pro obě varianty.</p>"
        b = "<div><p>Cena za 25 g bílkovin je stejná pro obě varianty.</p></div>"
        self.assertEqual(article_visible(a)[0], article_visible(b)[0])

    def test_checked_in_first_article(self):
        doc = json.loads(Path("content/ready/xfit-os-protein-guide.json").read_text(encoding="utf-8"))
        validated = validate_document(doc)
        self.assertEqual(validated["slug"], "xfit-os-protein-guide")

if __name__ == "__main__":
    unittest.main()
