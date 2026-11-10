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
