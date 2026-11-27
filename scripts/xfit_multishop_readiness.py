"""Site-local source readiness for existing Core exact multishop contract.

Do not reimplement cross-merchant projection, invent a second feed or publish
offers. Report only anonymous aggregate completeness and ambiguity buckets.
"""
from collections import Counter
import json
from pathlib import Path
import re
import sys

from scripts.xfit_catalog_retrieval import verified_catalog_fetch_time
from scripts.xfit_select import folded, matches_kind, mass_grams
from scripts.xfit_equipment_comparison import equipment_kind
from scripts.xfit_feed_ingest import catalog_identity_matches_url
from scripts.xfit_availability import delivery_state
from scripts.xfit_public_feed_parity import _cents
from scripts.wp_publish import PublishError

CATALOG = Path("reports/private-greenmedical-catalog.json")
REPORT = Path("reports/xfit-multishop-source-readiness.json")
SCOPES = ("all", "creatine", "whey", "plant_protein", "equipment_mat", "equipment_band")


def valid_gtin(value):
    """Same GS1 checksum/length rule as Core validGtin, plus zero placeholder guard.

    Keep leading zeros. Checksum is a format screen, not proof of GS1 assignment.
    """
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{8}|[0-9]{12}|[0-9]{13}|[0-9]{14}", value):
        return False
    if len(set(value)) == 1:
        return False
    checksum = sum(int(digit) * (3 if i % 2 == 0 else 1)
                   for i, digit in enumerate(reversed(value[:-1])))
    return (10 - checksum % 10) % 10 == int(value[-1])


def explicit_brand(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 80:
        return False
    key = " ".join(folded(value).split())
    return (key not in {"-", "n/a", "na", "none", "null", "unknown", "neznamy",
                        "nezname", "bez znacky", "no brand", "generic"}
            and any(c.isalpha() for c in key))


def lane_members(row):
    """Broad candidate scopes only: never claim all are publication-eligible."""
    scopes = ["all"]
    for kind in ("creatine", "whey", "plant_protein"):
        if matches_kind(row, kind) and mass_grams(row.get("title")) is not None:
            scopes.append(kind)
    equipment = equipment_kind(row)
    if equipment:
        scopes.append("equipment_" + equipment)
    return scopes


def profile(catalog, *, now=None):
    verified_catalog_fetch_time(catalog, required=True, now=now)
    rows = catalog.get("products")
    if (catalog.get("merchant") != "namaximum.cz" or catalog.get("merchant_match") is not True
            or not isinstance(rows, list) or not 1 <= len(rows) <= 10000):
        raise PublishError("Expected complete verified NaMaximum catalog")
    identifiers = Counter()
    gtins = Counter()
    for row in rows:
        if not isinstance(row, dict):
            raise PublishError("Invalid source catalog row")
        pid = row.get("id")
        if (row.get("merchant") != "NaMaximum.cz" or not isinstance(pid, str)
                or not catalog_identity_matches_url(pid, row.get("source_url"))):
            raise PublishError("Invalid source merchant or product identity")
        identifiers[pid] += 1
        ean = row.get("ean")
        if valid_gtin(ean):
            # Zero padding detects ambiguous aliases across GTIN lengths,
            # but NEVER changes the original identity for the Core join.
            gtins[ean.zfill(14)] += 1
    counts = {scope: Counter() for scope in SCOPES}
    for row in rows:
        ean = row.get("ean")
        code_valid = valid_gtin(ean)
        brand = explicit_brand(row.get("manufacturer"))
        unique = (code_valid and gtins[ean.zfill(14)] == 1
                  and identifiers[row["id"]] == 1)
        price = _cents(row.get("price_czk"))
        eligible = price is not None and delivery_state(row) in {
            "feed_stocked", "up_to_week", "unknown"}
        for scope in lane_members(row):
            bucket = counts[scope]
            bucket["source_rows"] += 1
            bucket["gtin_checksum_valid"] += int(code_valid)
            bucket["explicit_brand_field"] += int(brand)
            bucket["gtin_and_brand_fields"] += int(code_valid and brand)
            bucket["ambiguous_gtin_or_source_id"] += int(code_valid and not unique)
            bucket["unique_gtin_brand_price_dispatch_screen"] += int(unique and brand and eligible)
    keys = ("source_rows", "gtin_checksum_valid", "explicit_brand_field",
            "gtin_and_brand_fields", "ambiguous_gtin_or_source_id",
            "unique_gtin_brand_price_dispatch_screen")
    return {
        "state": "ONE_MERCHANT_SOURCE_SCREEN_ONLY",
        "source_merchant_count": 1,
        "scopes": {scope: {key: counts[scope][key] for key in keys} for scope in SCOPES},
        "second_merchant_source": "NOT_PROVIDED",
        "same_product_cross_merchant_matches": "UNKNOWN",
        "core_exact_projection_executed": False,
        "price_comparison_publish_ready": False,
        "brand_and_gtin_independent_proof": False,
        "merchant_stock_verified": False,
        "commission_attribution": "UNKNOWN",
        "wordpress_writes": 0, "affiliate_click_requests": 0,
        "raw_identifiers_or_brand_names_logged": 0,
    }


def main():
    report = profile(json.loads(CATALOG.read_text(encoding="utf-8")))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (PublishError, ValueError, TypeError, KeyError, OSError) as exc:
        print("XFIT_MULTISHOP_SOURCE_SCREEN_BLOCKED: " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)
