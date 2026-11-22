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
        self.decision_summaries = []
        self.in_nav = False
        self.label = None
        self.cards = []
        self.current_card = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.setdefault(attrs["id"], []).append((tag, attrs))
        if tag == "article" and "xfit-product-card" in attrs.get("class", "").split():
            self.current_card = []
            self.cards.append(self.current_card)
        if tag == "a" and self.current_card is not None:
            self.current_card.append(attrs)
        if tag == "summary" and len(self.decision_summaries) < 3:
            self.decision_summaries.append(attrs)
        if tag == "nav":
            self.in_nav = True
            self.label = attrs.get("aria-label")
        if self.in_nav and tag == "a":
            self.shortcuts.append(attrs)

    def handle_endtag(self, tag):
        if tag == "nav":
            self.in_nav = False
        if tag == "article":
            self.current_card = None


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
                # The decision navigation must be the first useful action after
                # the short verdict, before dated catalog details or product CTAs.
                verdict_end = body.index("</p>") + len("</p>")
                nav_start = body.index("<nav ")
                self.assertEqual(body[verdict_end:nav_start].strip(), "")
                self.assertLess(nav_start, body.index("Rozpočet a doprava"))
                self.assertLess(nav_start, body.index('data-xfit-quick-pick="no-buy"'))
                self.assertEqual(body.count('aria-label="Rychlá navigace poradcem"'), 1)
                self.assertEqual(parser.label, "Rychlá navigace poradcem")
                self.assertEqual([a["href"] for a in parser.shortcuts],
                                 ["#xfit-need", "#xfit-vyber-podle-rozpoctu",
                                  "#xfit-offers"])
                for link in parser.shortcuts:
                    self.assertEqual(len(parser.ids[link["href"][1:]]), 1)
                    self.assertNotIn("target", link)
                    self.assertNotIn("onclick", link)
                tag, decision = parser.ids["xfit-need"][0]
                self.assertEqual(tag, "details")
                self.assertIn("open", decision)
                self.assertEqual(len(parser.decision_summaries), 3)
                for summary in parser.decision_summaries:
                    self.assertIn("min-height:44px", summary["style"])
                    self.assertNotIn("role", summary)
                self.assertEqual(parser.ids["xfit-offers"][0][0], "h2")
                # The budget shortcut reaches the decision section before
                # product cards, keeping the reader within their spend limit.
                budget_id = 'id="xfit-vyber-podle-rozpoctu"'
                self.assertEqual(parser.ids["xfit-vyber-podle-rozpoctu"][0][0], "h2")
                self.assertLess(body.index(budget_id), body.index('id="xfit-offers"'))
                self.assertIn("Vybrat podle rozpočtu</a>", body)
                self.assertIn("padding:12px 0", parser.shortcuts[1]["style"])
                self.assertLess(body.index("<nav "), body.index("<details "))
                # The first-screen purchase option explains its affiliate
                # relationship and offers an explicit no-purchase exit first.
                self.assertLess(body.index('může získat provizi'),
                                body.index('rel="sponsored nofollow'))
                self.assertLess(body.index('data-xfit-quick-pick="no-buy"'),
                                body.index('rel="sponsored nofollow'))
                # Every card offers a same-page way to reconsider spending,
                # including after following a budget shortcut down the page.
                self.assertEqual(len(parser.cards), 2)
                for links in parser.cards:
                    returns = [a for a in links if a.get("href") ==
                               "#xfit-vyber-podle-rozpoctu"]
                    self.assertEqual(len(returns), 1)
                    back = returns[0]
                    self.assertNotIn("target", back)
                    self.assertNotIn("onclick", back)
                    self.assertFalse(any(k.startswith("data-") for k in back))
                    self.assertIn("padding:12px 0", back["style"])
                    purchases = [a for a in links if "sponsored" in
                                 a.get("rel", "").split()]
                    self.assertEqual(len(purchases), 1)
                self.assertEqual(body.count("Zpět k výběru podle rozpočtu</a>"), 2)


if __name__ == "__main__":
    unittest.main()
