"""Published plant-protein guide is a safe, early alternative to whey offers."""
import unittest
from html.parser import HTMLParser

from scripts.xfit_whey_guide import build_document

DEST = "https://xfit.cz/xfit-os-jak-vybrat-rostlinny-protein/"
BASE = ("https://www.namaximum.cz/?utm_medium=affiliate&utm_campaign=affial.com"
        "&utm_source=pap&a_aid=EXAMPLEID&a_bid=EXAMPLEBID")
SAMPLE = ("https://www.namaximum.cz/kategorie/kreatin/creatine-creapure"
          "?variant=392&utm_medium=affiliate&utm_campaign=affial.com"
          "&utm_source=pap&a_aid=EXAMPLEID&a_bid=EXAMPLEBID")


class GuideLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))


class PlantAlternativeHandoffTests(unittest.TestCase):
    def test_visible_alternative_before_first_sponsored_offer(self):
        products = []
        for ident, name, price in (
            (11, "Whey WPC 1kg", 700),
            (12, "Whey Isolate 750g", 1100),
            (13, "Whey Concentrate 500g", 450),
        ):
            products.append({
                "id": str(ident),
                "title": name,
                "price_czk": price,
                "category": "Syrovátkové proteiny",
                "merchant": "NaMaximum.cz",
                "ean": str(ident),
                "source_url": (
                    "https://www.namaximum.cz/p/whey?variant=" + str(ident)),
            })
        doc = build_document({
            "merchant": "namaximum.cz",
            "merchant_match": True,
            "products": products,
        }, BASE, SAMPLE)
        body = doc["content"]
        parsed = GuideLinks()
        parsed.feed(body)
        alternatives = [a for a in parsed.links if a.get("href") == DEST]
        sponsored = [a for a in parsed.links
                     if "sponsored" in a.get("rel", "").split()]
        self.assertEqual(len(alternatives), 1)
        self.assertNotIn("sponsored", alternatives[0].get("rel", "").split())
        self.assertGreater(len(sponsored), 0)
        self.assertLess(body.index('href="' + DEST + '"'),
                        body.index('rel="sponsored'))
        self.assertLess(body.index('id="xfit-milk-allergy"'),
                        body.index('href="' + DEST + '"'))
        self.assertIn("zkontrolujte složení a alergeny", body)
        self.assertIn("nemusíte doplněk kupovat", body)
        self.assertEqual(doc["slug"], "xfit-os-syrovatkovy-protein-porovnani")


if __name__ == "__main__":
    unittest.main()
