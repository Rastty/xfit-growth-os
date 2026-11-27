import unittest
from scripts.xfit_nut_butter_comparison import build_document,shortlist
from scripts.xfit_select import nut_butter
from scripts.wp_publish import PublishError
from test_equipment_comparison import item
from test_plant_comparison import BASE,SAMPLE,catalog

def row(i,title,price=100,path=None,category="Zdravá másla"):
    return item(i,title,price,path=path,category=category)

class NutButterTests(unittest.TestCase):
    def test_exact_kind_and_price_choices(self):
        rows=catalog(row(1,"Arašídové máslo 500 g",150,path="a"),row(2,"Mandlové máslo 250 g",90,path="b"),row(3,"Peanut Butter powder 500 g",20,path="c"))
        self.assertFalse(nut_butter(rows["products"][2]))
        doc=build_document(rows,BASE,SAMPLE)["content"]
        self.assertEqual(doc.count('class="xfit-product-card"'),2)
        self.assertIn("30,00 Kč",doc)
        self.assertIn("90,00 Kč",doc)
        self.assertNotIn("powder",doc)
        self.assertIn("za 100 g výrobku",doc)
        with self.assertRaises(PublishError):
            build_document(catalog(rows["products"][0],dict(rows["products"][1],delivery_date="20")),BASE,SAMPLE)
