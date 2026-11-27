import unittest
from scripts.xfit_drinkware_comparison import drinkware_kind,shortlist,build_document
from scripts.wp_publish import PublishError
from scripts.xfit_editorial_gate import check_document
from test_equipment_comparison import item
from test_plant_comparison import BASE,SAMPLE,catalog

def row(i,title,price=75,path=None,category="Šejkry a láhve"):
    return item(i,title,price,path=path,category=category)

class DrinkwareTests(unittest.TestCase):
    def test_strict_designation_and_category(self):
        for title,expected in (("Smart Šejkr Warrior vícedílný 600ml + 350ml","shaker"),
                               ("Shaker NaMaximum 600ml","shaker"),("Láhev Endurance 750ml","bottle"),
                               ("Proteinový MIX se shakerem",None),("Náhradní víčko pro shaker",None),
                               ("Shaker náhradní víčko",None),("Kosmetika v lahvi",None)):
            self.assertEqual(drinkware_kind(row(1,title)),expected)
        self.assertIsNone(drinkware_kind(row(1,"Shaker",category="Proteiny")))
    def test_real_family_price_and_disclosure(self):
        rows=catalog(row(1,"Shaker A",74,path="shaker-a"),row(2,"Shaker A modrý",75,path="shaker-a"),
                     row(3,"Šejkr B",119),row(4,"Láhev C",75))
        doc=build_document(rows,BASE,SAMPLE)
        self.assertEqual(check_document(doc)["product_cards"],3)
        self.assertIn("74,00 Kč",doc["content"])
        self.assertIn("nekupujte novou",doc["content"])
        self.assertEqual(doc["content"].count('rel="sponsored nofollow noopener noreferrer"'),3)
        self.assertEqual([x["id"] for x in shortlist(rows,BASE,SAMPLE)["shaker"]],["1","3"])
    def test_conflict_and_dispatch_fail_closed(self):
        a,b,c=row(1,"Shaker A"),row(2,"Shaker B"),row(3,"Láhev C")
        for rows in (catalog(a,dict(a,price_czk=2000),b,c),catalog(a,b,dict(c,delivery_date="10"))):
            with self.assertRaises(PublishError):
                build_document(rows,BASE,SAMPLE)
