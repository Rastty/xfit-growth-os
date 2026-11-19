import copy
from datetime import date
import unittest

from scripts.xfit_gsc_evidence_join import (
    join_review_queue, nonsecret_summary, parse_gsc_evidence,
    parse_prometheus_baseline,
)


TODAY = date(2026, 11, 17)


def evidence():
    return {
        "source": "google_search_console_page_aggregate",
        "property": "sc-domain:xfit.cz", "search_type": "web",
        "dimension": "page", "start_date": "2026-08-16", "end_date": "2026-11-13",
        "rows": [
            {"page": "https://xfit.cz/protein/", "clicks": 45, "impressions": 600},
            {"page": "https://xfit.cz/kreatin/", "clicks": 4, "impressions": 300},
            {"page": "https://other.example/spam/", "clicks": 500, "impressions": 2000},
        ],
    }


def archive():
    return {
        "complete": True,
        "content_quality_review_queue": {
            "status": "HUMAN_REVIEW_ONLY", "no_wordpress_writes": True,
            "candidates": [
                {"id": 1, "url": "https://xfit.cz/kreatin/", "title": "Kreatin",
                 "topic": "kreatin", "priority_score": 20, "reasons": ["old_promo"]},
                {"id": 2, "url": "https://xfit.cz/protein/", "title": "Protein",
                 "topic": "protein", "priority_score": 9, "reasons": ["old_promo"]},
                {"id": 3, "url": "https://xfit.cz/hubnuti/", "title": "Hubnutí",
                 "topic": "hubnutí", "priority_score": 11, "reasons": ["old_promo"]},
            ],
        },
    }


def native_prometheus_baseline():
    return {
        "schemaVersion": 1, "status": "SOURCE_BACKED_GSC_BASELINE",
        "source": "Google Search Console Search Analytics API",
        "mode": "authenticated_read_only", "site": "https://xfit.cz/",
        "gscProperty": "https://xfit.cz/", "wordpressWrites": 0,
        "credentialsExported": False,
        "period": {
            "startDate": "2026-10-17", "endDate": "2026-11-13",
            "days": 28, "searchType": "web", "dataState": "final",
        },
        "prioritizedReviewCandidates": [
            {"slug": "protein", "clicks": 22, "impressions": 280},
        ],
    }


class EvidenceJoinTests(unittest.TestCase):
    def test_reorders_only_by_measured_opportunity_and_keeps_unknown(self):
        result = join_review_queue(archive(), evidence(), as_of=TODAY)
        self.assertEqual([row["id"] for row in result["candidates"]], [2, 1, 3])
        self.assertEqual(result["matched_candidates"], 2)
        self.assertEqual(result["unmatched_candidates_are_unknown_not_zero"], 1)
        self.assertIsNone(result["candidates"][-1]["gsc_clicks"])
        self.assertEqual(result["candidates"][-1]["gsc_evidence_state"],
                         "NO_GSC_ROW_IN_SUPPLIED_EXPORT_NOT_ZERO")
        self.assertEqual(result["gsc_noncanonical_rows_ignored"], 1)
        self.assertFalse(result["mutated_wordpress"])
        self.assertNotIn("_sort", result["candidates"][0])

    def test_zero_is_not_missing(self):
        e = evidence()
        e["rows"] = [{"page": "https://xfit.cz/hubnuti/", "clicks": 0,
                      "impressions": 0}]
        result = join_review_queue(archive(), e, as_of=TODAY)
        self.assertEqual(result["matched_candidates"], 1)
        self.assertEqual(result["candidates"][0]["gsc_clicks"], 0)

    def test_source_backed_exposure_outside_archive_queue_is_separate(self):
        e = evidence()
        e["rows"] = [
            {"page": "https://xfit.cz/pilates-rozdily/", "clicks": 1,
             "impressions": 105},
            {"page": "https://xfit.cz/kreatin-pro-zacatecniky/", "clicks": 0,
             "impressions": 39},
            {"page": "https://not-xfit.example/foreign/", "clicks": 10,
             "impressions": 400},
            {"page": "https://xfit.cz/zero-exposure/", "clicks": 0,
             "impressions": 0},
        ]
        result = join_review_queue(archive(), e, as_of=TODAY)
        self.assertEqual(result["matched_candidates"], 0)
        self.assertEqual(result["unmatched_candidates_are_unknown_not_zero"], 3)
        self.assertEqual(result["limited_to_existing_triage_candidates"], 3)
        self.assertEqual(result["outside_triage_exposed_pages_in_supplied_gsc"], 2)
        self.assertFalse(result["outside_triage_exposure_truncated"])
        outside = result["outside_triage_exposure_review_only"]
        self.assertEqual([row["gsc_impressions"] for row in outside], [105, 39])
        self.assertEqual(outside[0]["url"],
                         "https://xfit.cz/pilates-rozdily/")
        self.assertTrue(all(row["review_scope"] ==
                            "GSC_EXPOSURE_ONLY_NOT_EDITORIAL_TRIAGE"
                            for row in outside))
        self.assertTrue(all(row["next_action"] ==
                            "VERIFY_LIVE_SOURCE_AND_SEARCH_INTENT_ONLY"
                            for row in outside))
        self.assertEqual({row["id"] for row in result["candidates"]}, {1, 2, 3})
        self.assertFalse(result["mutated_wordpress"])

    def test_outside_triage_exposure_bounded_and_logs_hide_urls(self):
        e = evidence()
        e["rows"] = [
            {"page": f"https://xfit.cz/only-gsc-{index}/",
             "clicks": 0, "impressions": index + 1}
            for index in range(25)
        ]
        result = join_review_queue(archive(), e, as_of=TODAY)
        self.assertEqual(result["outside_triage_exposed_pages_in_supplied_gsc"], 25)
        self.assertTrue(result["outside_triage_exposure_truncated"])
        outside = result["outside_triage_exposure_review_only"]
        self.assertEqual(len(outside), 20)
        self.assertEqual(outside[0]["url"], "https://xfit.cz/only-gsc-24/")
        self.assertEqual(outside[-1]["url"], "https://xfit.cz/only-gsc-5/")
        summary = nonsecret_summary(result)
        self.assertNotIn("candidates", summary)
        self.assertNotIn("outside_triage_exposure_review_only", summary)
        self.assertNotIn("only-gsc-24", str(summary))
        self.assertEqual(summary["outside_triage_exposed_pages_in_supplied_gsc"], 25)

    def test_incomplete_archive_rejected(self):
        a = archive()
        a["complete"] = False
        with self.assertRaises(ValueError):
            join_review_queue(a, evidence(), as_of=TODAY)

    def test_noncanonical_archive_candidate_rejected(self):
        a = archive()
        a["content_quality_review_queue"]["candidates"][0]["url"] = (
            "https://xfit.cz/kreatin/?utm_medium=partner")
        with self.assertRaises(ValueError):
            join_review_queue(a, evidence(), as_of=TODAY)

    def test_duplicate_archive_id_rejected(self):
        a = archive()
        a["content_quality_review_queue"]["candidates"][1]["id"] = 1
        with self.assertRaises(ValueError):
            join_review_queue(a, evidence(), as_of=TODAY)

    def test_wrong_property_aggregation_or_source_rejected(self):
        for key, value in [("source", "ga4"), ("property", "sc-domain:other.cz"),
                           ("search_type", "image"), ("dimension", "query")]:
            with self.subTest(field=key):
                e = evidence()
                e[key] = value
                with self.assertRaises(ValueError):
                    parse_gsc_evidence(e, as_of=TODAY)

    def test_stale_future_short_period_or_malformed_date_rejected(self):
        for key, value in [("end_date", "2026-10-01"),
                           ("end_date", "2026-12-01"),
                           ("start_date", "2026-11-01"),
                           ("start_date", "2026-08-16T00:00:00")]:
            with self.subTest(field=key, value=value):
                e = evidence()
                e[key] = value
                with self.assertRaises(ValueError):
                    parse_gsc_evidence(e, as_of=TODAY)

    def test_duplicate_canonical_page_rejected(self):
        e = evidence()
        e["rows"].append(copy.deepcopy(e["rows"][0]))
        with self.assertRaises(ValueError):
            parse_gsc_evidence(e, as_of=TODAY)

    def test_bad_counts_and_booleans_rejected(self):
        for clicks, impressions in [(True, 2), (-1, 3), (4, 3), ("0", 0), (1, 2.5)]:
            with self.subTest(clicks=clicks, impressions=impressions):
                e = evidence()
                e["rows"][0].update(clicks=clicks, impressions=impressions)
                with self.assertRaises(ValueError):
                    parse_gsc_evidence(e, as_of=TODAY)

    def test_noncanonical_host_or_query_is_not_matched(self):
        e = evidence()
        e["rows"] = [
            {"page": "http://xfit.cz/kreatin/", "clicks": 1, "impressions": 20},
            {"page": "https://www.xfit.cz/protein/", "clicks": 1, "impressions": 20},
            {"page": "https://xfit.cz/protein/?ref=other", "clicks": 1, "impressions": 20},
            {"page": "https://xfit.cz/protein/", "clicks": 1, "impressions": 20},
        ]
        report = join_review_queue(archive(), e, as_of=TODAY)
        self.assertEqual(report["gsc_noncanonical_rows_ignored"], 3)
        self.assertEqual(report["matched_candidates"], 1)

    def test_no_automatic_write_evidence_and_bounded_archive_queue(self):
        a = archive()
        a["content_quality_review_queue"]["no_wordpress_writes"] = False
        with self.assertRaises(ValueError):
            join_review_queue(a, evidence(), as_of=TODAY)
        a["content_quality_review_queue"]["no_wordpress_writes"] = True
        a["content_quality_review_queue"]["candidates"] *= 25
        with self.assertRaises(ValueError):
            join_review_queue(a, evidence(), as_of=TODAY)

    def test_existing_prometheus_core_28day_baseline_is_compatible(self):
        result = join_review_queue(archive(), native_prometheus_baseline(), as_of=TODAY)
        self.assertEqual(result["gsc_source_format"], "prometheus_xfit_native_28day_baseline")
        self.assertEqual(result["gsc_period"], "2026-10-17..2026-11-13")
        self.assertEqual(result["matched_candidates"], 1)
        self.assertEqual(result["candidates"][0]["id"], 2)
        self.assertEqual(result["unmatched_candidates_are_unknown_not_zero"], 2)
        self.assertIn("TOP_20", result["gsc_export_coverage"])

    def test_prometheus_source_candidate_without_archive_match_survives(self):
        baseline = native_prometheus_baseline()
        baseline["prioritizedReviewCandidates"] = [
            {"slug": "pilates-porovnani", "clicks": 1, "impressions": 105},
        ]
        result = join_review_queue(archive(), baseline, as_of=TODAY)
        self.assertEqual(result["matched_candidates"], 0)
        self.assertEqual(result["unmatched_candidates_are_unknown_not_zero"], 3)
        self.assertEqual(result["outside_triage_exposed_pages_in_supplied_gsc"], 1)
        self.assertEqual(result["outside_triage_exposure_review_only"][0]["url"],
                         "https://xfit.cz/pilates-porovnani/")

    def test_prometheus_baseline_provenance_and_window_fail_closed(self):
        for field, value in [("status", "GSC_SOURCE_UNAVAILABLE"),
                             ("credentialsExported", True), ("wordpressWrites", 1),
                             ("gscProperty", "https://evil.invalid/")]:
            with self.subTest(field=field):
                e = native_prometheus_baseline()
                e[field] = value
                with self.assertRaises(ValueError):
                    parse_prometheus_baseline(e, as_of=TODAY)
        for field, value in [("days", 90), ("dataState", "all"),
                             ("endDate", "2026-11-01")]:
            with self.subTest(field=field):
                e = native_prometheus_baseline()
                e["period"][field] = value
                with self.assertRaises(ValueError):
                    parse_prometheus_baseline(e, as_of=TODAY)

    def test_prometheus_native_candidate_cap_and_duplicate_key(self):
        e = native_prometheus_baseline()
        e["prioritizedReviewCandidates"] *= 21
        with self.assertRaises(ValueError):
            parse_prometheus_baseline(e, as_of=TODAY)
        e["prioritizedReviewCandidates"] = [
            {"slug": "protein", "clicks": 2, "impressions": 3},
            {"slug": "protein", "clicks": 2, "impressions": 3},
        ]
        with self.assertRaises(ValueError):
            parse_prometheus_baseline(e, as_of=TODAY)


if __name__ == "__main__":
    unittest.main()
