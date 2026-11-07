import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from scripts.xfit_public_freshness import (
    TARGETS, owns_public_url, visible_has, probe, product_card_texts,
    typography_key, public_get,
)
from scripts.wp_publish import PublishError


def post(slug, post_id, marker):
    source = "<!-- xfit-growth-os:v1 -->\n<h2>" + marker + "</h2>"
    if slug in ("xfit-os-kreatin-poradce", "xfit-os-syrovatkovy-protein-porovnani"):
        source += (
            "<article class='xfit-product-card'><h3>Produkt A</h3><p>Cena: 200,00 Kč</p>"
            "<a rel='sponsored nofollow' href='https://www.namaximum.cz/produkt-a"
            "?utm_medium=affiliate&a_aid=demo&a_bid=test'>Zobrazit</a></article>"
            "<article class='xfit-product-card'><h3>Produkt B</h3><p>Cena: 300,00 Kč</p>"
            "<a rel='sponsored nofollow' href='https://www.namaximum.cz/produkt-b"
            "?utm_medium=affiliate&a_aid=demo&a_bid=test'>Zobrazit</a></article>")
    return {"id":post_id, "slug":slug, "status":"publish",
            "content":{"raw":source},
            "link":"https://xfit.cz/"+slug+"/"}


class PublicFreshnessTests(unittest.TestCase):
    def test_known_canonical_urls_only(self):
        self.assertTrue(owns_public_url("https://xfit.cz/xfit-os-kreatin-poradce/", "xfit-os-kreatin-poradce"))
        self.assertFalse(owns_public_url("https://external.example/xfit-os-kreatin-poradce/", "xfit-os-kreatin-poradce"))
        self.assertFalse(owns_public_url("https://xfit.cz/xfit-os-kreatin-poradce/?token=private", "xfit-os-kreatin-poradce"))

    def test_public_view_checks_edited_body_not_unchanged_title(self):
        target = TARGETS[2]
        original = post(*target)
        success = probe(target, read_post=lambda _:original,
                        read_public=lambda url:("<html><h1>Jak vybrat kreatin</h1>"+original["content"]["raw"]+"</html>",{"Age":"0"}))
        self.assertEqual(success["status"],"PUBLIC_FRESH")
        stale = probe(target, read_post=lambda _:original,
                      read_public=lambda url:("<html><h1>Jak vybrat kreatin</h1><p>Starý obsah</p></html>",{"Age":"720"}))
        self.assertEqual(stale["status"],"PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
        self.assertTrue(stale["wp_source_has_target"])
        self.assertFalse(stale["public_has_target"])

    def test_stale_pricing_cards_fail_even_if_new_heading_is_already_visible(self):
        target = TARGETS[3]
        fresh_post = post(*target)
        changed_prices = fresh_post["content"]["raw"].replace("200,00 Kč", "999,00 Kč")
        report = probe(target, read_post=lambda _:fresh_post,
                       read_public=lambda _:("<html>"+changed_prices+"</html>",{}))
        self.assertEqual(report["status"],"PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
        self.assertTrue(report["public_has_target"])
        self.assertFalse(report["product_cards_match"])
        self.assertEqual(report["wp_product_cards"],2)
        self.assertEqual(report["public_product_cards"],2)

    def test_product_parser_ignores_unrelated_outer_articles(self):
        cards = product_card_texts(
            "<article><h3>Theme shell</h3><article class='xfit-product-card'>"
            "<h3>Whey A</h3><p>Cena: <strong>900&nbsp;Kč</strong></p>"
            "</article></article>")
        self.assertEqual(cards, ["whey a cena: 900 kč"])

    def test_source_missing_is_not_mistaken_for_cache_staleness(self):
        slug, ident, marker = TARGETS[3]
        source = post(slug, ident, "Stará sekce")
        result = probe(TARGETS[3], read_post=lambda _:source,
                       read_public=lambda _:("<h2>Dvě cesty k výběru podle ceny</h2>",{}))
        self.assertEqual(result["status"],"SOURCE_NOT_UPDATED")
        self.assertFalse(result["wp_source_has_target"])

    def test_public_transport_error_fails_safely_without_retrying_posts(self):
        target = TARGETS[2]
        result = probe(target, read_post=lambda _:post(*target),
                       read_public=lambda _: (_ for _ in ()).throw(OSError("network")))
        self.assertEqual(result["status"],"PUBLIC_READ_ERROR")
        self.assertNotIn("network",str(result))

    def test_commercial_drift_report_distinguishes_price_from_copy(self):
        target = TARGETS[2]
        original = post(*target)
        source = original["content"]["raw"]
        source = source.replace(
            "Cena: 200,00 Kč</p>",
            "Cena: 200,00 Kč · Balení: 500 g</p>"
            "<p>Cena za 100 g prášku: 40,00 Kč</p>"
        ).replace(
            "Cena: 300,00 Kč</p>",
            "Cena: 300,00 Kč · Balení: 600 g</p>"
            "<p>Cena za 100 g prášku: 50,00 Kč</p>"
        )
        source = source.replace(
            "</article>",
            '<a href="https://www.namaximum.cz/product?secret=private">'
            "Zobrazit balení</a></article>", 1
        )
        original["content"]["raw"] = source

        price_drift = probe(
            target, read_post=lambda _: original,
            read_public=lambda _: ("<html>" + source.replace(
                "Cena: 200,00 Kč", "Cena: 220,00 Kč") + "</html>", {})
        )
        self.assertEqual(price_drift["status"], "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
        self.assertEqual(price_drift["commercial_fact_drift_positions"], [1])
        self.assertEqual(price_drift["noncommercial_copy_drift_positions"], [])
        self.assertNotIn("secret", str(price_drift))
        self.assertNotIn("namaximum", str(price_drift))

        copy_drift = probe(
            target, read_post=lambda _: original,
            read_public=lambda _: ("<html>" + source.replace(
                "Produkt B", "Produkt B upravený") + "</html>", {})
        )
        self.assertEqual(copy_drift["commercial_fact_drift_positions"], [])
        self.assertEqual(copy_drift["noncommercial_copy_drift_positions"], [2])
        self.assertEqual(copy_drift["mismatched_card_positions"], [2])

    def test_same_visible_card_text_with_changed_affiliate_url_fails(self):
        target = TARGETS[2]
        original = post(*target)
        source = original["content"]["raw"]
        tampered = source.replace(
            "https://www.namaximum.cz/produkt-a",
            "https://external-merchant.example/produkt-a",
            1
        )
        result = probe(
            target, read_post=lambda _: original,
            read_public=lambda _: ("<html>" + tampered + "</html>", {})
        )
        self.assertTrue(result["public_has_target"])
        self.assertEqual(result["wp_product_cards"], 2)
        self.assertEqual(result["public_product_cards"], 2)
        self.assertFalse(result["product_cards_match"])
        self.assertFalse(result["public_affiliate_link_integrity"])
        self.assertEqual(result["affiliate_link_drift_positions"], [1])
        self.assertEqual(result["unsafe_affiliate_link_positions"], [1])
        self.assertEqual(result["status"], "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
        self.assertNotIn("a_aid", str(result))
        self.assertNotIn("demo", str(result))

    def test_wordpress_typographic_title_is_equivalent_without_weakening_prices(self):
        target = TARGETS[2]
        original = post(*target)
        original["content"]["raw"] = original["content"]["raw"].replace(
            "Produkt A", "Produkt A - Natural"
        )
        public = original["content"]["raw"].replace(
            "Produkt A - Natural", "Produkt A – Natural"
        )
        result = probe(
            target, read_post=lambda _: original,
            read_public=lambda _: ("<html>" + public + "</html>", {})
        )
        self.assertEqual(result["status"], "PUBLIC_FRESH")
        self.assertTrue(result["product_cards_match"])
        self.assertTrue(result["public_product_title_integrity"])
        self.assertTrue(result["public_affiliate_link_integrity"])
        self.assertEqual(result["product_title_drift_positions"], [1])
        self.assertEqual(result["typographic_title_drift_positions"], [1])
        self.assertEqual(result["substantive_title_drift_positions"], [])
        self.assertEqual(result["commercial_fact_drift_positions"], [])

    def test_missing_sponsored_disclosure_fails_even_with_matching_prices(self):
        target = TARGETS[3]
        original = post(*target)
        public = original["content"]["raw"].replace(
            "rel='sponsored nofollow'", "rel='nofollow'", 1
        )
        result = probe(
            target, read_post=lambda _: original,
            read_public=lambda _: ("<html>" + public + "</html>", {})
        )
        self.assertFalse(result["public_affiliate_link_integrity"])
        self.assertEqual(result["affiliate_link_drift_positions"], [1])
        self.assertIn(1, result["unsafe_affiliate_link_positions"])
        self.assertEqual(result["status"], "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")

    def test_noncommercial_title_change_is_identified(self):
        target = TARGETS[2]
        original = post(*target)
        public = original["content"]["raw"].replace("Produkt A", "Produkt A nová verze")
        result = probe(
            target, read_post=lambda _: original,
            read_public=lambda _: ("<html>" + public + "</html>", {})
        )
        self.assertEqual(result["product_title_drift_positions"], [1])
        self.assertEqual(result["typographic_title_drift_positions"], [])
        self.assertEqual(result["substantive_title_drift_positions"], [1])
        self.assertEqual(result["affiliate_link_drift_positions"], [])
        self.assertTrue(result["public_affiliate_link_integrity"])
        self.assertFalse(result["public_product_title_integrity"])
        self.assertEqual(result["status"], "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")

    def test_unparsable_card_is_not_mistaken_for_matching_price(self):
        target = TARGETS[3]
        original = post(*target)
        altered = original["content"]["raw"].replace("Produkt A", "Jiný produkt")
        report = probe(
            target, read_post=lambda _: original,
            read_public=lambda _: ("<html>" + altered + "</html>", {})
        )
        self.assertEqual(report["unparsed_commercial_fact_positions"], [1])
        self.assertEqual(report["commercial_fact_drift_positions"], [])
        self.assertEqual(report["status"], "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")

    def test_title_triage_never_confuses_typographic_and_substantive_drift(self):
        self.assertEqual(
            typography_key("Creatine monohydrate - Natural"),
            typography_key("Creatine monohydrate – Natural"),
        )
        self.assertNotEqual(
            typography_key("Creatine monohydrate - Natural 1kg"),
            typography_key("Creatine monohydrate - Natural 500g"),
        )

    def test_public_http_get_retries_only_readonly_transient_failures(self):
        class FakeResponse:
            status = 200
            headers = {"Age": "0"}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def geturl(self):
                return "https://xfit.cz/xfit-os-kreatin-poradce/"

            def read(self, size):
                return b"<html>public card</html>"

        url = "https://xfit.cz/xfit-os-kreatin-poradce/"
        with patch("scripts.xfit_public_freshness.urllib.request.urlopen",
                   side_effect=[URLError("temporary"), FakeResponse()]) as get, \
             patch("scripts.xfit_public_freshness.time.sleep") as pause:
            page, headers = public_get(url)
            self.assertEqual(page, "<html>public card</html>")
            self.assertEqual(headers["Age"], "0")
            self.assertEqual(get.call_count, 2)
            pause.assert_called_once_with(2)

        with patch("scripts.xfit_public_freshness.urllib.request.urlopen",
                   side_effect=HTTPError(url, 404, "Not Found", None, None)) as get, \
             patch("scripts.xfit_public_freshness.time.sleep") as pause:
            with self.assertRaises(HTTPError):
                public_get(url)
            self.assertEqual(get.call_count, 1)
            pause.assert_not_called()

        with patch("scripts.xfit_public_freshness.urllib.request.urlopen",
                   side_effect=URLError("still unavailable")) as get, \
             patch("scripts.xfit_public_freshness.time.sleep") as pause:
            with self.assertRaises(URLError):
                public_get(url)
            self.assertEqual(get.call_count, 3)
            self.assertEqual(pause.call_count, 2)

    def test_visible_text_decodes_entities_and_whitespace(self):
        self.assertTrue(visible_has("<h2>Dvě&nbsp;cesty k výběru podle ceny</h2>",
                                    "Dvě cesty k výběru podle ceny"))

if __name__ == "__main__":
    unittest.main()
