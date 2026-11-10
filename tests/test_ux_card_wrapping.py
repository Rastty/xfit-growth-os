"""Long feed titles must stay readable inside mobile product cards."""
import unittest
from html.parser import HTMLParser

from scripts.xfit_creatine_guide import build_document as creatine_document
from scripts.xfit_whey_guide import build_document as whey_document


class Cards(HTMLParser):
    def __init__(self):
        super().__init__()
        self.styles = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article" and "xfit-product-card" in attrs.get("class", "").split():
            self.styles.append(attrs.get("style", ""))


class CardWrappingTests(unittest.TestCase):
    def test_long_titles_are_preserved_with_intrinsic_width_safe_wrapping(self):
        base = ("https://www.namaximum.cz/?utm_medium=affiliate"
                "&utm_campaign=affial.com&utm_source=pap&a_aid=TEST&a_bid=TEST")
        sample = base.replace(".cz/", ".cz/p/example")
        for build, name, category in (
            (creatine_document, "Creatine Monohydrate", "Kreatin"),
            (whey_document, "Whey WPC", "Syrovátkové proteiny"),
        ):
            with self.subTest(guide=build.__module__):
                long_name = name + " " + "ExtraLongVariant" * 30
                catalog = {"merchant": "namaximum.cz", "merchant_match": True,
                           "products": [
                    {"id": str(i), "title": f"{long_name} {mass}g",
                     "price_czk": price, "category": category,
                     "merchant": "NaMaximum.cz",
                     "source_url": f"https://www.namaximum.cz/p/example?variant={i}"}
                    for i, mass, price in ((1, 500, 400), (2, 1000, 700))
                ]}
                body = build(catalog, base, sample)["content"]
                cards = Cards()
                cards.feed(body)
                self.assertEqual(len(cards.styles), 2)
                for style in cards.styles:
                    self.assertIn("overflow-wrap:anywhere", style)
                    self.assertNotIn("overflow:hidden", style)
                self.assertIn(long_name, body)


if __name__ == "__main__":
    unittest.main()
