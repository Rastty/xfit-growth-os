import unittest
from scripts.xfit_equipment_comparison import equipment_kind, shortlist, build_document
from scripts.wp_publish import PublishError
from scripts.xfit_editorial_gate import check_document
from test_plant_comparison import BASE, SAMPLE, catalog

def item(i, title, price=499, path=None, category="Pomůcky pro cvičení"):
    return {"id": str(i), "title": title, "price_czk": price, "category": category,
            "source_url": "https://www.namaximum.cz/p/" + (path or str(i)) + "?variant=" + str(i),
            "merchant": "NaMaximum.cz", "ean": str(i), "delivery_date": "0"}

class EquipmentTests(unittest.TestCase):
    def test_explicit_category_and_purpose(self):
        for title, expected in (("Podložka na cvičení Yoga Mat Pink", "mat"),
                                ("Booty Band posilovací guma", "band"),
                                ("Tiguar Power Band GT – Expander", "band"),
                                ("Masážní válec", None), ("Fitness stahovací pás", None),
                                ("Ochranná podložka pod stroj", None),
                                ("Náhradní držák pro odporové gumy", None)):
            self.assertEqual(equipment_kind(item(1, title)), expected)
        self.assertIsNone(equipment_kind(item(2, "Yoga Mat", category="Vitamíny")))
    def test_separate_purpose_price_and_exact_links(self):
        rows = catalog(item(1, "Yoga Mat", 499), item(2, "Podložka na cvičení", 349),
                       item(3, "Booty Band", 549), item(4, "Odporová guma", 299))
        doc = build_document(rows, BASE, SAMPLE)
        self.assertEqual(check_document(doc)["product_cards"], 4)
        self.assertIn("349,00 Kč", doc["content"])
        self.assertIn("299,00 Kč", doc["content"])
        self.assertEqual(doc["content"].count('rel="sponsored nofollow noopener noreferrer"'), 4)
        self.assertIn("variant=3&amp;utm_medium=affiliate", doc["content"])
        self.assertIn("nekupujte nic", doc["content"])
    def test_conflicts_and_unavailable_excluded(self):
        first = item(1, "Yoga Mat", 499)
        band = item(2, "Booty Band", 549)
        rows = catalog(first, dict(first, price_czk=3000), band)
        with self.assertRaises(PublishError):
            build_document(rows, BASE, SAMPLE)
        rows = catalog(first, dict(band, delivery_date="10"))
        with self.assertRaises(PublishError):
            build_document(rows, BASE, SAMPLE)
    def test_dedupes_product_family_without_inventing_pack_units(self):
        rows = catalog(item(1, "Yoga Mat Blue", 499, path="mat"),
                       item(2, "Yoga Mat Pink", 449, path="mat"),
                       item(3, "Resistance Band", 549))
        result = shortlist(rows, BASE, SAMPLE)
        self.assertEqual([r["id"] for r in result["mat"]], ["2"])
        self.assertEqual(len(result["band"]), 1)
        self.assertIn("nikoli nutně za jeden kus", build_document(rows, BASE, SAMPLE)["content"])

    def test_optional_ball_and_massage_are_separate_and_feed_bound(self):
        rows = catalog(item(1, "Yoga Mat", 499), item(2, "Resistance Band", 549),
                       item(3, "Fitball 85 cm – Muscle Aggressive", 369),
                       item(4, "Masážní sada Muscle Ball and Roller Set Black 4 ks – Muscle Aggressive", 499),
                       item(5, "Pumpa na Fitball 85 cm", 100))
        doc = build_document(rows, BASE, SAMPLE)
        self.assertEqual(check_document(doc)["product_cards"], 4)
        self.assertIn('id="xfit-gear-ball"', doc["content"])
        self.assertIn('id="xfit-gear-massage"', doc["content"])
        self.assertIn("1\u00a0048,00 Kč", doc["content"])
        self.assertNotIn("Pumpa na", doc["content"])
        self.assertEqual(len(shortlist(rows, BASE, SAMPLE)["ball"]), 1)
        self.assertNotIn('id="xfit-gear-ball"', build_document(catalog(item(1,"Yoga Mat"),item(2,"Resistance Band")),BASE,SAMPLE)["content"])
    def test_budget_is_exact_sum_and_preserves_no_buy(self):
        from scripts.xfit_equipment_comparison import budget_block,shortlist
        rows=catalog(item(1,"Yoga Mat",499),item(2,"Resistance Band",549))
        b=budget_block(shortlist(rows,BASE,SAMPLE))
        self.assertIn("1\u00a0048,00 Kč",b)
        self.assertIn("0 Kč",b)
        self.assertIn("ne cena akčního setu",b)

if __name__ == "__main__":
    unittest.main()
