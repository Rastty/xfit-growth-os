"""Readers see the single-merchant limitation before any purchase link."""
import unittest
from html.parser import HTMLParser

from scripts.xfit_creatine_guide import build_document as creatine_document
from scripts.xfit_whey_guide import build_document as whey_document


class ScopeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden_depth = 0
        self.paragraph = None
        self.notices = []
        self.purchase_states = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "details":
            self.hidden_depth += 1
        if tag == "p":
            self.paragraph = ""
        if tag == "a" and "sponsored" in attrs.get("rel", "").split():
            self.purchase_states.append(bool(self.notices))

    def handle_data(self, data):
        if self.paragraph is not None:
            self.paragraph += data

    def handle_endtag(self, tag):
        if tag == "details":
            self.hidden_depth -= 1
        if tag == "p" and self.paragraph is not None:
            if self.paragraph.startswith("Rozsah srovnání:"):
                self.notices.append((self.paragraph, self.hidden_depth))
            self.paragraph = None


class ComparisonScopeTests(unittest.TestCase):
    def test_visible_scope_precedes_all_sponsored_choices(self):
        # Synthetic catalog and tracking identifiers; no network requests.
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
                parser = ScopeParser()
                parser.feed(build(catalog, base, sample)["content"])
                self.assertEqual(len(parser.notices), 1)
                text, depth = parser.notices[0]
                self.assertEqual(depth, 0)
                self.assertIn("jediného prodejce, NaMaximum.cz", text)
                self.assertIn("nikoli z celého trhu", text)
                self.assertIn("není nezávislý test kvality ani účinnosti", text)
                self.assertIn("stejné balení i u jiných prodejců", text)
                self.assertTrue(parser.purchase_states)
                self.assertTrue(all(parser.purchase_states))
