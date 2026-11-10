"""Feed title ambiguity must never silently distort CZK per 100 g rankings."""
import unittest

from scripts.xfit_select import mass_grams, select_offers


def item(ident, title, price, category):
    return {
        "id": str(ident),
        "title": title,
        "price_czk": price,
        "category": category,
        "merchant": "NaMaximum.cz",
        "source_url": "https://www.namaximum.cz/p/example?variant=" + str(ident),
        "ean": str(ident),
    }


class SourceBoundMassTests(unittest.TestCase):
    def test_single_verified_pack_weight_still_parses(self):
        cases = {
            "Creatine Monohydrate Natural 1kg": 1000,
            "Whey WPC 500 g Vanilla": 500,
            "Whey WPI 1,5 kg": 1500,
            "Creatine 1 kg (serving 5g)": 1000,
            "Whey WPC 1kg (porce 30g)": 1000,
        }
        for title, grams in cases.items():
            with self.subTest(title=title):
                self.assertEqual(mass_grams(title), grams)

    def test_multiple_plausible_different_weights_are_not_rankable(self):
        cases = (
            "Whey WPC 1kg - 100g protein per serving",
            "Creatine Pure 500g + 100g zdarma",
            "Whey 1 kg / 500 g bonus",
            "Creatine monohydrate 100 g or 500 g",
        )
        for title in cases:
            with self.subTest(title=title):
                self.assertIsNone(mass_grams(title))

    def test_multipack_is_not_mistaken_for_single_pack(self):
        for title in (
            "Whey WPC 2x500g",
            "Whey WPC 2 x 500 g",
            "Whey WPC 2×500g",
            "Whey WPC 2*500g",
            "Creatine 2 x Natural 500g",
        ):
            with self.subTest(title=title):
                self.assertIsNone(mass_grams(title))

    def test_creatine_and_whey_price_selection_excludes_ambiguous_titles(self):
        for kind, category, product in (
            ("creatine", "Kreatin", "Creatine Monohydrate"),
            ("whey", "Syrovátkové proteiny", "Whey WPC"),
        ):
            offers = [
                item(1, product + " 500g", 400, category),
                item(2, product + " 1kg", 700, category),
                # Would be incorrectly ranked if 500g were read as 100g.
                item(3, product + " 500g + 100g extra", 220, category),
                # Would be incorrectly ranked as a 500g single package.
                item(4, product + " 2x500g", 500, category),
                item(5, product + " 1kg serving 5g", 750, category),
            ]
            selected = select_offers(
                {"products": offers}, kind, min_mass_g=200
            )
            with self.subTest(kind=kind):
                self.assertEqual({p["id"] for p in selected}, {"1", "2", "5"})
                self.assertTrue(all(p["mass_g"] >= 500 for p in selected))
                self.assertEqual(
                    next(p for p in selected if p["id"] == "5")["mass_g"], 1000
                )


if __name__ == "__main__":
    unittest.main()
