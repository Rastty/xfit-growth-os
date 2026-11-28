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
        self.assertIn("Pánské tričko A XL",doc["content"])
        self.assertIn('data-xfit-size="XL"',doc["content"])
        self.assertIn("299,00 Kč",doc["content"])
        self.assertIn("jiné velikosti",doc["content"])

    def test_size_selection_excludes_conflicting_identity_and_unavailable(self):
        from scripts.xfit_apparel_comparison import eligible_variants,size_shortlist
        a=item(1,"Pánské tričko A S",199,category="Pánská trička")
        b=item(2,"Pánské tričko B S",299,category="Pánská trička")
        c=item(3,"Pánské tričko C M",99,category="Pánská trička")
        data=catalog(a,dict(a,price_czk=999),b,dict(c,delivery_date="10"))
        sizes=size_shortlist(eligible_variants(data,BASE,SAMPLE))
        self.assertEqual(sizes["shirt"]["S"]["id"],"2")
        self.assertNotIn("M",sizes["shirt"])

    def test_sports_bra_requires_exact_category_and_product_type(self):
        category="Sportovní podprsenky a topy"
        bra=item(21,"Sportovní podprsenka A S",399,category=category)
        self.assertEqual(apparel_kind(bra),"bra")
        self.assertEqual(apparel_kind(item(22,"Fitness top S",199,category=category)),"top")
        self.assertIsNone(apparel_kind(item(27,"Sportovní podprsenka fitness top S",199,category=category)))
        self.assertIsNone(apparel_kind(item(28,"Fitness top S",199,category="Pánská trička")))
        self.assertIsNone(apparel_kind(item(23,"Sportovní podprsenka S",199,category="Pánská trička")))
        self.assertIsNone(apparel_kind(item(24,"Sportovní podprsenka bez velikosti",199,category=category)))
        doc=build_document(catalog(bra,item(25,"Sportovní podprsenka B M",599,category=category),
             item(26,"Fitness legíny C S",399,category="Fitness legíny")),BASE,SAMPLE)
        self.assertIn('id="xfit-apparel-bra"',doc["content"])
        self.assertIn('id="xfit-size-picker-bra"',doc["content"])
        self.assertEqual(check_document(doc)["product_cards"],3)
