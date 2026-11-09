"""Advisor shortcuts work without scripts and keep the no-purchase route first."""
import unittest
from html.parser import HTMLParser

from scripts.xfit_creatine_guide import build_document as creatine_document
from scripts.xfit_whey_guide import build_document as whey_document


class NavigationParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = {}
        self.shortcuts = []
        self.in_nav = False
        self.label = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.setdefault(attrs["id"], []).append((tag, attrs))
        if tag == "nav":
            self.in_nav = True
            self.label = attrs.get("aria-label")
        if self.in_nav and tag == "a":
            self.shortcuts.append(attrs)

    def handle_endtag(self, tag):
        if tag == "nav":
            self.in_nav = False


class GuideNavigationTests(unittest.TestCase):
    def test_shortcuts_resolve_once_and_prioritize_no_purchase(self):
        # Synthetic fixtures only; building HTML never visits these URLs.
        base = ("https://www.namaximum.cz/?utm_medium=affiliate"
                "&utm_campaign=affial.com&utm_source=pap&a_aid=TEST&a_bid=TEST")
        sample = base.replace(".cz/", ".cz/p/example")
        for build, name, category in (
            (creatine_document, "Creatine Monohydrate", "Kreatin"),
            (whey_document, "Whey WPC", "Syrovátkové proteiny"),
        ):
            with self.subTest(guide=build.__module__):
                catalog = {"merchant": "namaximum.cz", "merchant_match": True,
                           "products": [
                    {"id": str(i), "title": f"{name} {mass}g",
                     "price_czk": price, "category": category,
                     "merchant": "NaMaximum.cz",
                     "source_url": f"https://www.namaximum.cz/p/example?variant={i}"}
                    for i, mass, price in ((1, 500, 400), (2, 1000, 700))
                ]}
                body = build(catalog, base, sample)["content"]
                parser = NavigationParser()
                parser.feed(body)
                self.assertEqual(parser.label, "Rychlá navigace poradcem")
                self.assertEqual([a["href"] for a in parser.shortcuts],
                                 ["#xfit-need", "#xfit-offers"])
                for link in parser.shortcuts:
                    self.assertEqual(len(parser.ids[link["href"][1:]]), 1)
                    self.assertNotIn("target", link)
                    self.assertNotIn("onclick", link)
                tag, decision = parser.ids["xfit-need"][0]
                self.assertEqual(tag, "details")
                self.assertIn("open", decision)
                self.assertEqual(parser.ids["xfit-offers"][0][0], "h2")
                self.assertLess(body.index("<nav "), body.index("<details "))
                # Jump lands above disclosure, never directly on a purchase CTA.
                self.assertLess(body.index('id="xfit-offers"'),
                                body.index("provizi"))


if __name__ == "__main__":
    unittest.main()
