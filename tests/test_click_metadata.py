import unittest
from html.parser import HTMLParser

from scripts.xfit_click_metadata import card_click_attributes
from scripts.wp_publish import PublishError
BASE = ("https://www.namaximum.cz/?utm_medium=affiliate"
        "&utm_campaign=affial.com&utm_source=pap&a_aid=TESTA&a_bid=TESTB")
SAMPLE = ("https://www.namaximum.cz/kategorie/kreatin/creatine-creapure"
          "?variant=392&utm_medium=affiliate&utm_campaign=affial.com"
          "&utm_source=pap&a_aid=TESTA&a_bid=TESTB")
from scripts.xfit_creatine_guide import build_document as creatine_document
from scripts.xfit_whey_guide import build_document as whey_document


class OutboundAttributes(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ctas = []

    def handle_starttag(self, tag, attrs):
        if tag == "a" and "sponsored" in dict(attrs).get("rel", "").split():
            self.ctas.append(dict(attrs))


class ClickMetadataTests(unittest.TestCase):
    def test_feed_id_is_whitelisted_and_never_contains_tracking_url(self):
        self.assertEqual(
            card_click_attributes("392", "creatine"),
            ' data-xfit-engine="creatine" data-xfit-partner="namaximum"'
            ' data-xfit-product-id="392"',
        )
        for invalid in (None, "", "000392", "392&foo", "392.0", True, False,
                        0, -1, 2147483648, 3.2, "https://example.com/1"):
            with self.subTest(value=repr(invalid)), self.assertRaises(PublishError):
                card_click_attributes(invalid, "whey")
        with self.assertRaises(PublishError):
            card_click_attributes(392, "unknown")

    def test_both_trusted_catalog_builders_produce_attributed_ctas(self):
        def offer(ident, name, category, price):
            return {"id": str(ident), "title": name, "price_czk": price,
                    "category": category, "merchant": "NaMaximum.cz",
                    "source_url": ("https://www.namaximum.cz/p/product"
                                   "?variant=" + str(ident)),
                    "ean": str(ident)}
        creatine = {"merchant":"namaximum.cz","merchant_match": True,
                    "products": [
                        offer(392,"Creatine Monohydrate 1kg","Kreatin",800),
                        offer(393,"Creatine Monohydrate 500g","Kreatin",499)]}
        whey = {"merchant":"namaximum.cz","merchant_match": True,
                "products": [
                    offer(482,"Whey WPC 1kg","Syrovátkové proteiny",900),
                    offer(483,"Whey WPI 750g","Syrovátkové proteiny",1000)]}
        for builder, catalog, engine in (
            (creatine_document, creatine, "creatine"),
            (whey_document, whey, "whey"),
        ):
            page = builder(catalog, BASE, SAMPLE)
            parsed = OutboundAttributes()
            parsed.feed(page["content"])
            self.assertGreaterEqual(len(parsed.ctas), 2)
            for cta in parsed.ctas:
                self.assertEqual(cta["data-xfit-engine"], engine)
                self.assertEqual(cta["data-xfit-partner"], "namaximum")
                self.assertTrue(cta["data-xfit-product-id"].isdigit())
                self.assertNotIn("a_aid", " ".join(
                    str(v) for k, v in cta.items() if k.startswith("data-xfit")
                ))
                self.assertIn("sponsored", cta["rel"].split())


if __name__ == "__main__":
    unittest.main()
