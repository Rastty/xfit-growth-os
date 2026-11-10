"""Synthetic-only Affial Top Campaigns aggregate importer regression tests."""
from io import StringIO
import csv
import json
import unittest

from scripts.xfit_affial_csv_reconcile import ReconcileError
from scripts.xfit_affial_top_campaigns import summarize_campaigns


FIELDS = ["Názov", "Počet prodejů", "Provize", "Prokliky",
          "Měna", "Private email", "Private order"]


def fixture(rows, fields=FIELDS, delim=";"):
    buf = StringIO()
    writer = csv.writer(buf, delimiter=delim, lineterminator="\n")
    writer.writerow(fields)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


class CampaignReportTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            ["NaMaximum", "7", "49,25", "150", "EUR",
             "customer101@example.com", "order-secret-101"],
            ["Other merchant", "777", "99999,99", "50000", "EUR",
             "customer222@example.com", "order-secret-222"],
        ]

    def summarise(self, rows=None, **opts):
        base = dict(
            campaign="NaMaximum", campaign_column="Názov",
            clicks_column="Prokliky", commissions_count_column="Počet prodejů",
            commission_amount_column="Provize", currency_column="Měna",
            expected_currency="EUR",
        )
        base.update(opts)
        return summarize_campaigns(fixture(self.rows if rows is None else rows),
                                   **base)

    def test_selected_network_campaign_aggregate_never_claims_paid_or_xfit(self):
        result = self.summarise()
        self.assertEqual(result["network_report_clicks"], 150)
        self.assertEqual(result["network_report_commission_transactions"], 7)
        self.assertEqual(result["network_report_commission_total_eur"], "49.25")
        self.assertEqual(result["commission_approval_split"],
                         "UNKNOWN_NOT_IN_TOP_CAMPAIGNS_SUMMARY")
        self.assertEqual(result["approved_commission_eur"],
                         "UNKNOWN_REQUIRES_STATUS_EXPORT")
        self.assertEqual(result["paid_commission_eur"],
                         "UNKNOWN_REQUIRES_SEPARATE_PAYMENT_EVIDENCE")
        self.assertEqual(result["site_attribution"],
                         "UNKNOWN_NO_XFIT_ONLY_CHANNEL_EVIDENCE")
        self.assertEqual(result["click_uniqueness"],
                         "UNKNOWN_MAY_INCLUDE_REPEAT_CLICKS")
        self.assertEqual(result["currency_evidence"], "CSV_COLUMN_VERIFIED")
        output = json.dumps(result, ensure_ascii=False)
        for forbidden in ("NaMaximum", "Other merchant", "example.com",
                          "order-secret", "99999", "customer101"):
            self.assertNotIn(forbidden, output)

    def test_no_currency_column_is_assertion_not_source_verified(self):
        result = self.summarise(currency_column=None)
        self.assertEqual(result["currency_evidence"],
                         "OPERATOR_ASSERTED_NOT_CSV_VERIFIED")

    def test_exact_one_campaign_row_required(self):
        with self.assertRaisesRegex(ReconcileError,
                                    "AMBIGUOUS_CAMPAIGN_DUPLICATES"):
            self.summarise(self.rows + [list(self.rows[0])])
        with self.assertRaisesRegex(ReconcileError,
                                    "NO_MATCHING_CAMPAIGN_ROWS"):
            self.summarise(campaign="Not found")

    def test_counts_must_be_unambiguous_integers(self):
        for invalid in ("-1", "1.5", "1,500", "NaN", "Infinity",
                        "1e3", "=SUM(1;2)", "1.000", "0007", ""):
            rows = [list(row) for row in self.rows]
            rows[0][3] = invalid
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ReconcileError,
                                            "INVALID_REPORT_COUNT"):
                    self.summarise(rows)

    def test_amount_and_currency_are_explicit_eur_not_guessed(self):
        for invalid in ("1.234,56", "-2,3", "EUR 3,40", "NaN", "1e6"):
            rows = [list(row) for row in self.rows]
            rows[0][2] = invalid
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ReconcileError,
                                            "INVALID_EUR_AMOUNT"):
                    self.summarise(rows)
        rows = [list(row) for row in self.rows]
        rows[0][4] = "CZK"
        with self.assertRaisesRegex(ReconcileError, "CURRENCY_MISMATCH"):
            self.summarise(rows)
        with self.assertRaisesRegex(ReconcileError,
                                    "EXPLICIT_EUR_CURRENCY_REQUIRED"):
            self.summarise(expected_currency="CZK")

    def test_custom_headers_are_required_not_assumed(self):
        with self.assertRaisesRegex(ReconcileError,
                                    "REQUIRED_CSV_COLUMN_NOT_FOUND"):
            self.summarise(clicks_column="Unverified header")
        with self.assertRaisesRegex(ReconcileError,
                                    "AMBIGUOUS_COLUMN_MAPPING"):
            self.summarise(clicks_column="Provize")
        with self.assertRaisesRegex(ReconcileError,
                                    "EXPLICIT_COLUMN_MAPPING_REQUIRED"):
            self.summarise(clicks_column="")

    def test_zero_is_legitimate_report_observation_not_cash(self):
        rows = [list(self.rows[0])]
        rows[0][1] = "0"
        rows[0][2] = "0,00"
        rows[0][3] = "0"
        result = self.summarise(rows)
        self.assertEqual(result["network_report_clicks"], 0)
        self.assertEqual(result["network_report_commission_total_eur"], "0.00")
        self.assertEqual(result["paid_commission_eur"],
                         "UNKNOWN_REQUIRES_SEPARATE_PAYMENT_EVIDENCE")
        self.assertEqual(result["time_window"],
                         "UNKNOWN_EXPORT_FILTERS_NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
