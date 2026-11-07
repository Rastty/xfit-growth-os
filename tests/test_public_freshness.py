import unittest
from scripts.xfit_public_freshness import TARGETS, owns_public_url, visible_has, probe, product_card_texts
from scripts.wp_publish import PublishError


def post(slug, post_id, marker):
    source = "<!-- xfit-growth-os:v1 -->\n<h2>" + marker + "</h2>"
    if slug in ("xfit-os-kreatin-poradce", "xfit-os-syrovatkovy-protein-porovnani"):
        source += ("<article class='xfit-product-card'><h3>Produkt A</h3><p>Cena: 200,00 Kč</p></article>"
                   "<article class='xfit-product-card'><h3>Produkt B</h3><p>Cena: 300,00 Kč</p></article>")
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

    def test_visible_text_decodes_entities_and_whitespace(self):
        self.assertTrue(visible_has("<h2>Dvě&nbsp;cesty k výběru podle ceny</h2>",
                                    "Dvě cesty k výběru podle ceny"))

if __name__ == "__main__":
    unittest.main()
