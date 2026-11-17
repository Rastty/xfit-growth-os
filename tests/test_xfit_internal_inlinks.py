"""Privacy, coverage semantics and canonical target tests for post-body links."""

import unittest

from scripts.xfit_internal_inlinks import (
    GUIDE_SLUGS, MAX_SOURCE_EXAMPLES, build_coverage, target_from_href,
)
from scripts.xfit_archive_full import inventory


def make_post(post_id, slug, content, *, source_url=None):
    return {
        "id": post_id,
        "slug": slug,
        "link": source_url or f"https://xfit.cz/{slug}/",
        "title": {"rendered": slug},
        "content": {"rendered": content},
        "modified": "2026-11-17T00:00:00",
    }


def guide(report, slug):
    return next(p for p in report["guides"] if p["slug"] == slug)


class CoverageTests(unittest.TestCase):
    def test_all_six_guides_are_reported_without_claiming_seo_orphans(self):
        result = build_coverage([])
        self.assertEqual([p["slug"] for p in result["guides"]], list(GUIDE_SLUGS))
        self.assertEqual(result["posts_examined"], 0)
        self.assertTrue(result["no_wordpress_writes"])
        self.assertIn("menus", result["not_covered"])

    def test_genuine_anchor_sources_are_deduplicated_and_self_links_ignored(self):
        target = "xfit-os-kreatin-poradce"
        posts = [
            make_post(7, "kreatin-zacatky", f'<a href="/{target}/">Přejít</a>'
                      f'<a href="https://www.xfit.cz/{target}/#faq">FAQ</a>'),
            make_post(8, "kreatin-dalsi", f'<a href="https://xfit.cz/{target}/?utm_source=legacy">Info</a>'),
            make_post(9, target, f'<a href="/{target}/">Já</a>'),
            make_post(7, "kreatin-zacatky", f'<a href="/{target}/">Duplikát strany</a>'),
        ]
        result = build_coverage(posts)
        self.assertEqual(guide(result, target)["source_post_count"], 2)
        self.assertEqual(guide(result, target)["sample_source_posts"], [
            {"id": 7, "slug": "kreatin-zacatky"}, {"id": 8, "slug": "kreatin-dalsi"},
        ])
        # The main archive deduplicates WP pagination records before this step.
        from_archive = inventory(posts)["guide_inlink_coverage"]
        self.assertEqual(guide(from_archive, target)["source_post_count"], 2)

    def test_no_false_positives_from_templates_comments_or_non_anchor_text(self):
        target = "xfit-os-protein-guide"
        markup = (
            f'<!-- <a href="/{target}/">hidden</a> -->'
            f'<template><a href="/{target}/">template</a></template>'
            f'<script>"<a href=\'/{target}/\'>"</script>'
            f'<span data-href="/{target}/">text</span>'
            f'<a href="https://example.org/{target}/">offsite</a>'
            f'<a href="https://xfit.cz.evil.example/{target}/">offsite</a>'
        )
        self.assertTrue(guide(build_coverage([make_post(1, "jina", markup)]), target)
                        ["no_post_body_inlink_observed"])

    def test_untrusted_hosts_credentials_ports_and_lookalike_paths_are_ignored(self):
        target = "xfit-os-protein-guide"
        base = "https://xfit.cz/jiny-clanek/"
        rejected = (
            f"https://evil.example/{target}/",
            f"https://xfit.cz.evil.example/{target}/",
            f"https://test@xfit.cz/{target}/",
            f"https://xfit.cz:443/{target}/",
            f"http://evil.example/{target}/",
            f"/{target}-fake/",
            f"/another/{target}/",
            "javascript:alert(1)",
            "#in-page",
            "//evil.example/" + target + "/",
            "https://[broken/",
        )
        for href in rejected:
            with self.subTest(href=href):
                self.assertIsNone(target_from_href(href, base))
        self.assertIsNone(target_from_href(f"/{target}/", "https://bad.example/article/"))
        self.assertEqual(target_from_href(f"/{target}/#pricing", base), target)

    def test_sample_is_bounded_stable_and_does_not_expose_urls_or_queries(self):
        target = "xfit-os-syrovatkovy-protein-porovnani"
        posts = [make_post(i, f"clanek-{i}",
                           f'<a href="/{target}/?sensitive=should-not-appear">Info</a>')
                 for i in range(100, 100 + MAX_SOURCE_EXAMPLES + 3)][::-1]
        row = guide(build_coverage(posts), target)
        self.assertEqual(row["source_post_count"], MAX_SOURCE_EXAMPLES + 3)
        self.assertEqual(len(row["sample_source_posts"]), MAX_SOURCE_EXAMPLES)
        self.assertTrue(row["source_sample_truncated"])
        self.assertEqual(row["sample_source_posts"][0]["id"], 100)
        self.assertNotIn("sensitive", str(row))

    def test_non_post_body_structures_do_not_count_as_inlinks(self):
        target = "xfit-os-kreatin-nebo-protein"
        data = [make_post(3, "co-je-protein", f'<p>Viz {target}.</p>')]
        self.assertEqual(guide(build_coverage(data), target)["source_post_count"], 0)

    def test_archiver_carries_coverage_from_deduplicated_post_inventory(self):
        target = "xfit-os-doplnky-pro-zacatecniky"
        p = make_post(42, "pruvodce", f'<a href="/{target}/">Návod</a>')
        result = inventory([p, p])
        self.assertEqual(result["scanned"], 1)
        self.assertEqual(result["guide_inlink_coverage"]["posts_examined"], 1)
        self.assertEqual(guide(result["guide_inlink_coverage"], target)["source_post_count"], 1)


if __name__ == "__main__":
    unittest.main()
