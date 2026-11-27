import unittest
from scripts.xfit_select import matches_kind, select_offers
from scripts.xfit_plant_comparison import build_document, shortlist
from scripts.xfit_editorial_gate import check_document
from scripts.wp_publish import PublishError

BASE = "https://www.namaximum.cz/?utm_medium=affiliate&utm_campaign=affial.com&utm_source=pap&a_aid=DEMO&a_bid=SAMPLE"
SAMPLE = "https://www.namaximum.cz/kategorie/kreatin/creatine-creapure?variant=392&utm_medium=affiliate&utm_campaign=affial.com&utm_source=pap&a_aid=DEMO&a_bid=SAMPLE"

def item(ident, title, price=499, category="Rostlinné proteiny", path=None):
    return {"id": str(ident), "title": title, "price_czk": price, "category": category,
            "source_url": "https://www.namaximum.cz/p/" + (path or str(ident)) + "?variant=" + str(ident),
            "merchant": "NaMaximum.cz", "ean": str(ident), "delivery_date": "0"}

def catalog(*rows):
    return {"merchant": "namaximum.cz", "merchant_match": True, "products": list(rows)}

class PlantComparisonTests(unittest.TestCase):
    def test_accent_and_category_matches(self):
        for title, category in [
            ("Sotein sójový proteinový izolát 500 g", "Rostlinné proteiny"),
            ("BIO Rice Protein - Rýžový protein 1 kg", "Rostlinné"),
            ("BIO Pea Protein - Hrachový protein 500 g", "Proteiny na objem a růst svalů"),
            ("Vegan Protein 500 g", "Veganské proteiny"),
            ("BIO Hemp Protein - Konopný protein 500 g", "Rostlinné proteiny"),
        ]:
            with self.subTest(title=title):
                self.assertTrue(matches_kind(item(1, title, category=category), "plant_protein"))

    def test_not_plant_powder(self):
        for title in ("Vegan vitamíny 500 g", "Sójový protein tyčinka 500 g",
                      "Rýžový protein s whey 500 g", "Hrachový protein kapsle 500 g",
                      "Vegan protein gainer 1 kg", "Vegan protein flour 500 g",
                      "Rostlinný extrakt 500 g", "Hrachový protein s kolagenem 1 kg"):
            with self.subTest(title=title):
                self.assertFalse(matches_kind(item(1, title), "plant_protein"))
        self.assertFalse(matches_kind(item(1, "Vegan Protein 500 g", category="Vitamíny"), "plant_protein"))

    def test_source_bound_cards_and_czech_prices(self):
        data = catalog(item(1, "Sójový protein 500 g", 249, path="soja"),
                       item(2, "Rýžový protein 1 kg", 399, path="ryze"),
                       item(3, "Vegan protein 500 g", 300, path="vegan"),
                       item(4, "Hrachový protein 30 porcí", 100, path="unknown"))
        doc = build_document(data, BASE, SAMPLE)
        body = doc["content"]
        self.assertEqual(check_document(doc)["product_cards"], 3)
        self.assertIn("39,90 Kč", body)
        self.assertIn("249,00 Kč", body)
        self.assertIn("Sójový protein 500 g", body)
        self.assertIn("Rýžový protein 1 kg", body)
        self.assertNotIn("30 porcí", body)
        self.assertEqual(body.count('rel="sponsored nofollow noopener noreferrer"'), 3)
        self.assertIn("variant=2&amp;utm_medium=affiliate", body)
        self.assertIn("prášek nemusíte kupovat", body)
        self.assertIn("není cena za 100 g skutečných bílkovin", body)

    def test_single_family_or_insufficient_data_cannot_publish(self):
        data = catalog(item(1, "Sójový protein 500 g", path="soja"),
                       item(2, "Sójový protein 1 kg", path="soja"))
        self.assertEqual(shortlist(data, BASE, SAMPLE)[1], 1)
        with self.assertRaises(PublishError):
            build_document(data, BASE, SAMPLE)
        unknown = catalog(item(1, "Vegan protein 30 porcí"), item(2, "Rýžový protein 20 porcí"))
        self.assertEqual(select_offers(unknown, "plant_protein", limit=None), [])
        with self.assertRaises(PublishError):
            build_document(unknown, BASE, SAMPLE)

    def test_family_dedupe_and_missing_variant(self):
        data = catalog(item(1, "Sójový protein 500 g", 299, path="soja"),
                       item(2, "Sójový protein 500 g vanilka", 249, path="soja"),
                       item(3, "Rýžový protein 1 kg", 399, path="ryze"))
        rows, families = shortlist(data, BASE, SAMPLE)
        self.assertEqual(families, 2)
        self.assertEqual({row["id"] for row in rows}, {"2", "3"})
        data["products"][2]["source_url"] = "https://www.namaximum.cz/p/ryze?variant=99"
        with self.assertRaises(PublishError):
            build_document(data, BASE, SAMPLE)

if __name__ == "__main__":
    unittest.main()
