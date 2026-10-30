import json
import unittest
from pathlib import Path
from scripts.wp_publish import MARKER, PublishError, validate_document

SAMPLE = {
    "slug": "xfit-os-protein-guide",
    "title": "Jak vybrat protein: přehledný průvodce",
    "content": "<h2>Úvod</h2>" + ("Praktický kontrolovaný obsah. " * 18),
    "excerpt": "Výběr proteinu podle složení."
}

class PublisherValidationTests(unittest.TestCase):
    def test_valid_document_and_ownership_marker(self):
        doc = validate_document(SAMPLE)
        self.assertTrue(doc["content"].startswith(MARKER))
        self.assertEqual(doc["slug"], SAMPLE["slug"])

    def test_reject_non_namespaced_slug(self):
        doc = dict(SAMPLE, slug="vyziva")
        with self.assertRaises(PublishError):
            validate_document(doc)

    def test_reject_javascript(self):
        doc = dict(SAMPLE, content=SAMPLE["content"] + "<script>alert(1)</script>")
        with self.assertRaises(PublishError):
            validate_document(doc)

    def test_reject_short_content(self):
        doc = dict(SAMPLE, content="Krátký text")
        with self.assertRaises(PublishError):
            validate_document(doc)


    def test_pinned_post_id(self):
        doc = dict(SAMPLE, wp_post_id=25451)
        self.assertEqual(validate_document(doc)["wp_post_id"], 25451)

    def test_invalid_post_id_rejected(self):
        doc = dict(SAMPLE, wp_post_id="25451")
        with self.assertRaises(PublishError):
            validate_document(doc)

    def test_checked_in_first_article(self):
        doc = json.loads(Path("content/ready/xfit-os-protein-guide.json").read_text(encoding="utf-8"))
        validated = validate_document(doc)
        self.assertEqual(validated["slug"], "xfit-os-protein-guide")

if __name__ == "__main__":
    unittest.main()
