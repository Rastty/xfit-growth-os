"""Both advisors must expose the no-purchase path without interaction."""
import unittest
from html.parser import HTMLParser

from scripts.xfit_creatine_guide import build_document as creatine_document
from scripts.xfit_whey_guide import build_document as whey_document


class DecisionParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.questions = []
        self.active = None
        self.events = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "details":
            self.active = {"open": "open" in attrs, "text": ""}
            self.questions.append(self.active)
        if tag == "a" and "sponsored" in attrs.get("rel", "").split():
            self.events.append("purchase")

    def handle_data(self, data):
        if self.active is not None:
            self.active["text"] += data

    def handle_endtag(self, tag):
        if tag == "details":
            self.active = None
            self.events.append("decision")


class NoPurchaseTests(unittest.TestCase):
    def test_no_purchase_answer_is_expanded_before_commercial_choices(self):
        # Synthetic catalog only: no feed, merchant or public-site requests.
        base = ("https://www.namaximum.cz/?utm_medium=affiliate"
                "&utm_campaign=affial.com&utm_source=pap&a_aid=TESTAID&a_bid=TESTBID")
        sample = base.replace("/?", "/p/example?variant=1&")
        for build, name, category, answer in (
            (creatine_document, "Kreatin Monohydrat", "Kreatin", "nekoupit nic"),
            (whey_document, "Whey WPC", "Syrovátkové proteiny", "Ne."),
        ):
            with self.subTest(advisor=name):
                catalog = {"merchant": "namaximum.cz", "merchant_match": True,
                           "products": [
                    {"id": str(i), "title": f"{name} {mass}g", "price_czk": price,
                     "category": category, "merchant": "NaMaximum.cz",
                     "source_url": f"https://www.namaximum.cz/p/example?variant={i}"}
                    for i, mass, price in ((1, 500, 450), (2, 1000, 700))
                ]}
                parser = DecisionParser()
                parser.feed(build(catalog, base, sample)["content"])
                self.assertGreaterEqual(len(parser.questions), 3)
                self.assertTrue(parser.questions[0]["open"])
                self.assertIn(answer, parser.questions[0]["text"])
                self.assertTrue(all(not q["open"] for q in parser.questions[1:3]))
                self.assertIn("purchase", parser.events)
                self.assertLess(parser.events.index("decision"),
                                parser.events.index("purchase"))
