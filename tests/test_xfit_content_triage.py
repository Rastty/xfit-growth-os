import unittest
from datetime import date

from scripts.xfit_content_triage import build_review_queue, MAX_OUTPUT, PER_TOPIC_LIMIT
from scripts.xfit_archive_full import inventory


def row(i, title="Jak funguje kreatin a ledviny", *, modified="2023-05-01T10:00:00", promo=3,
        links=0, hosts=None, slug=None, off=False, spam=False):
    slug = slug or f"kreatin-ledviny-{i}"
    return {"id": i, "slug": slug, "url": f"https://xfit.cz/{slug}/",
            "title": title, "modified": modified, "body_chars": 2600,
            "stale_2022_promo_mentions": promo, "internal_link_count": links,
            "external_hosts": hosts or {}, "suspect_thin": False,
            "suspect_offtopic": off, "suspect_spam": spam}


class ContentQualityQueueTests(unittest.TestCase):
    REF = date(2026, 11, 17)

    def test_audited_old_coupon_is_human_review_only(self):
        report = build_review_queue([row(4800)], as_of=self.REF)
        self.assertEqual(report["status"], "HUMAN_REVIEW_ONLY")
        self.assertTrue(report["no_wordpress_writes"])
        self.assertEqual(report["eligible_review_candidates"], 1)
        candidate = report["candidates"][0]
        self.assertEqual(candidate["id"], 4800)
        self.assertIn("expired_2022_promo_visible_in_archive", candidate["reasons"])
        self.assertIn("health_claim_review_required", candidate["reasons"])
        self.assertIn("no_recognized_scientific_host_in_archive_sample", candidate["reasons"])
        self.assertIn("not_measured", report["ranking_kind"])

    def test_valid_scientific_host_removes_only_evidence_warning(self):
        candidate = build_review_queue([row(1, hosts={"ods.od.nih.gov":1})], as_of=self.REF)["candidates"][0]
        self.assertNotIn("no_recognized_scientific_host_in_archive_sample", candidate["reasons"])
        self.assertIn("health_claim_review_required", candidate["reasons"])

    def test_recent_future_missing_or_noncanonical_excluded(self):
        posts = [row(1, modified="2026-11-16T10:00:00"),
                 row(2, modified="2026-11-18T10:00:00"),
                 row(3, modified=None),
                 dict(row(4), url="https://not-xfit.example/other/"),
                 row(5, modified="2026-10-30T00:00:00")]
        report = build_review_queue(posts, as_of=self.REF)
        self.assertEqual([c["id"] for c in report["candidates"]], [5])
        self.assertEqual(report["skipped_recent"], 1)
        self.assertEqual(report["skipped_unknown_or_future_date"], 2)

    def test_spam_and_offtopic_are_separate_lanes(self):
        report = build_review_queue([row(1, spam=True), row(2, off=True), row(3)], as_of=self.REF)
        self.assertEqual([c["id"] for c in report["candidates"]], [3])

    def test_topic_diversity_and_stable_order(self):
        posts = [row(i) for i in range(1, 50)]
        posts += [row(100+i, title="Protein a síla", slug=f"protein-tipy-{i}") for i in range(45)]
        queue = build_review_queue(posts, as_of=self.REF)
        self.assertLessEqual(queue["shown"], MAX_OUTPUT)
        self.assertLessEqual(max(queue["topic_distribution"].values()), PER_TOPIC_LIMIT)
        self.assertEqual(queue, build_review_queue(list(reversed(posts)), as_of=self.REF))
        self.assertEqual(queue["eligible_review_candidates"], len(posts))

    def test_no_promo_but_health_claims_need_review(self):
        review = build_review_queue([row(1, promo=0, links=2)], as_of=self.REF)
        self.assertEqual(review["shown"], 1)
        self.assertNotIn("expired_2022_promo_visible_in_archive", review["candidates"][0]["reasons"])

    def test_full_archive_integration_no_remote_writes(self):
        post = {"id": 123, "slug": "kreatin-ledviny-123",
                "link": "https://xfit.cz/kreatin-ledviny-123/",
                "title": {"rendered": "Kreatin a ledviny: bezpečnost"},
                "modified": "2023-05-01T00:00:00",
                "content": {"rendered": "<h2>Kreatin</h2><p>5NM2022</p>"}}
        report = inventory([post])
        self.assertEqual(report["stale_2022_promo_posts"], 1)
        self.assertEqual(report["content_quality_review_queue"]["candidates"][0]["id"], 123)
        self.assertTrue(report["content_quality_review_queue"]["no_wordpress_writes"])

    def test_reference_date_must_be_explicit_date(self):
        with self.assertRaises(ValueError):
            build_review_queue([], as_of="2026-11-17")


if __name__ == "__main__":
    unittest.main()
