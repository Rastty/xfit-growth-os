#!/usr/bin/env python3
"""Offline, private Affial commission CSV origin-tag audit (NOT payout proof).

Never upload raw partner exports to GitHub or log customer, visitor, order,
affiliate IDs, campaign names, or full URL. Require explicit column mapping:
PAP installs and export locales can name Extra Data 1/2 differently.
"""

import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import sys

from scripts.xfit_affial_csv_reconcile import (
    MAX_BYTES, ReconcileError, STATUS, _amount, _canonical, _read_rows,
)


def summarize_origin(csv_bytes, *, campaign, campaign_column="Campaign",
                     status_column="Status", amount_column="Commission",
                     transaction_id_column="Transaction ID",
                     data1_column, data2_column,
                     currency_column=None, expected_currency="EUR"):
    if not isinstance(campaign, str) or not campaign.strip() or len(campaign) > 200:
        raise ReconcileError("EXACT_CAMPAIGN_REQUIRED")
    if expected_currency != "EUR":
        raise ReconcileError("EXPLICIT_EUR_CURRENCY_REQUIRED")
    needed = [campaign_column, status_column, amount_column,
              transaction_id_column, data1_column, data2_column]
    if currency_column is not None:
        needed.append(currency_column)
    if any(not isinstance(name, str) or not name.strip() for name in needed):
        raise ReconcileError("EXPLICIT_COLUMN_MAPPING_REQUIRED")
    headings, rows = _read_rows(csv_bytes)
    index = {_canonical(name): name for name in headings}
    if any(_canonical(name) not in index for name in needed):
        raise ReconcileError("REQUIRED_CSV_COLUMN_NOT_FOUND")
    fields = [index[_canonical(name)] for name in needed]
    if len(set(fields)) != len(fields):
        raise ReconcileError("AMBIGUOUS_COLUMN_MAPPING")
    campaign_key, status_key, amount_key, id_key, data1_key, data2_key = fields[:6]
    currency_key = fields[6] if currency_column else None

    counts = Counter()
    matched_status = Counter()
    matched_eur = {status: Decimal("0") for status in ("approved", "pending", "declined")}
    seen = set()
    selected = 0
    for row in rows:
        if _canonical(row[campaign_key]) != _canonical(campaign):
            continue
        selected += 1
        transaction = str(row[id_key] or "").strip()
        if not transaction or len(transaction) > 200:
            raise ReconcileError("MISSING_TRANSACTION_IDENTIFIER")
        if transaction in seen:
            raise ReconcileError("DUPLICATE_TRANSACTION_IDENTIFIER")
        seen.add(transaction)
        status = STATUS.get(_canonical(row[status_key]))
        if not status:
            raise ReconcileError("UNKNOWN_COMMISSION_STATUS")
        amount = _amount(row[amount_key])
        if currency_key and _canonical(row[currency_key]) not in ("eur", "€"):
            raise ReconcileError("CURRENCY_MISMATCH")
        data1, data2 = _canonical(row[data1_key]), _canonical(row[data2_key])
        if data1 == "xfit" and data2 == "creatine":
            counts["matched"] += 1
            matched_status[status] += 1
            matched_eur[status] += amount
        elif not data1 and not data2:
            counts["untagged"] += 1
        else:
            # Never silently assign a partially tagged or foreign campaign
            # commission to this site, even if one marker matches.
            counts["other_or_partial"] += 1
    if not selected:
        raise ReconcileError("NO_MATCHING_CAMPAIGN_ROWS")

    observed = counts["matched"] > 0
    return {
        "state": "USER_SUPPLIED_AFFIAL_ORIGIN_CSV_NOT_NETWORK_VERIFIED",
        "campaign_scope": "EXACT_OPERATOR_SUPPLIED_LABEL",
        "origin_scope": "DATA1_XFIT_AND_DATA2_CREATINE_EXACT_PAIR",
        "origin_evidence": ("MATCHING_MARKER_PRESENT_IN_CSV_ONLY" if observed
                            else "NO_XFIT_CREATINE_MARKER_OBSERVED_IN_EXPORT"),
        "source_completeness": "UNKNOWN_EXPORT_FILTERS_NOT_VERIFIED",
        "time_window": "UNKNOWN_EXPORT_FILTERS_NOT_VERIFIED",
        "currency": "EUR",
        "currency_evidence": ("CSV_COLUMN_VERIFIED" if currency_key
                              else "OPERATOR_ASSERTED_NOT_CSV_VERIFIED"),
        "campaign_rows_in_export": selected,
        "xfits_creatine_tagged_rows": counts["matched"],
        "untagged_campaign_rows": counts["untagged"],
        "other_or_partial_origin_rows": counts["other_or_partial"],
        "xfits_creatine_tagged_approved_rows": matched_status["approved"],
        "xfits_creatine_tagged_pending_rows": matched_status["pending"],
        "xfits_creatine_tagged_declined_rows": matched_status["declined"],
        "xfits_creatine_approved_eur_in_export": (
            format(matched_eur["approved"], ".2f") if observed
            else "UNKNOWN_NO_TAGGED_ROWS"),
        "xfits_creatine_pending_eur_in_export": (
            format(matched_eur["pending"], ".2f") if observed
            else "UNKNOWN_NO_TAGGED_ROWS"),
        "xfits_creatine_declined_eur_in_export": (
            format(matched_eur["declined"], ".2f") if observed
            else "UNKNOWN_NO_TAGGED_ROWS"),
        "paid_commission_eur": "UNKNOWN_REQUIRES_SEPARATE_PAYMENT_EVIDENCE",
        "network_click_credit": "UNKNOWN_REQUIRES_AFFIAL_CLICK_EVIDENCE",
        "ga4_outbound_events": "UNKNOWN",
        "all_time_revenue": "UNKNOWN",
        "transaction_ids_logged": 0,
        "personal_data_logged": 0,
        "affiliate_credentials_logged": 0,
        "network_requests": 0,
        "wordpress_writes": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--campaign", required=True, help="Exact label, not printed")
    parser.add_argument("--campaign-column", default="Campaign")
    parser.add_argument("--status-column", default="Status")
    parser.add_argument("--amount-column", default="Commission")
    parser.add_argument("--transaction-id-column", default="Transaction ID")
    parser.add_argument("--data1-column", required=True)
    parser.add_argument("--data2-column", required=True)
    parser.add_argument("--currency-column")
    parser.add_argument("--expected-currency", required=True, choices=("EUR",))
    args = parser.parse_args(argv)
    try:
        with args.file.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        report = summarize_origin(
            raw, campaign=args.campaign,
            campaign_column=args.campaign_column, status_column=args.status_column,
            amount_column=args.amount_column,
            transaction_id_column=args.transaction_id_column,
            data1_column=args.data1_column, data2_column=args.data2_column,
            currency_column=args.currency_column,
            expected_currency=args.expected_currency,
        )
    except ReconcileError as error:
        print("XFIT_AFFIAL_ORIGIN_CSV_ERROR: " + error.code, file=sys.stderr)
        return 2
    except OSError:
        print("XFIT_AFFIAL_ORIGIN_CSV_ERROR: PRIVATE_FILE_UNAVAILABLE", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
