#!/usr/bin/env python3
"""Private, offline Affial commission-approval evidence; NEVER a payout report.

Input: a user-exported Affial/PAP commissions CSV kept outside the repository.
No network, GitHub artifacts, WP writes, cookies, visitor data or order IDs
are emitted. A selected campaign and stable transaction identifier are
mandatory. An export is *not* proof of all-time performance or actual payment.
"""
import argparse
from collections import Counter
import csv
from decimal import Decimal, InvalidOperation
import io
import json
from pathlib import Path
import re
import sys

MAX_BYTES = 5_000_000
MAX_ROWS = 100_000
STATUS = {
    "povoleno": "approved",
    "approved": "approved",
    "a": "approved",
    "nerozhodnuto": "pending",
    "pending": "pending",
    "p": "pending",
    "zamítnuto": "declined",
    "zamítnuté": "declined",
    "declined": "declined",
    "denied": "declined",
    "d": "declined",
}
AMOUNT_PATTERN = re.compile(r"^(?:0|[1-9][0-9]{0,8})(?:[,.][0-9]{1,2})?$")


class ReconcileError(ValueError):
    """Only constant safe codes, never raw private values."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _canonical(value):
    return " ".join(str(value or "").split()).casefold()


def _amount(value):
    raw = str(value or "").strip().replace("\u00a0", "").replace("\u202f", "")
    raw = raw.replace(" ", "")
    if not AMOUNT_PATTERN.fullmatch(raw):
        raise ReconcileError("INVALID_EUR_AMOUNT")
    try:
        amount = Decimal(raw.replace(",", "."))
    except InvalidOperation:
        raise ReconcileError("INVALID_EUR_AMOUNT") from None
    if not amount.is_finite() or amount < 0:
        raise ReconcileError("INVALID_EUR_AMOUNT")
    return amount.quantize(Decimal("0.01"))


def _read_rows(csv_bytes):
    if not isinstance(csv_bytes, bytes) or not 0 < len(csv_bytes) <= MAX_BYTES:
        raise ReconcileError("INVALID_CSV_SIZE")
    try:
        value = csv_bytes.decode("utf-8-sig")
    except UnicodeError:
        raise ReconcileError("CSV_REQUIRES_UTF8") from None
    if "\x00" in value:
        raise ReconcileError("INVALID_CSV_CONTENT")
    try:
        dialect = csv.Sniffer().sniff(value[:8192], delimiters=",;\t")
    except csv.Error:
        raise ReconcileError("CSV_DELIMITER_UNKNOWN") from None
    reader = csv.DictReader(io.StringIO(value, newline=""), dialect=dialect)
    if not reader.fieldnames or not all(isinstance(x, str) and x.strip()
                                       for x in reader.fieldnames):
        raise ReconcileError("CSV_HEADER_MISSING")
    norm = [_canonical(x) for x in reader.fieldnames]
    if len(norm) != len(set(norm)):
        raise ReconcileError("CSV_DUPLICATE_HEADERS")
    rows = []
    for i, row in enumerate(reader):
        if i >= MAX_ROWS:
            raise ReconcileError("CSV_TOO_MANY_ROWS")
        if None in row or None in row.values():
            raise ReconcileError("CSV_INCONSISTENT_COLUMNS")
        rows.append(row)
    return reader.fieldnames, rows


def summarize(csv_bytes, *, campaign, campaign_column="Campaign",
              status_column="Status", amount_column="Commission",
              transaction_id_column="Transaction ID",
              currency_column=None, expected_currency="EUR"):
    """Summarize only exact campaign rows and explicit, nonduplicated IDs."""
    if not isinstance(campaign, str) or not campaign.strip() or len(campaign) > 200:
        raise ReconcileError("EXACT_CAMPAIGN_REQUIRED")
    if expected_currency != "EUR":
        raise ReconcileError("EXPLICIT_EUR_CURRENCY_REQUIRED")
    fields, rows = _read_rows(csv_bytes)
    index = {_canonical(field): field for field in fields}
    required = [campaign_column, status_column, amount_column, transaction_id_column]
    if currency_column is not None:
        required.append(currency_column)
    if any(not isinstance(field, str) or not field.strip()
           or _canonical(field) not in index for field in required):
        raise ReconcileError("REQUIRED_CSV_COLUMN_NOT_FOUND")
    names = [index[_canonical(name)] for name in required]
    if len(set(names)) != len(names):
        raise ReconcileError("AMBIGUOUS_COLUMN_MAPPING")
    c_name, s_name, a_name, t_name = names[:4]
    currency_name = names[4] if currency_column is not None else None
    seen_transactions = set()
    counts = Counter()
    totals = {"approved": Decimal("0"), "pending": Decimal("0"),
              "declined": Decimal("0")}
    selected = 0
    for row in rows:
        if _canonical(row[c_name]) != _canonical(campaign):
            continue
        selected += 1
        txn_id = str(row[t_name] or "").strip()
        # A reused order/transaction key can double-count approved commission.
        # Keep it only in memory; no raw identifiers in report/logs.
        if not txn_id or len(txn_id) > 200:
            raise ReconcileError("MISSING_TRANSACTION_IDENTIFIER")
        if txn_id in seen_transactions:
            raise ReconcileError("DUPLICATE_TRANSACTION_IDENTIFIER")
        seen_transactions.add(txn_id)
        status = STATUS.get(_canonical(row[s_name]))
        if not status:
            raise ReconcileError("UNKNOWN_COMMISSION_STATUS")
        if currency_name and _canonical(row[currency_name]) not in ("eur", "€"):
            raise ReconcileError("CURRENCY_MISMATCH")
        amount = _amount(row[a_name])
        counts[status] += 1
        totals[status] += amount
    if not selected:
        raise ReconcileError("NO_MATCHING_CAMPAIGN_ROWS")
    return {
        "state": "USER_SUPPLIED_CSV_APPROVAL_SUMMARY_NOT_NETWORK_VERIFIED",
        "campaign_scope": "EXACT_OPERATOR_SUPPLIED_LABEL",
        "time_window": "UNKNOWN_EXPORT_FILTERS_NOT_VERIFIED",
        "source_completeness": "UNKNOWN_EXPORT_MAY_BE_PARTIAL",
        "deduplication": "UNIQUE_TRANSACTION_IDS_WITHIN_EXPORT",
        "currency": "EUR",
        "currency_evidence": ("CSV_COLUMN_VERIFIED" if currency_name
                              else "OPERATOR_ASSERTED_NOT_CSV_VERIFIED"),
        "selected_commission_rows": selected,
        "approved_rows": counts["approved"],
        "pending_rows": counts["pending"],
        "declined_rows": counts["declined"],
        "approved_commission_eur_in_export": format(totals["approved"], ".2f"),
        "pending_commission_eur_in_export": format(totals["pending"], ".2f"),
        "declined_commission_eur_in_export": format(totals["declined"], ".2f"),
        "paid_commission_eur": "UNKNOWN_REQUIRES_SEPARATE_PAYMENT_EVIDENCE",
        "ga4_outbound_events": "UNKNOWN",
        "all_time_revenue": "UNKNOWN",
        "raw_transaction_identifiers_logged": 0,
        "personal_data_logged": 0,
        "network_requests": 0,
        "wordpress_writes": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--campaign", required=True,
                        help="EXACT label in your filtered CSV; not printed")
    parser.add_argument("--campaign-column", default="Campaign")
    parser.add_argument("--status-column", default="Status")
    parser.add_argument("--amount-column", default="Commission")
    parser.add_argument("--transaction-id-column", default="Transaction ID")
    parser.add_argument("--currency-column",
                        help="Optional exact name; verifies every matching row")
    parser.add_argument("--expected-currency", required=True, choices=("EUR",))
    options = parser.parse_args(argv)
    try:
        with options.file.open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        result = summarize(
            raw, campaign=options.campaign,
            campaign_column=options.campaign_column,
            status_column=options.status_column,
            amount_column=options.amount_column,
            transaction_id_column=options.transaction_id_column,
            currency_column=options.currency_column,
            expected_currency=options.expected_currency,
        )
    except ReconcileError as err:
        print("XFIT_AFFIAL_CSV_ERROR: " + err.code, file=sys.stderr)
        return 2
    except OSError:
        print("XFIT_AFFIAL_CSV_ERROR: PRIVATE_FILE_UNAVAILABLE", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
