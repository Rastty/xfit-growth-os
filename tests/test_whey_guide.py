import unittest
from scripts.xfit_whey_guide import build_document, kind_label
from scripts.wp_publish import PublishError

BASE=("https://www.namaximum.cz/?utm_medium=affiliate&utm_campaign=affial.com"
      "&utm_source=pap&a_aid=EXAMPLEID&a_bid=EXAMPLEBID")
SAMPLE=("https://www.namaximum.cz/kategorie/kreatin/creatine-creapure"
        "?variant=392&utm_medium=affiliate&utm_campaign=affial.com"
        "&utm_source=pap&a_aid=EXAMPLEID&a_bid=EXAMPLEBID")

def offer(id,name,price,category="Syrovátkové proteiny"):
    return {"id":str(id),"title":name,"price_czk":price,
            "category":category,"merchant":"NaMaximum.cz",
            "ean":str(id),"source_url":"https://www.namaximum.cz/p/whey?variant="+str(id)}
class WheyTests(unittest.TestCase):
    def setUp(self):
        self.catalog={"merchant":"namaximum.cz","merchant_match":True,"products":[
            offer(11,"Whey WPC 1kg",700),
            offer(12,"Whey Isolate 750g",1100),
            offer(13,"Whey Concentrate 500g",450),
            offer(14,"Whey gainer 1kg",400,"Proteiny na objem a růst svalů")
        ]}
    def test_whey_document(self):
        doc=build_document(self.catalog,BASE,SAMPLE)
        self.assertEqual(doc["slug"],"xfit-os-syrovatkovy-protein-porovnani")
        self.assertIn("Ceny se mohou měnit",doc["content"])
        self.assertIn('rel="sponsored nofollow noopener noreferrer"',doc["content"])
        self.assertNotIn("Whey gainer",doc["content"])
    def test_type_labels(self):
        self.assertIn("izolát",kind_label("Whey WPI").lower())
        self.assertIn("koncentrát",kind_label("Whey WPC").lower())
    def test_prices_preserve_cents_and_explain_rank(self):
        # Synthetic prices: both unit prices previously displayed as 70 Kč.
        self.catalog["products"] = [
            offer(21,"Whey WPC 1kg",695.40),
            offer(22,"Whey WPC 500g",347.55),
            offer(23,"Whey Isolate 750g",1100),
        ]
        body=build_document(self.catalog,BASE,SAMPLE)["content"]
        self.assertIn("Cena: 347,55 Kč",body)
        self.assertIn("Cena: 695,40 Kč",body)
        self.assertIn("Cena: 1\u00a0100,00 Kč",body)
        self.assertIn("Cena za 100 g prášku: 69,51 Kč",body)
        self.assertIn("Cena za 100 g prášku: 69,54 Kč",body)
        self.assertIn("Cena za 100 g prášku: 146,67 Kč",body)
        self.assertLess(body.index("Cena: 347,55 Kč"),body.index("Cena: 695,40 Kč"))
    def test_insufficient_catalog(self):
        with self.assertRaises(PublishError):
            build_document({"merchant":"namaximum.cz","merchant_match":True,"products":[]},BASE,SAMPLE)
