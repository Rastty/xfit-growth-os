"""The first screen reaches exactly the source-bound merchant cards in one click."""
import unittest
from html.parser import HTMLParser

from scripts.wp_publish import PublishError
from scripts.xfit_quick_pick import quick_pick
from tests.test_price_tradeoff import BASE, SAMPLE, catalog_item
from scripts.xfit_creatine_guide import build_document as creatine
from scripts.xfit_whey_guide import build_document as whey
from scripts import xfit_affiliate_public_audit as public_audit


def offer(ident, title, total, grams, per100):
    return dict(id=str(ident), title=title, price_czk=total,
                mass_g=grams, price_per_100g_powder_czk=per100,
                tracked_url=("https://www.namaximum.cz/product?variant=" + str(ident) +
                             "&utm_medium=affiliate&utm_campaign=affial.com"
                             "&utm_source=pap&a_aid=EXAMPLEID&a_bid=EXAMPLEBID"))


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
        self.assertEqual(body.count('data-xfit-cta="quick-pick"'), 2)
        self.assertEqual(body.count('rel="sponsored nofollow noopener noreferrer"'), 2)
        self.assertEqual(body.count('target="_blank"'), 2)
        self.assertIn("může získat provizi", body)
        self.assertIn("450,00 Kč", body)
        self.assertIn("70,00 Kč", body)
        self.assertIn("ne čistých bílkovin", body)
        self.assertIn('href="https://xfit.cz/xfit-os-cena-proteinu-podle-etikety/"', body)
        self.assertLess(body.index('postup přepočtu ceny podle nutriční etikety'),
                        body.index('data-xfit-cta="quick-pick"'))
        self.assertIn("min-height:44px", body)
        self.assertIn('href="https://www.namaximum.cz/product?variant=2', body)
        self.assertNotIn("<script", body)
        self.assertNotIn("onclick", body)

    def test_visible_affiliate_disclosure_satisfies_live_hero_audit(self):
        # The production audit requires both plain-language affiliate labelling
        # and commission disclosure *inside* the early-purchase section.
        # Checking only the full page missed this failure in the live workflow.
        for kind, slug in (
            ("creatine", "xfit-os-kreatin-poradce"),
            ("whey", "xfit-os-syrovatkovy-protein-porovnani"),
        ):
            with self.subTest(kind=kind):
                items = [dict(item) for item in self.items]
                if kind == "creatine":
                    for item in items:
                        item["tracked_url"] += "&data1=xfit&data2=creatine"
                markup = quick_pick(items, product_kind=kind)
                parser = public_audit.QuickPicks()
                parser.feed(markup)
                visible = " ".join(parser.copy).casefold()
                self.assertIn("affiliate", visible)
                self.assertIn("provizi", visible)
                # The same production validation rule must stay satisfied
                # even if the wording above the hero section changes.
                self.assertEqual(parser.sections, 1)
                self.assertEqual(len(parser.links), 2)
                self.assertTrue(parser.no_buy_link)
                card_signature = [
                    (link["product_id"], link["engine"], link["partner"],
                     public_audit.comparable_href(link["href"]))
                    for link in parser.links
                ]
                evidence = public_audit.quick_pick_evidence(
                    markup, slug, items[0]["tracked_url"], card_signature,
                )
                self.assertEqual(evidence["errors"], [])
                unsafe = markup.replace("affiliate", "partnerské")
                evidence = public_audit.quick_pick_evidence(
                    unsafe, slug, items[0]["tracked_url"], card_signature,
                )
                self.assertIn("missing_quick_pick_disclosure", evidence["errors"])

    def test_same_winner_creates_no_fake_second_product(self):
        items = [offer(1, "Vítěz", 400, 1000, 40),
                 offer(2, "Další", 450, 500, 90)]
        body = quick_pick(items, product_kind="creatine")
        self.assertIn('data-xfit-quick-pick="both"', body)
        self.assertNotIn('data-xfit-quick-pick="upfront"', body)
        self.assertNotIn('data-xfit-quick-pick="unit"', body)
        self.assertEqual(body.count('href="#xfit-offer-'), 1)
        self.assertEqual(body.count('data-xfit-cta="quick-pick"'), 1)
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

    def test_quick_pick_rejects_untracked_or_cross_product_merchant_destinations(self):
        base = self.items[0]["tracked_url"]
        for bad in (
            base.replace("www.namaximum.cz", "namaximum.cz.evil.example"),
            base.replace("variant=1", "variant=2"),
            base.replace("a_aid=EXAMPLEID", "a_aid="),
            base.replace("utm_medium=affiliate", "utm_medium=cpc"),
            base.replace("&a_bid=EXAMPLEBID", ""),
            base + "&variant=1",
            base.replace("https://", "http://"),
            base.replace("/product?", "/?"),
            base + "&redirect=https://evil.example",
        ):
            with self.subTest(bad=bad):
                copied = [dict(row) for row in self.items]
                copied[0]["tracked_url"] = bad
                with self.assertRaises(PublishError):
                    quick_pick(copied, product_kind="creatine")

    def test_creatine_origin_pilot_requires_exact_pair_and_never_leaks_to_whey(self):
        valid = [dict(item) for item in self.items]
        valid[0]["tracked_url"] += "&data1=xfit&data2=creatine"
        valid[1]["tracked_url"] += "&data1=xfit&data2=creatine"
        valid[2]["tracked_url"] += "&data1=xfit&data2=creatine"
        self.assertEqual(quick_pick(valid, product_kind="creatine").count(
            'data-xfit-cta="quick-pick"'), 2)
        for kind, url in (
            ("creatine", self.items[0]["tracked_url"] + "&data1=xfit"),
            ("creatine", self.items[0]["tracked_url"] + "&data2=creatine"),
            ("creatine", self.items[0]["tracked_url"] + "&data1=other&data2=creatine"),
            ("creatine", self.items[0]["tracked_url"] + "&data1=xfit&data2=whey"),
            ("creatine", self.items[0]["tracked_url"] + "&data1=xfit&data2=creatine&data1=xfit"),
            ("whey", self.items[0]["tracked_url"] + "&data1=xfit&data2=creatine"),
        ):
            with self.subTest(kind=kind, url=url):
                bad = [dict(item) for item in self.items]
                bad[0]["tracked_url"] = url
                with self.assertRaises(PublishError):
                    quick_pick(bad, product_kind=kind)

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
                # A useful offer must be discoverable before the navigation
                # list and long method/price explanation, not hundreds of
                # words down the page.
                self.assertLess(document.index('id="xfit-rychly-vyber"'), 1250)
                self.assertLess(document.index('id="xfit-rychly-vyber"'),
                                document.index('<nav aria-label="Rychlá navigace poradcem"'))
                if 'Kdy jsme data nabídky načetli' in document:
                    self.assertLess(document.index('Kdy jsme data nabídky načetli'),
                                    document.index('id="xfit-rychly-vyber"'))
                self.assertLess(document.index('id="xfit-rychly-vyber"'),
                                document.index('id="xfit-need"'))
                self.assertLess(document.index('id="xfit-rychly-vyber"'),
                                document.index('id="xfit-offers"'))
                if builder is whey:
                    self.assertLess(document.index('id="xfit-milk-allergy"'),
                                    document.index('id="xfit-rychly-vyber"'))
                    self.assertLess(document.index('id="xfit-rychly-vyber"'),
                                    document.index('href="https://xfit.cz/xfit-os-cena-proteinu-podle-etikety/"'))
                else:
                    self.assertLess(document.index('Zdravotní omezení:'),
                                    document.index('id="xfit-rychly-vyber"'))
                fragment = document.split('<section id="xfit-rychly-vyber"', 1)[1].split('</section>', 1)[0]
                links = Anchors()
                links.feed(fragment)
                self.assertEqual(len(links.hrefs), 6 if builder is whey else 5)
                internal = [href for href in links.hrefs if href.startswith("#")]
                external = [href for href in links.hrefs if href.startswith("https://")]
                self.assertEqual(len(internal), 3)
                self.assertEqual(len(external), 3 if builder is whey else 2)
                if builder is whey:
                    self.assertEqual(external.count(
                        "https://xfit.cz/xfit-os-cena-proteinu-podle-etikety/"), 1)
                all_nodes = Anchors()
                all_nodes.feed(document)
                self.assertTrue(all(href.removeprefix("#") in all_nodes.ids for href in internal))
                self.assertEqual(document.count('rel="sponsored nofollow'), 5)
                if builder is whey:
                    self.assertNotIn("data1=", document)
                    self.assertNotIn("data2=", document)
                else:
                    self.assertEqual(document.count("data1=xfit"), 5)
                    self.assertEqual(document.count("data2=creatine"), 5)


if __name__ == "__main__":
    unittest.main()
