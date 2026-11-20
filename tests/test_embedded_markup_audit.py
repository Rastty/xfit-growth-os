"""Read-only archive evidence and fail-closed pagination tests."""
import unittest

from scripts import xfit_embedded_markup_audit as a


def post(post_id=100, source="<p>Valid article</p>", modified="2026-11-20"):
    return {"id": post_id, "slug": f"article-{post_id}",
            "link": f"https://xfit.cz/article-{post_id}/", "modified": modified,
            "content": {"rendered": source}}


class MarkupAuditTests(unittest.TestCase):
    def test_plain_article_not_flagged(self):
        self.assertIsNone(a.examine(post()))

    def test_four_documents_and_fake_canonical_rank_high(self):
        corrupt = ("<!DOCTYPE html><html><head><title>Bad</title>"
                   '<link rel="canonical" href="https://www.example.com/fitness-diet-post">'
                   '</head><body>Text</body></html>') * 4
        result = a.examine(post(source=corrupt))
        self.assertEqual(result["doctype_count"], 4)
        self.assertEqual(result["bogus_canonical_count"], 4)
        self.assertEqual(result["confidence"], "HIGH")

    def test_single_tutorial_code_tag_is_low_confidence(self):
        result = a.examine(post(source="<p>To understand HTML use &lt;head&gt;</p><html>"))
        self.assertEqual(result["confidence"], "LOW_SNIPPET_POSSIBLE")

    def test_canonical_inside_article_high_confidence_even_without_doctype(self):
        result = a.examine(post(source='<link rel="canonical" href="https://example.test/">'))
        self.assertEqual(result["body_canonical_count"], 1)
        self.assertEqual(result["confidence"], "HIGH")

    def test_normal_link_to_other_article_is_not_canonical(self):
        self.assertIsNone(a.examine(post(source='<a href="https://example.com/article">External source</a>')))

    def test_complete_two_page_scan(self):
        def read(page, size):
            return ([post(page, '<html><head><title>Wrong</title></head></html>')], 2)
        result = a.audit(pages=2, size=1, reader=read)
        self.assertTrue(result["complete"])
        self.assertEqual(result["scanned_posts"], 2)
        self.assertEqual(result["wordpress_writes"], 0)

    def test_pagination_total_drift_marks_incomplete(self):
        def read(page, size):
            return ([post(page)], 3 if page == 1 else 4)
        result = a.audit(pages=3, size=1, reader=read)
        self.assertFalse(result["complete"])
        self.assertEqual(result["interruption"]["page"], 2)

    def test_conflicting_post_repeated_across_page_blocks_completion(self):
        def read(page, size):
            return ([post(100, modified=str(page))], 2)
        result = a.audit(pages=2, size=1, reader=read)
        self.assertFalse(result["complete"])
        self.assertEqual(result["interruption"]["page"], 2)

    def test_identical_repeated_post_counted_but_not_double_counted(self):
        def read(page, size):
            return ([post(100)], 2)
        result = a.audit(pages=2, size=1, reader=read)
        self.assertTrue(result["complete"])
        self.assertEqual(result["scanned_posts"], 1)
        self.assertEqual(result["repeated_same_record_count"], 1)

    def test_missing_content_aborts_with_no_absence_claim(self):
        def read(page, size):
            return ([{"id": 1, "slug": "x", "link": "https://xfit.cz/x/"}], 1)
        result = a.audit(pages=1, size=1, reader=read)
        self.assertFalse(result["complete"])
        self.assertEqual(result["scanned_posts"], 0)

    def test_empty_archive_page_not_a_complete_finding(self):
        result = a.audit(pages=2, size=1, reader=lambda page, size: ([], 2))
        self.assertFalse(result["complete"])

    def test_invalid_parameters_rejected(self):
        for pages, size in [(0, 1), (1, 0), (251, 100), (1, 101)]:
            with self.assertRaises(ValueError):
                a.audit(pages=pages, size=size, reader=lambda p, s: ([], 1))


if __name__ == "__main__":
    unittest.main()
