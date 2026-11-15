"""Private CSV fixtures contain no real merchant, visitor or order data."""
import csv
from io import StringIO
import json
import unittest

from scripts.xfit_affial_csv_reconcile import ReconcileError
from scripts.xfit_affial_origin_reconcile import summarize_origin


HEAD = ["ID", "Campaign", "Status", "Commission", "Extra Data 1",
        "Extra Data 2", "Currency", "Email", "IP"]


def csv_fixture(rows, head=HEAD):
    sink = StringIO()
    writer = csv.writer(sink, delimiter=";", lineterminator="\n")
    writer.writerow(head)
    writer.writerows(rows)
    return sink.getvalue().encode("utf-8")


class OriginReconcileTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            ["p-01", "Partner 1", "Approved", "5,50", "xfit", "creatine", "EUR", "a@secret.test", "192.0.2.1"],
            ["p-02", "Partner 1", "Pending", "2.00", "XFIT", "CREATINE", "EUR", "b@secret.test", "192.0.2.2"],
            ["p-03", "Partner 1", "Declined", "7", "xfit", "creatine", "EUR", "c@secret.test", "192.0.2.3"],
            ["p-04", "Partner 1", "Approved", "99", "", "", "EUR", "d@secret.test", "192.0.2.4"],
            ["p-05", "Partner 1", "Approved", "88", "other", "creatine", "EUR", "e@secret.test", "192.0.2.5"],
            ["p-06", "Partner 1", "Approved", "77", "xfit", "", "EUR", "f@secret.test", "192.0.2.6"],
            ["p-07", "Partner 2", "Approved", "1000", "xfit", "creatine", "EUR", "g@secret.test", "192.0.2.7"],
        ]

    def report(self, rows=None, **options):
        return summarize_origin(csv_fixture(self.rows if rows is None else rows),
                                campaign="Partner 1", transaction_id_column="ID",
                                data1_column="Extra Data 1", data2_column="Extra Data 2",
                                currency_column="Currency", **options)

    def test_only_exact_source_pair_contributes_to_status_amounts(self):
        report = self.report()
        self.assertEqual(report["campaign_rows_in_export"], 6)
        self.assertEqual(report["xfits_creatine_tagged_rows"], 3)
        self.assertEqual(report["untagged_campaign_rows"], 1)
        self.assertEqual(report["other_or_partial_origin_rows"], 2)
        self.assertEqual(report["xfits_creatine_tagged_approved_rows"], 1)
        self.assertEqual(report["xfits_creatine_tagged_pending_rows"], 1)
        self.assertEqual(report["xfits_creatine_tagged_declined_rows"], 1)
        self.assertEqual(report["xfits_creatine_approved_eur_in_export"], "5.50")
        self.assertEqual(report["xfits_creatine_pending_eur_in_export"], "2.00")
        self.assertEqual(report["xfits_creatine_declined_eur_in_export"], "7.00")
        self.assertEqual(report["paid_commission_eur"],
                         "UNKNOWN_REQUIRES_SEPARATE_PAYMENT_EVIDENCE")
        self.assertEqual(report["currency_evidence"], "CSV_COLUMN_VERIFIED")
        text = json.dumps(report)
        for private in ("Partner 1", "p-01", "secret.test", "192.0.2", "1000"):
            self.assertNotIn(private, text)

    def test_no_matching_source_tag_is_unknown_not_proven_zero(self):
        empty = [list(self.rows[3])]
        report = self.report(empty)
        self.assertEqual(report["origin_evidence"],
                         "NO_XFIT_CREATINE_MARKER_OBSERVED_IN_EXPORT")
        self.assertEqual(report["xfits_creatine_approved_eur_in_export"],
                         "UNKNOWN_NO_TAGGED_ROWS")

    def test_duplicate_transaction_and_malformed_money_fail_closed(self):
        with self.assertRaisesRegex(ReconcileError,
                                    "DUPLICATE_TRANSACTION_IDENTIFIER"):
            self.report([self.rows[0], self.rows[0]])
        truncated = [self.rows[0], self.rows[1][:-1]]
        # The shared strict reader may reject malformed row widths already
        # during delimiter inference, before it can inspect row values.
        with self.assertRaisesRegex(ReconcileError, "CSV_DELIMITER_UNKNOWN"):
            self.report(truncated)
        for field, value, error in (
            (0, "", "MISSING_TRANSACTION_IDENTIFIER"),
            (2, "Payment", "UNKNOWN_COMMISSION_STATUS"),
            (3, "-1", "INVALID_EUR_AMOUNT"),
            (6, "USD", "CURRENCY_MISMATCH"),
        ):
            altered = list(self.rows[0])
            altered[field] = value
            with self.subTest(error=error):
                with self.assertRaisesRegex(ReconcileError, error):
                    self.report([altered])

    def test_export_columns_are_explicit_and_never_guessed(self):
        with self.assertRaisesRegex(ReconcileError, "REQUIRED_CSV_COLUMN_NOT_FOUND"):
            summarize_origin(csv_fixture(self.rows), campaign="Partner 1",
                             transaction_id_column="ID",
                             data1_column="SubID", data2_column="Extra Data 2")
        with self.assertRaisesRegex(ReconcileError, "AMBIGUOUS_COLUMN_MAPPING"):
            summarize_origin(csv_fixture(self.rows), campaign="Partner 1",
                             transaction_id_column="ID",
                             data1_column="Extra Data 2", data2_column="Extra Data 2")
        with self.assertRaisesRegex(ReconcileError, "EXPLICIT_COLUMN_MAPPING_REQUIRED"):
            summarize_origin(csv_fixture(self.rows), campaign="Partner 1",
                             transaction_id_column="ID",
                             data1_column="", data2_column="Extra Data 2")
        with self.assertRaisesRegex(ReconcileError, "NO_MATCHING_CAMPAIGN_ROWS"):
            summarize_origin(csv_fixture(self.rows), campaign="Not in export",
                             transaction_id_column="ID",
                             data1_column="Extra Data 1", data2_column="Extra Data 2")

    def test_optional_currency_column_is_explicit_operator_assertion(self):
        report = summarize_origin(csv_fixture(self.rows), campaign="Partner 1",
                                  transaction_id_column="ID",
                                  data1_column="Extra Data 1",
                                  data2_column="Extra Data 2")
        self.assertEqual(report["currency_evidence"],
                         "OPERATOR_ASSERTED_NOT_CSV_VERIFIED")


if __name__ == "__main__":
    unittest.main()
