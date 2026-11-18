"""Regression checks for aggregate XFIT affiliate interest, not attribution."""
import json
import unittest
from unittest.mock import patch

from scripts import xfit_revenue_events

from scripts.xfit_revenue_events import summarize_funnel


PAGE = "xfit-os-kreatin-poradce"
ENGINE = "creatine"


def click(product_id):
    return {"name": "affiliate_outbound_click",
            "params": {"page": PAGE, "selection_engine": ENGINE,
                       "partner": "namaximum", "product_id": product_id}}


class ProductRollupSafetyTests(unittest.TestCase):
    def test_disguised_strings_cannot_export_unapproved_text(self):
        class Disguised(str):
            def __new__(cls, allowed):
                value = super().__new__(cls, "private-answer")
                value.allowed = allowed
                return value

            def __eq__(self, other):
                return self.allowed == other

            def __hash__(self):
                return hash(self.allowed)

        for field in ("name", "page", "partner", "selection_engine"):
            with self.subTest(field=field):
                event = click(392)
                target = event if field == "name" else event["params"]
                target[field] = Disguised(target[field])
                # The underlying text differs from the impersonated value.
                self.assertEqual(json.loads(json.dumps(target[field])),
                                 "private-answer")
                with self.assertRaises(ValueError) as error:
                    xfit_revenue_events.build_event(
                        event["name"], event["params"], analytics_consent=True,
                        verified_product_ids_by_page={PAGE: {392}})
                self.assertNotIn("private-answer", str(error.exception))
                with self.assertRaises(ValueError):
                    summarize_funnel(
                        [click(392), event], analytics_consent=True,
                        verified_product_ids_by_page={PAGE: {392}})

    def test_funnel_rejects_non_json_mapping_shapes(self):
        class CustomDict(dict):
            pass

        class CustomKey(str):
            pass

        event = click(392)
        params = event["params"]
        invalid_params = (CustomDict(params), {
            CustomKey("page"): PAGE,
            **{key: value for key, value in params.items() if key != "page"},
        })
        options = {"analytics_consent": True,
                   "verified_product_ids_by_page": {PAGE: {392}}}
        for fields in invalid_params:
            with self.subTest(fields_type=type(fields)):
                with self.assertRaises(ValueError):
                    xfit_revenue_events.build_event(event["name"], fields, **options)
                with self.assertRaises(ValueError):
                    summarize_funnel([dict(event, params=fields)], **options)
        for record in (CustomDict(event),
                       {CustomKey("name"): event["name"], "params": params}):
            with self.subTest(record_type=type(record)):
                with self.assertRaises(ValueError):
                    summarize_funnel([record], **options)

    def test_catalog_is_validated_once_for_multiple_clicks_and_advisors(self):
        whey = "xfit-os-syrovatkovy-protein-porovnani"
        whey_click = {"name": "affiliate_outbound_click", "params": {
            "page": whey, "selection_engine": "whey",
            "partner": "namaximum", "product_id": 393}}
        with patch.object(xfit_revenue_events, "_snapshot_catalogs",
                          wraps=xfit_revenue_events._snapshot_catalogs) as snapshot:
            result = summarize_funnel(
                iter([click(392), whey_click, click(392)]),
                analytics_consent=True,
                verified_product_ids_by_page={PAGE: {392}, whey: {393}})
        self.assertEqual(snapshot.call_count, 1)
        self.assertEqual(result["product_click_counts"], {
            PAGE: {392: 2}, whey: {393: 1}})
        self.assertEqual(result["commission"], "UNKNOWN")

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
