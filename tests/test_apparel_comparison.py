import unittest
from scripts.xfit_apparel_comparison import apparel_kind,explicit_size,shortlist,build_document
from scripts.xfit_editorial_gate import check_document
from scripts.wp_publish import PublishError
from test_equipment_comparison import item
from test_plant_comparison import BASE,SAMPLE,catalog

class ApparelTests(unittest.TestCase):
    def test_exact_category_size_and_family_price(self):
        rows=catalog(item(1,"Pánské tričko A M",199,path="shirt-a",category="Pánská trička"),
                     item(2,"Pánské tričko A XL",299,path="shirt-a",category="Pánská trička"),
                     item(3,"Pánská mikina B L",499,category="Pánské mikiny"),
                     item(4,"Fitness legíny C S",399,category="Fitness legíny"),
                     item(5,"Tričko D bez velikosti",99,category="Pánská trička"))
        groups=shortlist(rows,BASE,SAMPLE)
        self.assertEqual(len(groups["shirt"]),1)
        self.assertEqual(groups["shirt"][0]["size"],"M")
        self.assertIsNone(explicit_size("Tričko s potiskem"))
        self.assertIsNone(explicit_size("Tričko M nebo L"))
        doc=build_document(rows,BASE,SAMPLE)
        self.assertEqual(check_document(doc)["product_cards"],3)
        self.assertIn("Velikost v názvu: M",doc["content"])
        self.assertNotIn("Tričko D",doc["content"])
        self.assertNotIn("Pánské tričko A XL",doc["content"])
        self.assertIn("jiné velikosti",doc["content"])
