import copy
from datetime import date
import unittest

from scripts.xfit_gsc_evidence_join import join_review_queue, parse_gsc_evidence


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


if __name__ == "__main__":
    unittest.main()
