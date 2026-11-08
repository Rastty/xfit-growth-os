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

    def test_public_identity_rejects_wrong_path_even_if_full_article_matches(self):
        from scripts.wp_publish import verify_public
        from unittest.mock import patch
        import io

        slug = "xfit-os-protein-guide"
        good_url = "https://xfit.cz/" + slug + "/"
        title = "Jak vybrat kvalitní protein"
        body = (
            "<h2>Výběr podle skutečné etikety a ceny</h2>"
            "<p>Zkontrolujte celkovou hmotnost proteinu i uvedený obsah "
            "bílkovin, jinak se jednotková cena nedá srovnat.</p>"
            "<p>Pokud máte dost bílkovin z běžného jídla, není důvod "
            "kupovat proteinový prášek jen kvůli reklamě.</p>"
            "<p>Před nákupem srovnejte aktuální cenu za porci a "
            "zkontrolujte informace na konkrétním obalu.</p>"
        )
        rendered = ("<html><h1>" + title + "</h1><main>" + body +
                    "</main></html>")

        class Response(io.BytesIO):
            status = 200
            def __init__(self, location):
                super().__init__(rendered.encode("utf-8"))
                self.location = location
            def geturl(self):
                return self.location

        for redirect in (
            "https://xfit.cz/",
            "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",
            good_url + "?cache=2026",
            "https://xfit.cz/" + slug + "-duplicate/",
            "https://xfit.cz:444/" + slug + "/",
            "https://other.example/" + slug + "/",
        ):
            with self.subTest(redirect=redirect), \
                 patch("scripts.wp_publish.urllib.request.urlopen",
                       side_effect=lambda *a, **k: Response(redirect)):
                with self.assertRaisesRegex(
                        PublishError, "different canonical page"):
                    verify_public(good_url, title, body)

        # Existing website canonicalization from xfit.cz to www.xfit.cz
        # must remain valid when the article path is unchanged.
        with patch("scripts.wp_publish.urllib.request.urlopen",
                   side_effect=lambda *a, **k: Response(
                       "https://www.xfit.cz/" + slug)):
            self.assertTrue(verify_public(good_url, title, body))

    def test_public_url_input_rejects_query_credentials_or_homepage(self):
        from scripts.wp_publish import verify_public
        from unittest.mock import patch
        with patch("scripts.wp_publish.urllib.request.urlopen") as get:
            for invalid in (
                "https://xfit.cz/",
                "https://xfit.cz/xfit-os-protein-guide/?key=invalid",
                "https://evil@xfit.cz/xfit-os-protein-guide/",
                "https://xfit.cz:443/xfit-os-protein-guide/",
                "http://xfit.cz/xfit-os-protein-guide/",
            ):
                with self.subTest(url=invalid), self.assertRaisesRegex(
                        PublishError, "Unexpected public URL identity"):
                    verify_public(invalid,"Any title","<p>Any content</p>")
            get.assert_not_called()

    def test_truncated_public_html_fails_early_even_with_full_test_body(self):
        from scripts.wp_publish import verify_public
        from unittest.mock import patch
        import io
        class Response(io.BytesIO):
            status = 200
            def geturl(self):
                return "https://xfit.cz/xfit-os-protein-guide/"
        big = b"<html><h1>Protein</h1>" + b"abc " * 600000
        body = ("<h2>Rozhodnutí na základě ceny a etikety</h2>"
                "<p>Pro konkrétní výrobek si ověřte dostupnost "
                "a příslušnou deklaraci jeho složení.</p>"
                "<p>Jiná varianta může obsahovat jiné množství "
                "bílkovin při stejné porci prášku.</p>"
                "<p>Nejde o osobní ani zdravotní doporučení, "
                "bílkoviny můžete přijímat také běžným jídlem.</p>")
        with patch("scripts.wp_publish.urllib.request.urlopen",
                   side_effect=lambda *a, **k: Response(big)):
            with self.assertRaisesRegex(PublishError, "too large"):
                verify_public("https://xfit.cz/xfit-os-protein-guide/","Protein",body)

    def test_wptexturize_punctuation_does_not_look_like_stale_body(self):
        from scripts.wp_publish import verify_public
        from unittest.mock import patch
        import io

        title = "Jak vybrat kreatin - srovnání balení"
        body = (
            '<h2>Na co se zaměřit – výběr podle ceny</h2>'
            '<p>Modelové balení "Natural" za 549,00 Kč je zde pouze ukázkou '
            'toho, jak srovnat skutečnou cenu za 100 g prášku.</p>'
            '<p>Jiná gramáž – a případně jiný výrobek – může vycházet dražší, '
            'proto je nutné porovnat cenu při stejné jednotce.</p>'
            '<p>Na etiketu se dívejte vždy před kliknutím a rozlišujte '
            'prášek od přesného obsahu deklarované látky.</p>'
        )
        public = ('<html><h1>Jak vybrat kreatin – srovnání balení</h1>'
                  '<main>' + body.replace(
                      'výběr podle ceny', 'výběr podle ceny').replace(
                      'zaměřit –', 'zaměřit -').replace(
                      '"Natural"', '“Natural”').replace(
                      'Jiná gramáž –', 'Jiná gramáž -')
                  + '</main></html>')

        class Response(io.BytesIO):
            status = 200
            def geturl(self):
                return "https://xfit.cz/xfit-os-kreatin-poradce/"

        with patch("scripts.wp_publish.urllib.request.urlopen",
                   side_effect=lambda *a, **k: Response(public.encode())), \
             patch("scripts.wp_publish.time.sleep") as pause:
            self.assertTrue(verify_public(
                "https://xfit.cz/xfit-os-kreatin-poradce/", title, body))
        pause.assert_not_called()

    def test_wptexturize_does_not_hide_changed_product_price(self):
        from scripts.wp_publish import verify_public
        from unittest.mock import patch
        import io

        title = "Srovnání proteinů"
        body = (
            '<h2>Modelové nabídky podle ceny za 100 g</h2>'
            '<p>První produkt je uveden za 549,00 Kč a má gramáž 1000 g; '
            'to umožňuje jasně vysvětlit jednotkovou cenu.</p>'
            '<p>Druhý produkt je uveden za 699,00 Kč a má gramáž 500 g; '
            'je nutné srovnávat stejnou jednotku.</p>'
            '<p>Nejde o slib nejlepší ceny na trhu, návštěvník '
            'si cenu i dostupnost ověří u prodejce.</p>'
        )
        changed = ('<html><h1>' + title + '</h1>' +
                   body.replace('549,00 Kč', '599,00 Kč') + '</html>')

        class Response(io.BytesIO):
            status = 200
            def geturl(self):
                return "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/"

        with patch("scripts.wp_publish.urllib.request.urlopen",
                   side_effect=lambda *a, **k: Response(changed.encode())), \
             patch("scripts.wp_publish.time.sleep") as pause:
            with self.assertRaisesRegex(PublishError, "old/incomplete"):
                verify_public(
                    "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",
                    title, body)
        self.assertEqual(pause.call_count, 2)

    def test_public_stale_body_fails_closed_even_when_title_matches(self):
        from scripts.wp_publish import verify_public
        from unittest.mock import patch
        import io
        title = "Přehled proteinu"
        body = ("<h2>Úplně nový srovnávací blok</h2>"
                "<p>Porovnejte stejný počet gramů bílkovin podle údajů na skutečném obalu.</p>"
                "<p>Nikdy nesrovnávejte jen objem jedné odměrky, protože se složení liší.</p>"
                "<p>Vysvětlete si cenu za stejné množství bílkovin dříve než nakoupíte.</p>"
               "<p>Nezapomeňte zkontrolovat velikost balení, etiketu a konkrétní variantu výrobku.</p>")
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
        doc = validate_document(dict(SAMPLE, wp_post_id=25451))
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
