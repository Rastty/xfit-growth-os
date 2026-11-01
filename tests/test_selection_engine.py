import unittest
from scripts.xfit_select import mass_grams, matches_kind, select_offers

def offer(name, price, grams=None, id="1", category="Kreatiny", host="www.namaximum.cz"):
    return {
      "id":id, "title":name, "price_czk":price, "category":category,
      "source_url":f"https://{host}/p/example?variant={id}",
      "merchant":"NaMaximum.cz", "ean":id,
    }

class SelectionTests(unittest.TestCase):
    def test_mass_units_and_unknown_mass(self):
        self.assertEqual(mass_grams("Creatine Pure 1kg"), 1000)
        self.assertEqual(mass_grams("Whey 500 g"), 500)
        self.assertEqual(mass_grams("Protein 1,5 kg"), 1500)
        self.assertIsNone(mass_grams("Protein 30 porcí"))
        self.assertIsNone(mass_grams("Creatine dose 5g"))

    def test_creatine_budget_and_price_comparison(self):
        items = [
            offer("Creatine Pure 1kg", 800, id="1"),
            offer("Creatine Monohydrate 500g", 280, id="2"),
            offer("Creatine capsules 1kg", 100, id="3"),
            offer("Creatine Unknown grams", 200, id="4"),
        ]
        ranked = select_offers({"products":items},"creatine",max_price=900)
        self.assertEqual([p["id"] for p in ranked],["2","1"])
        self.assertEqual(ranked[0]["price_per_100g_powder_czk"], 56)
        self.assertFalse(ranked[0]["publish_ready"])
        self.assertIsNone(ranked[0]["affiliate_url"])

    def test_reject_other_merchants_and_duplicates(self):
        items = [
            offer("Creatine 500 g",300,id="2"),
            offer("Creatine 500 g",200,id="2"),
            offer("Creatine 500 g",100,id="3",host="evil.example"),
        ]
        ranked=select_offers({"products":items},"creatine")
        self.assertEqual(len(ranked),1)
        self.assertEqual(ranked[0]["price_czk"],300)

    def test_protein_requires_category_and_powder(self):
        items = [
           offer("Whey protein 1kg",700,id="1",category="Syrovátkové proteiny"),
           offer("Whey protein capsules 1kg",100,id="2",category="Syrovátkové proteiny"),
           offer("Whey protein 1kg",500,id="3",category="Pánské mikiny")
        ]
        ranked=select_offers({"products":items},"whey")
        self.assertEqual(len(ranked),1)
        self.assertEqual(ranked[0]["id"],"1")

    def test_scenario_shortlist_keeps_cheapest_upfront_even_if_not_in_unit_top_six(self):
        from scripts.xfit_select import choose_price_scenarios
        offers = [
            {"id":str(i),"title":f"Option {i}","price_czk":900+i,
             "price_per_100g_powder_czk":45+i} for i in range(7)
        ]
        offers.append({"id":"8","title":"Entry package","price_czk":299,
                       "price_per_100g_powder_czk":59.8})
        selected, value_i, budget_i = choose_price_scenarios(offers)
        self.assertEqual(len(selected),6)
        self.assertEqual(selected[value_i]["id"],"0")
        self.assertEqual(selected[budget_i]["id"],"8")
        self.assertEqual(len({o["id"] for o in selected}),6)

    def test_scenario_shortlist_handles_same_value_and_budget_pick(self):
        from scripts.xfit_select import choose_price_scenarios
        products = [
            {"id":"1","title":"A","price_czk":100,"price_per_100g_powder_czk":20},
            {"id":"2","title":"B","price_czk":200,"price_per_100g_powder_czk":30},
        ]
        selected, value_i, budget_i = choose_price_scenarios(products)
        self.assertEqual((value_i,budget_i),(0,0))
        self.assertEqual(len(selected),2)

    def test_invalid_controls(self):
        with self.assertRaises(ValueError):
            select_offers({"products":[]},"unknown")
        with self.assertRaises(ValueError):
            select_offers({"products":[]},"whey",limit=0)

if __name__=="__main__":
    unittest.main()
