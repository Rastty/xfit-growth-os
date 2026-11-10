"""Privacy-first, non-network Affial approvals import tests.

The local CSV is synthetic and must never be committed with real commissions,
orders, click IPs, customer emails or affiliate tokens.
"""
import csv
from io import StringIO
import json
import unittest

from scripts.xfit_affial_csv_reconcile import ReconcileError, summarize


HEAD = ["Transaction ID", "Campaign", "Status", "Commission", "Currency",
        "Customer Email", "Visitor IP"]


def sample(rows, *, columns=HEAD, sep=";"):
    out = StringIO()
    writer = csv.writer(out, delimiter=sep, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


class AffialCsvEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            ["private-order-101", "NaMaximum.cz", "Povoleno", "3,50",
             "EUR", "person101@example.com", "192.0.2.1"],
            ["private-order-102", "NaMaximum.cz", "Nerozhodnuto", "1,25",
             "EUR", "person102@example.com", "192.0.2.2"],
            ["private-order-103", "NaMaximum.cz", "Zamítnuto", "7,00",
             "EUR", "person103@example.com", "192.0.2.3"],
            ["unrelated-order", "Other Campaign", "Povoleno", "999,99",
             "EUR", "person999@example.com", "192.0.2.4"],
        ]

    def run_csv(self, rows=None, **kwargs):
        return summarize(
            sample(self.rows if rows is None else rows),
            campaign="NaMaximum.cz", currency_column="Currency",
            **kwargs
        )

    def test_only_campaign_approved_money_is_reported_not_customer_or_payout(self):
        data = self.run_csv()
        self.assertEqual(data["state"],
                         "USER_SUPPLIED_CSV_APPROVAL_SUMMARY_NOT_NETWORK_VERIFIED")
        self.assertEqual(data["approved_rows"], 1)
        self.assertEqual(data["pending_rows"], 1)
        self.assertEqual(data["declined_rows"], 1)
        self.assertEqual(data["selected_commission_rows"], 3)
        self.assertEqual(data["approved_commission_eur_in_export"], "3.50")
        self.assertEqual(data["pending_commission_eur_in_export"], "1.25")
        self.assertEqual(data["declined_commission_eur_in_export"], "7.00")
        self.assertEqual(data["paid_commission_eur"],
                         "UNKNOWN_REQUIRES_SEPARATE_PAYMENT_EVIDENCE")
        self.assertEqual(data["all_time_revenue"], "UNKNOWN")
        self.assertEqual(data["currency_evidence"], "CSV_COLUMN_VERIFIED")
        serialized = json.dumps(data, ensure_ascii=False)
        for secret in ("private-order", "person101", "example.com",
                       "192.0.2", "NaMaximum", "999,99"):
            self.assertNotIn(secret, serialized)

    def test_approval_codes_and_custom_czech_column_names(self):
        columns = ["ID transakce", "Kampaň", "Stav", "Provize", "Měna"]
        rows = [
            ["tx-1", "NaMaximum.cz", "A", "3.10", "EUR"],
            ["tx-2", "NaMaximum.cz", "P", "2,90", "EUR"],
            ["tx-3", "NaMaximum.cz", "D", "0", "EUR"],
        ]
        data = summarize(
            b"\xef\xbb\xbf" + sample(rows, columns=columns, sep=","),
            campaign=" NaMaximum.cz ", campaign_column="Kampaň",
            status_column="Stav", amount_column="Provize",
            transaction_id_column="ID transakce", currency_column="Měna",
            expected_currency="EUR",
        )
        self.assertEqual((data["approved_rows"], data["pending_rows"],
                          data["declined_rows"]), (1, 1, 1))
        self.assertEqual(data["approved_commission_eur_in_export"], "3.10")

    def test_no_currency_column_never_claims_source_proof(self):
        columns = HEAD[:-3]
        rows = [["tx-1", "NaMaximum.cz", "Povoleno", "5,50"]]
        out = summarize(sample(rows, columns=columns), campaign="NaMaximum.cz",
                        expected_currency="EUR")
        self.assertEqual(out["currency_evidence"],
                         "OPERATOR_ASSERTED_NOT_CSV_VERIFIED")
        self.assertEqual(out["paid_commission_eur"],
                         "UNKNOWN_REQUIRES_SEPARATE_PAYMENT_EVIDENCE")

    def test_repeat_transaction_fails_instead_of_double_counting(self):
        with self.assertRaisesRegex(ReconcileError,
                                    "DUPLICATE_TRANSACTION_IDENTIFIER"):
            self.run_csv(self.rows + [self.rows[0]])

    def test_missing_transaction_id_and_unknown_status_fail_closed(self):
        cases = [
            (0, "", "MISSING_TRANSACTION_IDENTIFIER"),
            (2, "Already paid", "UNKNOWN_COMMISSION_STATUS"),
            (3, "NaN", "INVALID_EUR_AMOUNT"),
            (4, "USD", "CURRENCY_MISMATCH"),
        ]
        for pos, changed, error in cases:
            with self.subTest(error=error):
                rows = [list(row) for row in self.rows]
                rows[0][pos] = changed
                with self.assertRaisesRegex(ReconcileError, error):
                    self.run_csv(rows)

    def test_negative_nonfinite_or_ambiguous_numbers_never_become_money(self):
        for bad in ("-1.00", "NaN", "Infinity", "1e3", "1.234,56",
                    "€12.25", "=SUM(1;2)", "1000000000"):
            with self.subTest(bad=bad):
                rows = [list(r) for r in self.rows]
                rows[0][3] = bad
                with self.assertRaisesRegex(ReconcileError,
                                            "INVALID_EUR_AMOUNT"):
                    self.run_csv(rows)

    def test_empty_campaign_or_unmatched_export_is_unknown_not_zero(self):
        with self.assertRaisesRegex(ReconcileError, "EXACT_CAMPAIGN_REQUIRED"):
            summarize(sample(self.rows), campaign="", expected_currency="EUR")
        with self.assertRaisesRegex(ReconcileError, "NO_MATCHING_CAMPAIGN_ROWS"):
            summarize(sample(self.rows), campaign="Missing campaign",
                      expected_currency="EUR")

    def test_ambiguous_or_missing_mapped_columns_rejected(self):
        with self.assertRaisesRegex(ReconcileError,
                                    "REQUIRED_CSV_COLUMN_NOT_FOUND"):
            summarize(sample(self.rows), campaign="NaMaximum.cz",
                      transaction_id_column="Order ID", expected_currency="EUR")
        with self.assertRaisesRegex(ReconcileError,
                                    "AMBIGUOUS_COLUMN_MAPPING"):
            summarize(sample(self.rows), campaign="NaMaximum.cz",
                      campaign_column="Status", expected_currency="EUR")
        duplicate = sample([["1", "2"]], columns=["Status", " status "])
        with self.assertRaisesRegex(ReconcileError, "CSV_DUPLICATE_HEADERS"):
            summarize(duplicate, campaign="NaMaximum.cz",
                      expected_currency="EUR")

    def test_input_byte_cap_and_disallowed_currency_are_fail_closed(self):
        with self.assertRaisesRegex(ReconcileError, "INVALID_CSV_SIZE"):
            summarize(b"", campaign="NaMaximum.cz", expected_currency="EUR")
        with self.assertRaisesRegex(ReconcileError,
                                    "EXPLICIT_EUR_CURRENCY_REQUIRED"):
            summarize(sample(self.rows), campaign="NaMaximum.cz",
                      expected_currency="CZK")
        with self.assertRaisesRegex(ReconcileError, "INVALID_CSV_SIZE"):
            summarize(b"a" * 5_000_001, campaign="NaMaximum.cz",
                      expected_currency="EUR")


if __name__ == "__main__":
    unittest.main()
