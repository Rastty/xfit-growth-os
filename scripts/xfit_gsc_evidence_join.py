#!/usr/bin/env python3
"""Join XFIT editorial triage with explicit, recent GSC *page* evidence.

Read-only and opt-in. This never requests credentials, infers missing traffic as
zero, or grants permission to edit WordPress. The input is a normalized,
owner-controlled GSC export from Prometheus, not a live API connection.
"""

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit


MAX_GSC_ROWS = 25000
MAX_DAYS_OLD = 14
EXPECTED_SOURCE = "google_search_console_page_aggregate"
EXPECTED_PROPERTY = {"sc-domain:xfit.cz", "https://xfit.cz/"}


def _date(value):
    if not isinstance(value, str):
        raise ValueError("GSC period must be ISO dates")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError("GSC period must be ISO dates") from None
    if parsed.isoformat() != value:
        raise ValueError("GSC period must be canonical ISO dates")
    return parsed


def _canonical_xfit_page(value):
    """Only an exact page URL is evidence for an exact archived permalink."""
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return (parsed.scheme == "https" and parsed.netloc == "xfit.cz"
            and parsed.path.startswith("/") and parsed.path.endswith("/")
            and "//" not in parsed.path and not parsed.query
            and not parsed.fragment and not parsed.username
            and not parsed.password and parsed.geturl() == value)


def _nonnegative_count(value):
    return type(value) is int and value >= 0


def parse_gsc_evidence(payload, *, as_of=None, window_days=(84, 100)):
    """Validate provenance, freshness, aggregation scope and unique pages.

    Absence from an export is *unknown*, because GSC may truncate exported rows.
    """
    now = as_of if as_of is not None else datetime.now(timezone.utc).date()
    if not isinstance(now, date) or isinstance(now, datetime):
        raise ValueError("as_of must be a date")
    if not isinstance(payload, dict) or payload.get("source") != EXPECTED_SOURCE:
        raise ValueError("Expected explicit GSC page aggregate evidence")
    if (not isinstance(payload.get("property"), str)
            or payload["property"] not in EXPECTED_PROPERTY):
        raise ValueError("GSC property is not verified XFIT")
    if payload.get("search_type") != "web" or payload.get("dimension") != "page":
        raise ValueError("GSC must be web search aggregated by page")
    start, end = _date(payload.get("start_date")), _date(payload.get("end_date"))
    if not window_days[0] <= (end - start).days + 1 <= window_days[1]:
        raise ValueError("Unexpected GSC observation window")
    if not 0 <= (now - end).days <= MAX_DAYS_OLD:
        raise ValueError("GSC evidence is future-dated or stale")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) > MAX_GSC_ROWS:
        raise ValueError("Invalid or unbounded GSC rows")
    by_page = {}
    ignored_noncanonical = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Malformed GSC page row")
        page, clicks, impressions = (row.get("page"), row.get("clicks"),
                                      row.get("impressions"))
        if not _nonnegative_count(clicks) or not _nonnegative_count(impressions):
            raise ValueError("GSC clicks and impressions must be integer counts")
        if clicks > impressions:
            raise ValueError("Clicks cannot exceed impressions")
        if not _canonical_xfit_page(page):
            ignored_noncanonical += 1
            continue
        if page in by_page:
            raise ValueError("Duplicate page key in GSC aggregate")
        by_page[page] = {"clicks": clicks, "impressions": impressions}
    return {
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "pages": by_page, "rows_supplied": len(rows),
        "rows_ignored_noncanonical": ignored_noncanonical,
        "coverage": "SUPPLIED_ROWS_ONLY_NOT_A_COMPLETE_SEARCH_CONSOLE_CENSUS",
    }


def parse_prometheus_baseline(payload, *, as_of=None):
    """Consume Prometheus' ACTUAL 28-day bounded XFIT GSC artifact format.

    Its top 20 directional candidates are not the complete 25,000-page GSC
    response. Missing queue URLs are unknown, even if not among those 20.
    """
    if (not isinstance(payload, dict) or payload.get("schemaVersion") != 1
            or payload.get("status") != "SOURCE_BACKED_GSC_BASELINE"
            or payload.get("source") != "Google Search Console Search Analytics API"
            or payload.get("mode") != "authenticated_read_only"
            or payload.get("site") != "https://xfit.cz/"
            or payload.get("wordpressWrites") != 0
            or payload.get("credentialsExported") is not False):
        raise ValueError("Not a verified read-only Prometheus GSC baseline")
    period = payload.get("period")
    rows = payload.get("prioritizedReviewCandidates")
    if (not isinstance(period, dict) or period.get("days") != 28
            or period.get("searchType") != "web"
            or period.get("dataState") != "final"
            or not isinstance(rows, list) or len(rows) > 20):
        raise ValueError("Unexpected Prometheus baseline scope")
    normalized_rows = []
    for item in rows:
        if not isinstance(item, dict) or not isinstance(item.get("slug"), str):
            raise ValueError("Malformed Prometheus page candidate")
        slug = item["slug"]
        if (not slug or "/" in slug or "?" in slug or "#" in slug
                or slug.strip() != slug):
            raise ValueError("Invalid Prometheus candidate slug")
        normalized_rows.append({
            "page": "https://xfit.cz/" + slug + "/",
            "clicks": item.get("clicks"),
            "impressions": item.get("impressions"),
        })
    normalized = {
        "source": EXPECTED_SOURCE, "property": payload.get("gscProperty"),
        "search_type": "web", "dimension": "page",
        "start_date": period.get("startDate"), "end_date": period.get("endDate"),
        "rows": normalized_rows,
    }
    report = parse_gsc_evidence(normalized, as_of=as_of, window_days=(28, 28))
    report["coverage"] = "PROMETHEUS_TOP_20_HEURISTIC_REVIEW_CANDIDATES_ONLY"
    report["source_format"] = "prometheus_xfit_native_28day_baseline"
    return report


def join_review_queue(archive, gsc, *, as_of=None):
    """Reorder preselected editorial candidates by measured exposure.

    This intentionally does NOT widen the archive's 70-item editorial queue.
    A fully measured all-posts priority model belongs in Prometheus Core.
    """
    if not isinstance(archive, dict) or archive.get("complete") is not True:
        raise ValueError("Archive audit is missing or incomplete")
    queue = archive.get("content_quality_review_queue")
    if (not isinstance(queue, dict) or queue.get("status") != "HUMAN_REVIEW_ONLY"
            or queue.get("no_wordpress_writes") is not True):
        raise ValueError("Missing safe editorial triage queue")
    candidates = queue.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > 70:
        raise ValueError("Invalid bounded editorial triage candidates")
    if isinstance(gsc, dict) and gsc.get("source") == "Google Search Console Search Analytics API":
        evidence = parse_prometheus_baseline(gsc, as_of=as_of)
        property_value = gsc["gscProperty"]
    else:
        evidence = parse_gsc_evidence(gsc, as_of=as_of)
        evidence["source_format"] = "normalized_private_90day_export"
        property_value = gsc["property"]
    output = []
    seen = set()
    for item in candidates:
        if not isinstance(item, dict) or not _canonical_xfit_page(item.get("url")):
            raise ValueError("Unsafe canonical archive candidate")
        if type(item.get("id")) is not int or item["id"] <= 0:
            raise ValueError("Invalid archive post ID")
        if item["id"] in seen:
            raise ValueError("Duplicate archive candidate")
        seen.add(item["id"])
        page = evidence["pages"].get(item["url"])
        if page is None:
            band, rank, click_key, impression_key = (
                "NO_GSC_ROW_IN_SUPPLIED_EXPORT_NOT_ZERO", 3, 0, 0)
            clicks, impressions = None, None
        else:
            clicks, impressions = page["clicks"], page["impressions"]
            if clicks >= 20:
                band, rank = "MEASURED_EXISTING_SEARCH_TRAFFIC", 0
            elif impressions >= 200:
                band, rank = "MEASURED_SEARCH_EXPOSURE", 1
            else:
                band, rank = "MEASURED_LOW_SEARCH_EXPOSURE", 2
            click_key, impression_key = clicks, impressions
        output.append({
            "id": item["id"], "url": item["url"], "title": item.get("title"),
            "topic": item.get("topic"), "editorial_priority_score": item.get("priority_score"),
            "editorial_reasons": item.get("reasons"),
            "gsc_evidence_state": band, "gsc_clicks": clicks,
            "gsc_impressions": impressions,
            "next_action": "EDITORIAL_AND_LIVE_SOURCE_REVIEW_ONLY",
            "_sort": (rank, -click_key, -impression_key,
                      -(item.get("priority_score") or 0), item["id"]),
        })
    output.sort(key=lambda x: x.pop("_sort"))
    return {
        "state": "GSC_EVIDENCE_JOIN_READ_ONLY", "mutated_wordpress": False,
        "gsc_period": evidence["start_date"] + ".." + evidence["end_date"],
        "gsc_property": property_value,
        "gsc_source_format": evidence["source_format"],
        "gsc_export_coverage": evidence["coverage"],
        "gsc_supplied_rows": evidence["rows_supplied"],
        "gsc_noncanonical_rows_ignored": evidence["rows_ignored_noncanonical"],
        "matched_candidates": sum(x["gsc_clicks"] is not None for x in output),
        "unmatched_candidates_are_unknown_not_zero": sum(
            x["gsc_clicks"] is None for x in output),
        "limited_to_existing_triage_candidates": len(candidates),
        "not_measured": "GA4_landing_sessions_conversion_events_affiliate_revenue",
        "candidates": output,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--gsc", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    # The private GSC input/output stay outside the public Git checkout.
    repo_root = Path(__file__).resolve().parent.parent
    for path in (args.gsc, args.output):
        if path.resolve().is_relative_to(repo_root):
            parser.error("Private GSC input/output must be outside the Git repository")
    output = join_review_queue(
        json.loads(args.archive.read_text(encoding="utf-8")),
        json.loads(args.gsc.read_text(encoding="utf-8")))
    if args.output.exists():
        parser.error("Refusing to overwrite existing GSC evidence output")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in output.items() if k != "candidates"},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
