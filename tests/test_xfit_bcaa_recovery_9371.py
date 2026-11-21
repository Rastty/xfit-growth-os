"""Guardrails for staged BCAA WP #9371 editorial replacement; never publishes."""
import json
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit

from scripts.xfit_editorial_gate import check_document

CONTENT = Path("content/revisions/bcaa-recovery-9371.html")
MANIFEST = Path("content/revisions/bcaa-recovery-9371.manifest.json")

LINKS = (
    "https://xfit.cz/xfit-os-protein-guide/",
    "https://xfit.cz/bcaa-vs-whey-protein-jake-jsou-rozdily-a-ktere-doplneni-je-pro-vas-nejlepsi/",
    "https://xfit.cz/xfit-os-kreatin-nebo-protein/",
)
SOURCES = (
    "https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC5477153/",
)


class Bcaa9371ReviewTests(unittest.TestCase):
    def setUp(self):
        self.body = CONTENT.read_text(encoding="utf-8")
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_quality_and_readability(self):
        result = check_document({"content": self.body})
        self.assertGreaterEqual(result["word_count"], 850)
        self.assertGreaterEqual(result["h2_count"], 8)
        self.assertEqual(self.body.count('data-xfit-bcaa-9371="v1"'), 1)
        self.assertEqual(self.body.count("<nav "), 1)

    def test_no_legacy_document_tags_or_coupon(self):
        for bad in (r"<!doctype", r"<html\b", r"<head\b", r"<body\b",
                    r"<link\b", r"<script\b", r"<iframe\b", r"<form\b",
                    r"<style\b", r"\bon\w+\s*=", r"5nm2022", r"example\.com"):
            with self.subTest(bad=bad):
                self.assertNotRegex(self.body.lower(), bad)

    def test_internal_decision_links_have_large_touch_targets(self):
        for target in LINKS:
            self.assertEqual(self.body.count('href="' + target + '"'), 1)
        self.assertEqual(self.body.count("min-height:48px"), 3)
        self.assertIn("Nejdřív ověřit", self.body)
        self.assertIn("žádný doplněk", self.body.lower())

    def test_source_links_and_allowed_hosts_only(self):
        for source in SOURCES:
            self.assertEqual(self.body.count('href="' + source + '"'), 1)
        urls = re.findall(r'href="([^"]+)"', self.body)
        self.assertEqual(len(urls), len(LINKS) + len(SOURCES))
        for url in urls:
            self.assertEqual(urlsplit(url).scheme, "https")
            self.assertIn(urlsplit(url).hostname,
                          {"xfit.cz", "ods.od.nih.gov", "pmc.ncbi.nlm.nih.gov"})

    def test_exact_source_pin_and_no_publish_permission(self):
        m = self.manifest
        self.assertEqual(m["state"], "PREPARED_NOT_DEPLOYED")
        self.assertEqual(m["post_id"], 9371)
        self.assertEqual(m["reviewed_source"]["modified_gmt"], "2023-10-21T07:44:55")
        self.assertEqual(m["reviewed_source"]["authenticated_raw_sha256"],
                         "e6deec0b5bba9c52457d3cb3dbd141f4ef8eeb3b2d531408054084e8a2e8de20")
        self.assertEqual(m["reviewed_source"]["body_canonical_host"], "www.example.com")
        self.assertEqual(m["reviewed_source"]["stale_coupon_count"], 3)
        self.assertEqual(m["reviewed_source"]["nested_doctype_count"], 3)
        self.assertIs(m["release_policy"]["wordpress_write_permitted"], False)
        self.assertEqual(m["content_path"], str(CONTENT))
        self.assertEqual(len(m["release_policy"]["requirements"]), 5)


if __name__ == "__main__":
    unittest.main()
