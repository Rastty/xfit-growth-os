import unittest
from scripts.xfit_nut_butter_comparison import nut_butter_kind, shortlist, build_document
from scripts.wp_publish import PublishError
from test_equipment_comparison import item
from test_plant_comparison import BASE,SAMPLE,catalog

class NutButterTests(unittest.TestCase):
    def test_exact_mass_and_group_comparison(self):
        def row(i,title,price,category="Zdravá másla"):
            return item(i,title,price,category=category)
        a=row(1,"Arašídové máslo 500 g",150)
        b=row(2,"Arašídové máslo 250 g",100)
        c=row(3,"Mandlové máslo 200 g",180)
        bad=row(4,"Arašídové máslo bez hmotnosti",5)
        self.assertIsNone(nut_butter_kind(row(5,"Arašídové máslo",5,"Proteiny")))
        groups=shortlist(catalog(a,b,c,bad),BASE,SAMPLE)
        self.assertEqual([x["id"] for x in groups["peanut"]],["1","2"])
        self.assertEqual(str(groups["peanut"][0]["unit_price"]),"30.00")
        doc=build_document(catalog(a,b,c,bad),BASE,SAMPLE)
        self.assertEqual(doc["content"].count('class="xfit-product-card"'),3)
        self.assertIn("za 100 g výrobku",doc["content"])
        self.assertNotIn("bez hmotnosti",doc["content"])
        with self.assertRaises(PublishError):
            build_document(catalog(a,bad),BASE,SAMPLE)
