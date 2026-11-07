import unittest

from scripts.xfit_budget_choices import budget_choices
from scripts.wp_publish import PublishError


def offer(ident, title, total, per100, grams=500):
    return {"id": str(ident), "title": title, "price_czk": total,
            "price_per_100g_powder_czk": per100, "mass_g": grams,
            "tracked_url": "https://www.namaximum.cz/demo"}


class BudgetChoicesTests(unittest.TestCase):
    def setUp(self):
        # In same order as the verified xfit-offer-N cards: lowest per100 first.
        self.cards = [
            offer(102, "Creatine velké balení", 1300, 50, 1000),
            offer(101, "Creatine střední balení", 900, 60, 750),
            offer(100, "Creatine malé balení", 450, 90, 500),
        ]

    def test_budget_ceiling_recommends_actual_matching_card_anchor(self):
        result = budget_choices(self.cards, (500, 1000, 1500),
                                product_kind="creatine")
        self.assertEqual(result.count("<details>"), 3)
        self.assertEqual(result.count("</details>"), 3)
        self.assertIn("Do 500 Kč — 1 nabídka", result)
        self.assertIn("Do 1000 Kč — 2 nabídky", result)
        self.assertIn("Do 1500 Kč — 3 nabídky", result)
        self.assertIn('href="#xfit-offer-3"', result)
        self.assertIn('href="#xfit-offer-2"', result)
        self.assertIn('href="#xfit-offer-1"', result)
        self.assertIn("450,00 Kč", result)
        self.assertIn("60,00 Kč za 100 g prášku", result)
        self.assertNotIn("nejlevnější na trhu", result)
        self.assertNotIn("https://www.namaximum.cz", result)
        self.assertNotIn("<script", result)
        self.assertIn("pokud jej nepotřebujete, nekupujte jej", result.casefold())

    def test_same_best_product_across_multiple_budgets_has_unique_helpful_copy(self):
        # The live creatine selection may be expensive enough that only one
        # product fits all thresholds; editorial gate must not reject the
        # legitimate same recommendation as duplicated filler.
        cards = [
            offer(901, "Creatine velké 1 kg", 490, 49, 1000),
            offer(902, "Creatine menší 500 g", 850, 170, 500),
        ]
        output = budget_choices(cards, (500, 1000, 1500),
                                product_kind="creatine")
        self.assertEqual(output.count('href="#xfit-offer-1"'), 3)
        for limit in (500, 1000, 1500):
            self.assertIn("V limitu do " + str(limit) + " Kč", output)
        from scripts.xfit_editorial_gate import Inspector
        import re
        checker = Inspector()
        checker.feed(output)
        normalized = [
            re.sub(r"\\W+", " ", p.casefold()).strip()
            for p in checker.paragraphs if len(p) > 110
        ]
        self.assertEqual(len(normalized), len(set(normalized)))

    def test_no_offer_in_budget_explicitly_admits_limit_and_no_purchase(self):
        result = budget_choices(self.cards, (300, 500), product_kind="creatine")
        self.assertIn("Do 300 Kč — 0 nabídek", result)
        self.assertIn("žádná nabídka do 300 Kč není", result)
        self.assertIn("To neznamená, že na trhu žádná neexistuje", result)
        self.assertEqual(result.count('href="#xfit-offer-'), 1)

    def test_whey_explains_powder_is_not_protein_and_no_nutrient_claim(self):
        selected = [
            offer(201, 'Whey "Natural" & WPC', 1100, 70),
            offer(202, "Whey Isolate", 650, 110),
        ]
        result = budget_choices(selected, (750, 1200), product_kind="whey")
        self.assertIn('Whey &quot;Natural&quot; &amp; WPC', result)
        self.assertIn("nikoli množství skutečných bílkovin", result)
        self.assertIn('href="#xfit-offer-2"', result)
        self.assertIn('href="#xfit-offer-1"', result)
        self.assertNotIn("proteinů na 100", result)

    def test_fraudulent_or_missing_catalog_prices_fail_closed(self):
        for invalid in ("NaN", "Infinity", "0", "-4", None, True, "abc", 0):
            with self.subTest(price=invalid):
                cards = [dict(x) for x in self.cards]
                cards[0]["price_czk"] = invalid
                with self.assertRaises(PublishError):
                    budget_choices(cards, (500, 1500), product_kind="creatine")
        for invalid in ("NaN", float("inf"), -1, 0, "broken"):
            with self.subTest(per100=invalid):
                cards = [dict(x) for x in self.cards]
                cards[0]["price_per_100g_powder_czk"] = invalid
                with self.assertRaises(PublishError):
                    budget_choices(cards, (500, 1500), product_kind="creatine")

    def test_invalid_configuration_and_duplicate_offers_rejected(self):
        for levels in ((1500, 500), (500, 500), (500, "1000"), [500, 1000],
                       (), (True, 500)):
            with self.subTest(levels=levels), self.assertRaises(PublishError):
                budget_choices(self.cards, levels, product_kind="creatine")
        with self.assertRaises(PublishError):
            budget_choices(self.cards, (500, 1500), product_kind="peptides")
        duplicates = [dict(self.cards[0]), dict(self.cards[0])]
        with self.assertRaises(PublishError):
            budget_choices(duplicates, (500, 1500), product_kind="creatine")

    def test_equal_unit_prices_use_total_then_card_order(self):
        cards = [
            offer(1, "Velké", 1200, 80),
            offer(2, "Levnější", 700, 80),
            offer(3, "Dražší", 1400, 80),
        ]
        result = budget_choices(cards, (1500,), product_kind="creatine")
        self.assertIn('href="#xfit-offer-2"', result)
        self.assertEqual(result.count('href="#xfit-offer-'), 1)


if __name__ == "__main__":
    unittest.main()
