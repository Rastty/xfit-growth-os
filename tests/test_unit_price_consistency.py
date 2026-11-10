"""Fail closed on an inconsistent pack/100g price in both buyer journeys."""
import unittest

from scripts.wp_publish import PublishError
from scripts.xfit_price_tradeoff import price_tradeoff


def card(number, price, grams, per100):
    return {
        "id": str(number),
        "title": f"Testovací balení {number}",
        "price_czk": price,
        "mass_g": grams,
        "price_per_100g_powder_czk": per100,
        # Product links are not emitted; the trade-off links to card anchors.
        "tracked_url": "https://www.namaximum.cz/p/example",
    }


class UnitPriceConsistencyTests(unittest.TestCase):
    def test_rejects_incorrect_unit_price_before_rendering(self):
        correct = card(1, 500, 1000, 50)
        for kind in ("creatine", "whey"):
            for wrong in (card(2, 750, 500, 15),
                          card(2, 750, 500, 150.02),
                          card(2, 750, 500, 149.98)):
                with self.subTest(kind=kind, reported=wrong["price_per_100g_powder_czk"]):
                    with self.assertRaisesRegex(PublishError, "unit price conflicts"):
                        price_tradeoff([correct, wrong], product_kind=kind)

    def test_accepts_rounding_from_real_pack_prices(self):
        # select_offers uses round(price / grams * 100, 2).
        cards = [
            card(1, 499.97, 750, round(499.97 / 750 * 100, 2)),
            card(2, 399.99, 500, round(399.99 / 500 * 100, 2)),
        ]
        for kind in ("creatine", "whey"):
            with self.subTest(kind=kind):
                markup = price_tradeoff(cards, product_kind=kind)
                self.assertIn('id="xfit-price-tradeoff"', markup)
                self.assertIn('href="#xfit-offer-', markup)
                self.assertNotIn('href="https://', markup)

    def test_does_not_allow_one_wrong_metric_to_change_the_winner(self):
        # A bogus unit price must not promote a product over a truthful one.
        cards = [card(1, 500, 1000, 50), card(2, 450, 500, 4.5)]
        with self.assertRaises(PublishError):
            price_tradeoff(cards, product_kind="creatine")


if __name__ == "__main__":
    unittest.main()
