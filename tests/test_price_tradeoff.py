"""Source-bound price tradeoffs on both actually owned commercial guides."""
import unittest
from html.parser import HTMLParser

from scripts.wp_publish import PublishError
from scripts.xfit_price_tradeoff import price_tradeoff
from scripts.xfit_creatine_guide import build_document as creatine
from scripts.xfit_whey_guide import build_document as whey


BASE = ("https://www.namaximum.cz/?utm_medium=affiliate"
        "&utm_campaign=affial.com&utm_source=pap&a_aid=EXAMPLE&a_bid=DEMO")
SAMPLE = ("https://www.namaximum.cz/kategorie/kreatin/creatine-creapure"
          "?variant=392&utm_medium=affiliate&utm_campaign=affial.com"
          "&utm_source=pap&a_aid=EXAMPLE&a_bid=DEMO")


def selected(ident, title, total, grams, per100):
    return {
        "id": str(ident), "title": title, "price_czk": total,
        "mass_g": grams, "price_per_100g_powder_czk": per100,
        "tracked_url": "https://www.namaximum.cz/p/fake",
    }


def catalog_item(ident, title, total, category):
    return {
        "id":str(ident), "title":title, "price_czk":total,
        "category":category, "merchant":"NaMaximum.cz", "ean":str(ident),
        "source_url":"https://www.namaximum.cz/p/whey?variant="+str(ident),
    }


class ProductLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors=[]
        self.ids=[]

    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=="a" and a.get("href","").startswith("#xfit-offer-"):
            self.anchors.append(a["href"])
        if tag=="article" and a.get("id","").startswith("xfit-offer-"):
            self.ids.append("#"+a["id"])


class TradeoffTests(unittest.TestCase):
    def setUp(self):
        self.cards=[
            selected(101,"Výhodnější velké balení 1 kg",700,1000,70),
            selected(102,"Levnější malé balení 500 g",450,500,90),
            selected(103,"Nevýhodnější balení 750 g",900,750,120),
        ]

    def test_two_source_bound_goals_show_concrete_costs(self):
        body=price_tradeoff(self.cards, product_kind="creatine")
        self.assertIn('data-xfit-tradeoff="upfront"',body)
        self.assertIn('data-xfit-tradeoff="unit"',body)
        self.assertIn('data-xfit-tradeoff="difference"',body)
        self.assertIn('href="#xfit-offer-2"',body)
        self.assertIn('href="#xfit-offer-1"',body)
        self.assertIn("450,00 Kč za celé balení 500 g",body)
        self.assertIn("700,00 Kč za celé balení 1000 g",body)
        self.assertIn("o 250,00 Kč více",body)
        self.assertIn("cenový rozdíl 20,00 Kč",body)
        self.assertIn("nikoli o zaručenou úsporu".casefold(),body.casefold())
        self.assertIn("Nejnižší výdaj při nákupu",body)
        self.assertIn("Nejnižší cena za 100 g prášku",body)
        self.assertNotIn("href=\"https://",body)
        self.assertNotIn("onclick",body)
        self.assertNotIn("<script",body)

    def test_equal_mass_compares_whole_packs_without_implying_same_protein(self):
        # 1x 2kg whey vs 2x 1kg: a comparable amount of powder, but
        # necessarily NOT proof of identical nutrients or shipping.
        cards=[
            selected(201,"Whey 2kg",1699,2000,84.95),
            selected(202,"Whey 1kg",879,1000,87.90),
            selected(203,"Whey alternative 1kg",1000,1000,100),
        ]
        body=price_tradeoff(cards,product_kind="whey")
        self.assertEqual(body.count('data-xfit-tradeoff="same-mass"'),1)
        self.assertIn("2 menší balení po 1000 g",body)
        self.assertIn("1 758,00 Kč",body)
        self.assertIn("1 699,00 Kč",body)
        self.assertIn("59,00 Kč",body)
        self.assertIn("neověřuje stejné složení",body)
        self.assertIn("trvanlivost po otevření",body)
        self.assertIn("ani cenu dopravy",body)
        self.assertNotIn('<a href="https://',body)
        self.assertNotIn("<script",body)

    def test_noninteger_pack_multiple_does_not_claim_fake_equal_mass_savings(self):
        # 1kg versus 400g: 2.5 small packs can't be purchased in reality.
        cards=[
            selected(201,"Creatine 1kg",549,1000,54.9),
            selected(202,"Creatine 400g",269,400,67.25),
        ]
        body=price_tradeoff(cards,product_kind="creatine")
        self.assertIn('data-xfit-tradeoff="difference"',body)
        self.assertNotIn('data-xfit-tradeoff="same-mass"',body)

    def test_more_than_five_small_packs_does_not_promote_bulk_stockpiling(self):
        cards=[
            selected(201,"Creatine 1kg",400,1000,40),
            selected(202,"Creatine 100g",100,100,100),
        ]
        body=price_tradeoff(cards,product_kind="creatine")
        self.assertNotIn('data-xfit-tradeoff="same-mass"',body)

    def test_same_winner_has_no_duplicate_link_or_misleading_saving(self):
        cards=[
            selected(101,"Velké balení 1 kg",400,1000,40),
            selected(102,"Menší balení 500 g",450,500,90)
        ]
        body=price_tradeoff(cards,product_kind="whey")
        self.assertIn('data-xfit-tradeoff="same"',body)
        self.assertEqual(body.count('href="#xfit-offer-1"'),1)
        self.assertNotIn('data-xfit-tradeoff="unit"',body)
        self.assertNotIn('data-xfit-tradeoff="difference"',body)
        self.assertIn("Nejnižší cena za 100 g prášku",body)
        self.assertIn("Nejde o cenu čistých bílkovin",body)

    def test_equal_unit_price_picks_lower_purchase_price(self):
        cards=[
            selected(101,"Velké balení",900,1000,90),
            selected(102,"Malé balení",450,500,90),
        ]
        body=price_tradeoff(cards,product_kind="creatine")
        self.assertIn('href="#xfit-offer-2"',body)
        self.assertEqual(body.count('href="#xfit-offer-'),1)
        self.assertIn('data-xfit-tradeoff="same"',body)

    def test_titles_are_escaped_and_external_urls_absent(self):
        cards=[
            selected(101,'Product "A" & Balance',700,1000,70),
            selected(102,"Product <B> pack",450,500,90),
        ]
        body=price_tradeoff(cards,product_kind="whey")
        self.assertIn("Product &quot;A&quot; &amp; Balance",body)
        self.assertIn("Product &lt;B&gt; pack",body)
        self.assertNotIn("<B>",body)
        self.assertNotIn("https://www.namaximum.cz",body)

    def test_bad_cost_mass_and_identity_fail_before_render(self):
        invalid=[
            {"price_czk":"NaN"}, {"price_czk":"Infinity"},
            {"price_per_100g_powder_czk":"-Infinity"},
            {"price_per_100g_powder_czk":"0"},
            {"price_czk":None}, {"price_czk":True},
            {"mass_g":0}, {"mass_g":"500"}, {"mass_g":False},
            {"title":""}, {"id":""},
        ]
        for mistake in invalid:
            with self.subTest(mistake=mistake):
                cards=[dict(row) for row in self.cards]
                cards[0].update(mistake)
                with self.assertRaises(PublishError):
                    price_tradeoff(cards,product_kind="creatine")
        with self.assertRaises(PublishError):
            price_tradeoff([self.cards[0],dict(self.cards[0])],product_kind="whey")
        with self.assertRaises(PublishError):
            price_tradeoff(self.cards,product_kind="peptides")
        with self.assertRaises(PublishError):
            price_tradeoff(self.cards[:1],product_kind="creatine")

    def test_both_guides_keep_decisions_anchored_to_verified_cards(self):
        for kind,builder,category,titles in [
            ("creatine",creatine,"Kreatin",
                ("Creatine Monohydrate 1kg","Creatine Monohydrate 500g",
                 "Creatine Monohydrate 250g")),
            ("whey",whey,"Syrovátkové proteiny",
                ("Whey WPC 1kg","Whey WPC 500g",
                 "Whey Isolate 750g")),
        ]:
            catalog={
                "merchant":"namaximum.cz",
                "merchant_match":True,
                "products":[
                    catalog_item(901,titles[0],700,category),
                    catalog_item(902,titles[1],450,category),
                    catalog_item(903,titles[2],900,category),
                ]
            }
            with self.subTest(kind=kind):
                body=builder(catalog,BASE,SAMPLE)["content"]
                self.assertEqual(body.count('data-xfit-tradeoff="upfront"'),1)
                self.assertEqual(body.count('data-xfit-tradeoff="unit"'),1)
                self.assertEqual(body.count('data-xfit-tradeoff="difference"'),1)
                self.assertIn("o 250,00 Kč více",body)
                self.assertIn("cenový rozdíl 20,00 Kč",body)
                parsed=ProductLinks()
                parsed.feed(body)
                self.assertEqual(len(parsed.ids),3)
                self.assertTrue(all(a in parsed.ids for a in parsed.anchors))
                self.assertEqual(body.count('rel="sponsored nofollow'),3)
                self.assertIn('id="xfit-vyber-podle-rozpoctu"',body)


if __name__=="__main__":
    unittest.main()
