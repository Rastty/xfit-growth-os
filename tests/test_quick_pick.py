"""The first screen links to real, source-bound offers without a new merchant CTA."""
import unittest
from html.parser import HTMLParser

from scripts.wp_publish import PublishError
from scripts.xfit_quick_pick import quick_pick
from tests.test_price_tradeoff import BASE, SAMPLE, catalog_item
from scripts.xfit_creatine_guide import build_document as creatine
from scripts.xfit_whey_guide import build_document as whey


def offer(ident, title, total, grams, per100):
    return dict(id=str(ident), title=title, price_czk=total,
                mass_g=grams, price_per_100g_powder_czk=per100,
                tracked_url="https://www.namaximum.cz/product")


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
        self.ids = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a":
            self.hrefs.append(a.get("href"))
        if a.get("id"):
            self.ids.append(a["id"])


class QuickPickTests(unittest.TestCase):
    def setUp(self):
        self.items = [
            offer(1, "Výhodné 1000 g", 700, 1000, 70),
            offer(2, "Levné 500 g", 450, 500, 90),
            offer(3, "Dražší 750 g", 900, 750, 120),
        ]

    def test_two_real_choices_and_no_buy_above_comparison(self):
        body = quick_pick(self.items, product_kind="whey")
        self.assertIn('data-xfit-quick-pick="upfront"', body)
        self.assertIn('data-xfit-quick-pick="unit"', body)
        self.assertIn('data-xfit-quick-pick="no-buy"', body)
        self.assertIn('href="#xfit-offer-2"', body)
        self.assertIn('href="#xfit-offer-1"', body)
        self.assertIn('href="#xfit-need"', body)
        self.assertIn("450,00 Kč", body)
        self.assertIn("70,00 Kč", body)
        self.assertIn("ne čistých bílkovin", body)
        self.assertIn("min-height:44px", body)
        self.assertNotIn('href="https://', body)
        self.assertNotIn("<script", body)
        self.assertNotIn("onclick", body)

    def test_same_winner_creates_no_fake_second_product(self):
        items = [offer(1, "Vítěz", 400, 1000, 40),
                 offer(2, "Další", 450, 500, 90)]
        body = quick_pick(items, product_kind="creatine")
        self.assertIn('data-xfit-quick-pick="both"', body)
        self.assertNotIn('data-xfit-quick-pick="upfront"', body)
        self.assertNotIn('data-xfit-quick-pick="unit"', body)
        self.assertEqual(body.count('href="#xfit-offer-'), 1)
        self.assertIn("ne laboratorně potvrzenou", body)

    def test_tainted_name_escaped_and_bad_prices_fail(self):
        items = [dict(self.items[0], title='<script>alert("X")</script>'),
                 self.items[1]]
        body = quick_pick(items, product_kind="whey")
        self.assertIn("&lt;script&gt;", body)
        self.assertNotIn("<script", body)
        for broken in ({"price_czk": "NaN"}, {"mass_g": "500"},
                       {"price_per_100g_powder_czk": 5}, {"id": ""}):
            with self.subTest(broken=broken):
                copied = [dict(row) for row in self.items]
                copied[0].update(broken)
                with self.assertRaises(PublishError):
                    quick_pick(copied, product_kind="whey")
        with self.assertRaises(PublishError):
            quick_pick([self.items[0], dict(self.items[0])], product_kind="whey")

    def test_both_documents_link_only_to_their_rendered_product_cards(self):
        for builder, category, titles in [
            (creatine, "Kreatin", ("Creatine Monohydrate 1kg", "Creatine Monohydrate 500g", "Creatine Monohydrate 750g")),
            (whey, "Syrovátkové proteiny", ("Whey WPC 1kg", "Whey WPC 500g", "Whey WPI 750g")),
        ]:
            with self.subTest(builder=builder.__module__):
                catalog = dict(merchant="namaximum.cz", merchant_match=True,
                               products=[catalog_item(i, title, price, category)
                                         for i, title, price in zip((901, 902, 903), titles, (700, 450, 900))])
                document = builder(catalog, BASE, SAMPLE)["content"]
                self.assertEqual(document.count('id="xfit-rychly-vyber"'), 1)
                self.assertLess(document.index('id="xfit-rychly-vyber"'),
                                document.index('id="xfit-need"'))
                self.assertLess(document.index('id="xfit-rychly-vyber"'),
                                document.index('id="xfit-offers"'))
                fragment = document.split('<section id="xfit-rychly-vyber"', 1)[1].split('</section>', 1)[0]
                links = Anchors()
                links.feed(fragment)
                self.assertEqual(len(links.hrefs), 3)
                self.assertTrue(all(href.startswith("#") for href in links.hrefs))
                all_nodes = Anchors()
                all_nodes.feed(document)
                self.assertTrue(all(href.removeprefix("#") in all_nodes.ids for href in links.hrefs))
                self.assertEqual(document.count('rel="sponsored nofollow'), 3)


if __name__ == "__main__":
    unittest.main()
