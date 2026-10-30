import unittest
from scripts.xfit_creatine_guide import (
    build_document, build_tracked_url, shortlist, validate_example,
)
from scripts.wp_publish import PublishError

BASE=("https://www.namaximum.cz/?utm_medium=affiliate&utm_campaign=affial.com"
      "&utm_source=pap&a_aid=TESTAID&a_bid=TESTBID")
SAMPLE=("https://www.namaximum.cz/kategorie/kreatin/creatine-creapure"
        "?variant=392&utm_medium=affiliate&utm_campaign=affial.com"
        "&utm_source=pap&a_aid=TESTAID&a_bid=TESTBID")

def item(id, name, price, mass):
    return {
        "id": str(id), "title": name, "price_czk": price,
        "mass_g":mass,"category":"Kreatin", "merchant":"NaMaximum.cz",
        "ean":str(id),
        "source_url":"https://www.namaximum.cz/kategorie/kreatin/creatine-creapure?variant="+str(id),
        "image_url":"https://greenmedical.bwcdn.net/media/example.jpg",
    }

class CreatineGuideTests(unittest.TestCase):
    def setUp(self):
        self.catalog={"merchant":"namaximum.cz","merchant_match":True,"products":[
            item(392,"Creatine Pure Creapure 1kg",900,1000),
            item(401,"Kreatin Monohydrat 500g",430,500),
            item(402,"Creatine Monohydrate 250g",270,250),
            item(403,"Creatine Monohydrate Complex 500g",180,500),
            item(404,"Creatine Creatine 500g",420,500),
        ]}
    def test_sample(self):
        self.assertTrue(validate_example(BASE,SAMPLE))
    def test_correct_target_and_no_heureka(self):
        link=build_tracked_url(
           "https://www.namaximum.cz/kategorie/kreatin/creatine-creapure?variant=392",
           BASE,SAMPLE)
        self.assertIn("variant=392",link)
        self.assertIn("a_aid=TESTAID",link)
        self.assertNotIn("heureka",link)
    def test_sample_homepage_fails(self):
        with self.assertRaises(ValueError):
            validate_example(BASE,SAMPLE.replace("/kategorie/kreatin/creatine-creapure","/"))
    def test_other_host_fails(self):
        with self.assertRaises(PublishError):
            build_tracked_url("https://other.example/p",BASE,SAMPLE)
    def test_unknown_param_fails(self):
        with self.assertRaises(PublishError):
            build_tracked_url("https://www.namaximum.cz/p?evil=yes",BASE,SAMPLE)
    def test_shortlist_and_transparency(self):
        guide=build_document(self.catalog,BASE,SAMPLE)
        self.assertIn('rel="sponsored nofollow noopener noreferrer"',guide["content"])
        self.assertIn("Cena za 100 g",guide["content"])
        self.assertNotIn("Creatine Monohydrate Complex",guide["content"])
        self.assertGreater(len(guide["content"]),2500)
        self.assertEqual(guide["slug"],"xfit-os-kreatin-poradce")
    def test_insufficient_offers_stop_release(self):
        data={"merchant":"namaximum.cz","merchant_match":True,
              "products":[self.catalog["products"][0]]}
        with self.assertRaises(PublishError):
            build_document(data,BASE,SAMPLE)

    def test_prices_preserve_cents_and_explain_rank(self):
        # Synthetic fixtures: both unit prices used to display as 86 Kč.
        self.catalog["products"] = [
            item(501,"Creatine Monohydrate 500g",430.45,500),
            item(502,"Creatine Monohydrate 250g",215.10,250),
            item(503,"Creatine Pure Creapure 1kg",1100,1000),
        ]
        body=build_document(self.catalog,BASE,SAMPLE)["content"]
        self.assertIn("Cena: 215,10 Kč",body)
        self.assertIn("Cena: 430,45 Kč",body)
        self.assertIn("Cena: 1\u00a0100,00 Kč",body)
        self.assertIn("Cena za 100 g prášku: 86,04 Kč",body)
        self.assertIn("Cena za 100 g prášku: 86,09 Kč",body)
        self.assertIn("Cena za 100 g prášku: 110,00 Kč",body)
        cards=body.split('<article class="xfit-product-card"')[1:]
        self.assertEqual(len(cards),3)
        self.assertIn("Creatine Monohydrate 250g",cards[0])
        self.assertIn("Nejnižší jednotková cena ve výběru",cards[0])
        self.assertIn("Creatine Monohydrate 500g",cards[1])
