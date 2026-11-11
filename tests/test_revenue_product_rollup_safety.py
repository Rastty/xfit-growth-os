"""Regression checks for aggregate XFIT affiliate interest, not attribution."""
import json
import unittest

from scripts.xfit_revenue_events import summarize_funnel


PAGE = "xfit-os-kreatin-poradce"
ENGINE = "creatine"


def click(product_id):
    return {"name": "affiliate_outbound_click",
            "params": {"page": PAGE, "selection_engine": ENGINE,
                       "partner": "namaximum", "product_id": product_id}}


class ProductRollupSafetyTests(unittest.TestCase):
    def test_invalid_later_click_aborts_entire_aggregate(self):
        # A valid first row must not justify reporting a partly processed
        # dataset after the second row fails the catalog membership check.
        with self.assertRaises(ValueError):
            summarize_funnel(iter([click(392), click(999)]),
                             analytics_consent=True,
                             verified_product_ids_by_page={PAGE: {392}})

    def test_catalog_refresh_cannot_admit_unverified_click_mid_report(self):
        for replace_page in (False, True):
            with self.subTest(replace_page=replace_page):
                catalogs = {PAGE: {392}}

                def events():
                    yield click(392)
                    if replace_page:
                        catalogs[PAGE] = {999}
                    else:
                        catalogs[PAGE].add(999)
                    yield click(999)

                with self.assertRaises(ValueError):
                    summarize_funnel(events(), analytics_consent=True,
                                     verified_product_ids_by_page=catalogs)

    def test_catalog_refresh_cannot_remove_initially_verified_product(self):
        catalogs = {PAGE: {392}}

        def events():
            catalogs.clear()
            yield click(392)
            yield click(392)

        result = summarize_funnel(events(), analytics_consent=True,
                                  verified_product_ids_by_page=catalogs)
        self.assertEqual(result["product_click_counts"][PAGE], {392: 2})
        self.assertEqual(result["commission"], "UNKNOWN")

    def test_invalid_catalog_fails_before_event_stream_is_read(self):
        def unreadable():
            raise AssertionError("events consumed before catalog validation")
            yield

        with self.assertRaises(ValueError):
            summarize_funnel(unreadable(), analytics_consent=True,
                             verified_product_ids_by_page={PAGE: {True}})

    def test_rollup_is_aggregate_only_and_not_evidence_of_sales(self):
        events = [click(392), click(392),
                  {"name": "advisor_complete", "params": {
                      "page": PAGE, "selection_engine": ENGINE}}]
        data = summarize_funnel(events, analytics_consent=True,
                                verified_product_ids_by_page={PAGE: {392}})
        self.assertEqual(data["product_click_counts"][PAGE], {392: 2})
        self.assertEqual(data["action_counts"][PAGE]["affiliate_outbound_click"], 2)
        for field in ("unique_visitors", "orders", "commission"):
            self.assertEqual(data[field], "UNKNOWN")
        serialized = json.dumps(data, ensure_ascii=False)
        self.assertNotIn("a_aid", serialized)
        self.assertNotIn("a_bid", serialized)
        self.assertNotIn("user_id", serialized)
        self.assertNotIn("email", serialized)
        self.assertNotIn("https://", serialized)

    def test_denied_consent_does_not_consume_private_event_stream(self):
        def forbidden():
            raise AssertionError("events accessed without consent")
            yield
        self.assertIsNone(summarize_funnel(
            forbidden(), analytics_consent=False))


if __name__ == "__main__":
    unittest.main()
