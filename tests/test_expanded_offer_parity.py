"""Offline regression for plant/equipment live offer proof. No network."""
import json
import unittest
from scripts.xfit_public_feed_parity import inspect_expanded, ParityError
from scripts.xfit_plant_comparison import build_document as plant_doc, SLUG as PLANT
from scripts.xfit_equipment_comparison import build_document as gear_doc, SLUG as GEAR
from test_plant_comparison import BASE, SAMPLE, catalog, item as plant_item
from test_equipment_comparison import item as gear_item


def fixture():
    rows = [
        plant_item(11, "Sójový protein 500 g", 249, path="soja"),
        plant_item(12, "Rýžový protein 1 kg", 399, path="ryze"),
        gear_item(21, "Yoga Mat", 499, path="mat"),
        gear_item(22, "Resistance Band", 349, path="band"),
    ]
    feed = catalog(*rows)
    plant = plant_doc(feed, BASE, SAMPLE)["content"]
    gear = gear_doc(feed, BASE, SAMPLE)["content"]
    return rows, {PLANT: (plant, plant), GEAR: (gear, gear)}


class ExpandedParityTests(unittest.TestCase):
    def test_exact_fresh_source_and_public_cards(self):
        rows, pages = fixture()
        result = inspect_expanded(rows, pages, BASE, SAMPLE)
        self.assertEqual(result["state"], "EXPANDED_SOURCE_FEED_PARITY_OBSERVED")
        self.assertEqual([p["exact_current_feed_match"] for p in result["pages"]], [2, 2])
        self.assertEqual(result["wordpress_writes"], 0)
        self.assertFalse(result["merchant_checkout_stock_verified"])
        for sensitive in ("Sójový protein", "variant=", "DEMO", "249", "namaximum.cz/p/"):
            self.assertNotIn(sensitive, json.dumps(result, ensure_ascii=False))

    def test_feed_change_absence_and_duplicate_are_review_not_stock_claim(self):
        rows, pages = fixture()
        rows[0]["price_czk"] = 259
        rows[2]["delivery_date"] = "10"
        result = inspect_expanded(rows, pages, BASE, SAMPLE)
        self.assertEqual(result["state"], "REVIEW_EXPANDED_OFFERS")
        self.assertEqual(result["pages"][0]["feed_price_differs_or_invalid"], 1)
        self.assertEqual(result["pages"][1]["feed_dispatch_no_longer_eligible"], 1)
        rows, pages = fixture()
        rows.append(dict(rows[0]))
        rows.pop(2)
        result = inspect_expanded(rows, pages, BASE, SAMPLE)
        self.assertEqual(result["pages"][0]["ambiguous_feed_identity"], 1)
        self.assertEqual(result["pages"][1]["feed_destination_not_observed"], 1)

    def test_variant_and_campaign_drift_cannot_be_hidden(self):
        rows, pages = fixture()
        source, public = pages[PLANT]
        for modified in (public.replace("variant=11", "variant=99"),
                         public.replace("a_aid=DEMO", "a_aid=FOREIGN"),
                         public.replace("249,00 Kč", "249,01 Kč"),
                         public.replace("rel=\"sponsored", "rel=\"nofollow")):
            with self.subTest(sample=modified[:80]), self.assertRaises(ParityError):
                inspect_expanded(rows, {**pages, PLANT: (source, modified)}, BASE, SAMPLE)
        # Both rendered sources agree, but a fabricated variant doesn't join.
        forged = source.replace("variant=11", "variant=99")
        result = inspect_expanded(rows, {**pages, PLANT: (forged, forged)}, BASE, SAMPLE)
        self.assertEqual(result["pages"][0]["feed_destination_not_observed"], 1)

    def test_per_card_disclosure_and_ambiguous_prices_fail(self):
        rows, pages = fixture()
        for slug, (source, _) in pages.items():
            broken = source.replace("Partnerský odkaz · Xfit.cz může získat provizi", "Obchodní nabídka")
            with self.assertRaises(ParityError):
                inspect_expanded(rows, {**pages, slug: (broken, broken)}, BASE, SAMPLE)
        source = pages[PLANT][0].replace("za balení 500 g.", "za balení 500 g. 299,00 Kč za balení 500 g.")
        with self.assertRaises(ParityError):
            inspect_expanded(rows, {**pages, PLANT: (source, source)}, BASE, SAMPLE)


if __name__ == "__main__":
    unittest.main()
