import unittest
from decimal import Decimal

from scripts.wp_publish import PublishError
from scripts.xfit_model_portions import model_portion_line, model_portion_intro
from scripts.xfit_creatine_guide import build_document as creatine_page
from scripts.xfit_whey_guide import build_document as whey_page

BASE = ("https://www.namaximum.cz/?utm_medium=affiliate"
        "&utm_campaign=affial.com&utm_source=pap"
        "&a_aid=UNITTEST&a_bid=UNITTEST")
SAMPLE = ("https://www.namaximum.cz/kategorie/kreatin/creatine-creapure"
          "?variant=392&utm_medium=affiliate&utm_campaign=affial.com"
          "&utm_source=pap&a_aid=UNITTEST&a_bid=UNITTEST")


def item(ident, title, price, category):
    return {
        "id": str(ident), "title": title, "price_czk": price,
        "category": category, "merchant": "NaMaximum.cz",
        "source_url": "https://www.namaximum.cz/p/product?variant=" + str(ident),
        "ean": str(ident),
    }


class ModelPortionTests(unittest.TestCase):
    def test_creatine_500g_real_price_math(self):
        row = {"price_czk": 430.45, "mass_g": 500}
        rendered = model_portion_line(row, "creatine")
        self.assertIn("166 celých porcí v balení", rendered)
        self.assertIn("2,58 Kč za 3 g prášku", rendered)
        self.assertIn('class="xfit-model-portion"', rendered)
        self.assertNotIn("mg kreatinu", rendered)

    def test_whey_750g_powder_not_actual_protein_content(self):
        row = {"price_czk": 1100, "mass_g": 750}
        rendered = model_portion_line(row, "whey")
        self.assertIn("25 celých porcí", rendered)
        self.assertIn("44,00 Kč za 30 g prášku", rendered)
        self.assertIn("Porce 30 g prášku není 30 g skutečných bílkovin",
                      model_portion_intro("whey"))

    def test_rounding_and_nondivisible_mass_are_transparent(self):
        row = {"price_czk": Decimal("347.55"), "mass_g": 500}
        rendered = model_portion_line(row, "whey")
        self.assertIn("16 celých porcí", rendered)
        self.assertIn("20,85 Kč za 30 g", rendered)
        # The remnant is not allocated to the 16 complete portions.
        self.assertNotIn("21,72", rendered)

    def test_invalid_prices_mass_and_kind_fail_closed(self):
        for bad in ("NaN", "Infinity", "", "abc", "0", "-1", None,
                    True, float("inf")):
            with self.subTest(price=bad), self.assertRaises(PublishError):
                model_portion_line({"price_czk": bad, "mass_g":500}, "whey")
        for bad in (None, True, False, 0, -100, 2, 49, 10001,
                    500.0, "500", 2**63):
            with self.subTest(mass=bad), self.assertRaises(PublishError):
                model_portion_line({"price_czk": 500, "mass_g":bad}, "creatine")
        with self.assertRaises(PublishError):
            model_portion_line({"price_czk": 500, "mass_g":500}, "hormones")
        with self.assertRaises(PublishError):
            model_portion_intro("hormones")

    def test_creatine_and_whey_builders_use_only_actual_selected_cards(self):
        fixtures = (
            (creatine_page, "creatine", [
                item(392, "Creatine Pure Creapure 1kg", 900, "Kreatin"),
                item(393, "Creatine Monohydrate 500g", 430, "Kreatin"),
                item(394, "Kreatin Monohydrat 250g", 270, "Kreatin"),
            ]),
            (whey_page, "whey", [
                item(482, "Whey WPC 1kg", 700, "Syrovátkové proteiny"),
                item(483, "Whey Isolate 750g", 1000, "Syrovátkové proteiny"),
                item(484, "Whey WPC 500g", 450, "Syrovátkové proteiny"),
            ]),
        )
        for build, kind, products in fixtures:
            with self.subTest(kind=kind):
                catalog = {
                    "merchant": "namaximum.cz", "merchant_match": True,
                    "products": products,
                }
                html = build(catalog, BASE, SAMPLE)["content"]
                count = html.count('<article class="xfit-product-card"')
                self.assertGreaterEqual(count, 2)
                self.assertEqual(html.count('class="xfit-model-portion"'), count)
                self.assertEqual(html.count("Zobrazit konkrétní balení na NaMaximum.cz (nová karta)</a>"), count)
                self.assertIn("nejde o doporučen", html.casefold())
                self.assertNotIn("počtu gramů skutečných bílkovin", html)

if __name__ == "__main__":
    unittest.main()
