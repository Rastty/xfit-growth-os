#!/usr/bin/env python3
"""Private, offline Affial Top Campaigns report importer.

The Top Campaigns report can expose clicks and network-side commission
totals without individual customer/order records. Those totals are NOT
necessarily XFIT-only, approved or paid. No network access, WordPress
writes, cookies, visitors, campaign names or transaction data in output.
"""
import argparse
import json
from pathlib import Path
import re
import sys

from scripts.xfit_affial_csv_reconcile import (
    MAX_BYTES, ReconcileError, _amount, _canonical, _read_rows,
)

COUNT = re.compile(r"^(?:0|[1-9][0-9]{0,11})$")


def _count(raw):
    value = str(raw or "").strip().replace("\u00a0", "").replace("\u202f", "")
    # Decimal grouping with spaces is unambiguous; 1,000 and 1.000 are NOT.
    value = value.replace(" ", "")
    if not COUNT.fullmatch(value):
        raise ReconcileError("INVALID_REPORT_COUNT")
    return int(value)


def summarize_campaigns(csv_bytes, *, campaign, campaign_column,
                        clicks_column, commissions_count_column,
                        commission_amount_column, currency_column=None,
                        expected_currency="EUR"):
    """Summarize exactly one matched aggregate row, never combine snapshots."""
    if not isinstance(campaign, str) or not campaign.strip() or len(campaign) > 200:
        raise ReconcileError("EXACT_CAMPAIGN_REQUIRED")
    if expected_currency != "EUR":
        raise ReconcileError("EXPLICIT_EUR_CURRENCY_REQUIRED")
    labels = [campaign_column, clicks_column, commissions_count_column,
              commission_amount_column]
    if currency_column is not None:
        labels.append(currency_column)
    if any(not isinstance(x, str) or not x.strip() for x in labels):
        raise ReconcileError("EXPLICIT_COLUMN_MAPPING_REQUIRED")
    headings, rows = _read_rows(csv_bytes)
    index = {_canonical(name): name for name in headings}
    if any(_canonical(name) not in index for name in labels):
        raise ReconcileError("REQUIRED_CSV_COLUMN_NOT_FOUND")
    keys = [index[_canonical(name)] for name in labels]
    if len(set(keys)) != len(keys):
        raise ReconcileError("AMBIGUOUS_COLUMN_MAPPING")
    candidates = [row for row in rows
                  if _canonical(row[keys[0]]) == _canonical(campaign)]
    if not candidates:
        raise ReconcileError("NO_MATCHING_CAMPAIGN_ROWS")
    # A multirow result may be separate periods, publishers, currencies or
    # duplicated aggregates. Blind summation would invent an economic fact.
    if len(candidates) != 1:
        raise ReconcileError("AMBIGUOUS_CAMPAIGN_DUPLICATES")
    selected = candidates[0]
    if len(keys) == 5 and _canonical(selected[keys[4]]) not in ("eur", "€"):
        raise ReconcileError("CURRENCY_MISMATCH")
    clicks = _count(selected[keys[1]])
    commission_transactions = _count(selected[keys[2]])
    amount = _amount(selected[keys[3]])
    return {
        "state": "USER_SUPPLIED_AFFIAL_TOP_CAMPAIGN_SUMMARY_NOT_LIVE_VERIFIED",
        "report_type": "AFFIAL_TOP_CAMPAIGNS_EXPORT",
        "campaign_scope": "EXACT_OPERATOR_SUPPLIED_CAMPAIGN_NOT_A_SITE_OR_CHANNEL",
        "site_attribution": "UNKNOWN_NO_XFIT_ONLY_CHANNEL_EVIDENCE",
        "source_completeness": "UNKNOWN_EXPORT_FILTERS_NOT_VERIFIED",
        "time_window": "UNKNOWN_EXPORT_FILTERS_NOT_VERIFIED",
        "currency": "EUR",
        "currency_evidence": ("CSV_COLUMN_VERIFIED" if len(keys) == 5
                              else "OPERATOR_ASSERTED_NOT_CSV_VERIFIED"),
        "network_report_clicks": clicks,
        "network_report_commission_transactions": commission_transactions,
        "network_report_commission_total_eur": format(amount, ".2f"),
        "click_uniqueness": "UNKNOWN_MAY_INCLUDE_REPEAT_CLICKS",
        "commission_approval_split": "UNKNOWN_NOT_IN_TOP_CAMPAIGNS_SUMMARY",
        "approved_commission_eur": "UNKNOWN_REQUIRES_STATUS_EXPORT",
        "paid_commission_eur": "UNKNOWN_REQUIRES_SEPARATE_PAYMENT_EVIDENCE",
        "ga4_outbound_events": "UNKNOWN",
        "xfits_site_conversion_rate": "UNKNOWN_NOT_ATTRIBUTABLE",
        "personal_data_logged": 0,
        "campaign_name_logged": False,
        "network_requests": 0,
        "wordpress_writes": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--campaign", required=True,
                        help="Exact Affial campaign value, never printed")
    parser.add_argument("--campaign-column", required=True)
    parser.add_argument("--clicks-column", required=True)
    parser.add_argument("--commission-count-column", required=True)
    parser.add_argument("--commission-eur-column", required=True)
    parser.add_argument("--currency-column",
                        help="Optional exact CSV header for independent EUR check")
    parser.add_argument("--expected-currency", required=True, choices=("EUR",))
    args = parser.parse_args(argv)
    try:
        with args.file.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        report = summarize_campaigns(
            data, campaign=args.campaign,
            campaign_column=args.campaign_column,
            clicks_column=args.clicks_column,
            commissions_count_column=args.commission_count_column,
            commission_amount_column=args.commission_eur_column,
            currency_column=args.currency_column,
            expected_currency=args.expected_currency,
        )
    except ReconcileError as exc:
        print("XFIT_AFFIAL_CAMPAIGN_REPORT_ERROR: " + exc.code, file=sys.stderr)
        return 2
    except OSError:
        print("XFIT_AFFIAL_CAMPAIGN_REPORT_ERROR: PRIVATE_FILE_UNAVAILABLE",
              file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
