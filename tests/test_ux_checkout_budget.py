"""Budget limits must not imply a verified delivered checkout total."""
import unittest
from html.parser import HTMLParser

from scripts.xfit_creatine_guide import build_document as creatine_document
from scripts.xfit_whey_guide import build_document as whey_document


class Paragraphs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.paragraphs = []
        self.details_depth = 0
        self.checkout_notice_visible = False
        self.purchase_notice_states = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "details":
            self.details_depth += 1
        if tag == "a" and "sponsored" in attrs.get("rel", "").split():
            self.purchase_notice_states.append(self.checkout_notice_visible)
        if tag == "p":
            self.current = ""

    def handle_data(self, data):
        if self.current is not None:
            self.current += data

    def handle_endtag(self, tag):
        if tag == "details":
            self.details_depth -= 1
        if tag == "p" and self.current is not None:
            self.paragraphs.append(self.current)
            if self.current.startswith("Rozpočet a doprava:"):
                self.checkout_notice_visible = self.details_depth == 0
            self.current = None


class CheckoutBudgetTests(unittest.TestCase):
    def test_both_guides_explain_checkout_costs_before_price_decisions(self):
        # Synthetic offers and campaign IDs; no merchant requests or live data.
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
                     "price_czk": price, "merchant": "NaMaximum.cz",
                     "category": category,
                     "source_url": f"https://www.namaximum.cz/p/example?variant={i}"}
                    for i, mass, price in ((1, 500, 400), (2, 1000, 700))
                ]}
                body = build(catalog, base, sample)["content"]
                parser = Paragraphs()
                parser.feed(body)
                notices = [p for p in parser.paragraphs
                           if p.startswith("Rozpočet a doprava:")]
                self.assertEqual(len(notices), 1)
                self.assertIn("bez dopravy a případných poplatků za platbu", notices[0])
                self.assertIn("Konečnou částku ověřte v košíku prodejce", notices[0])
                self.assertIn("nemusíte nákup dokončit", notices[0])
                self.assertIn("ani přidávat další zboží", notices[0])
                # Include the first-screen merchant CTAs, not only the later
                # budget section: shipping can change the cheapest choice.
                self.assertTrue(parser.purchase_notice_states)
                self.assertTrue(all(parser.purchase_notice_states))
                self.assertLess(body.index("Rozpočet a doprava:"),
                                body.index('id="xfit-price-tradeoff"'))
                self.assertLess(body.index("Rozpočet a doprava:"),
                                body.index('id="xfit-vyber-podle-rozpoctu"'))
