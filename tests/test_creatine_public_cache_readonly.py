"""No-write verification of real cache views, not search-crawler snapshots."""
import unittest
from unittest.mock import patch

from scripts import xfit_creatine_public_cache_readonly as audit
from scripts import xfit_creatine_disadvantages_onepost as content
from scripts.wp_publish import PublishError


def updated_post():
    return {
        "id": content.PINNED_POST_ID, "slug": content.SLUG,
        "link": content.URL, "status": "publish",
        "title": {"raw": content.NEW_TITLE},
        "content": {"raw": content.reviewed_document()},
        "excerpt": {"raw": content.EXCERPT},
        "modified_gmt": "2026-11-21T10:12:25",
    }


def public_page(*, title=content.NEW_TITLE, extra="", include_canonical=True,
                body=None):
    links = ('<link rel="canonical" href="' + content.URL + '">'
             if include_canonical else "")
    return (
        "<!DOCTYPE html><html><head><title>XFIT creatine</title>"
        + links + extra + "</head><body><h1>" + title + "</h1>"
        + (content.reviewed_document() if body is None else body)
        + "</body></html>"
    )


class CreatineCacheReadOnlyTests(unittest.TestCase):
    def test_exact_public_edit_and_links_match_and_noindex_absent(self):
        result = audit.inspect_html(public_page(),
                                    expected=content.reviewed_document())
        self.assertEqual(result["state"], "PUBLIC_EDITORIAL_FRESH")
        self.assertEqual(result["content_segments_expected"],
                         result["content_segments_matched"])
        self.assertTrue(result["all_five_reviewed_links_visible"])
        self.assertTrue(result["single_self_canonical"])
        self.assertFalse(result["noindex_seen"])
        self.assertEqual(result["legacy_unsupported_claims_visible"],
                         [False, False, False])

    def test_old_h1_and_partial_new_page_are_not_fresh(self):
        for page in (
            public_page(title=content.OLD_TITLE),
            public_page(body="<p>Stručná odpověď: Kreatin.</p>" * 20),
            public_page(include_canonical=False),
            public_page(extra='<meta name="robots" content="noindex,follow">'),
            public_page(body=content.reviewed_document().replace(
                content.PRIMARY_BUYER, "https://xfit.cz/other/")),
            public_page(body=content.reviewed_document() +
                        "<p>Kreatin může způsobit dehydrataci.</p>"),
        ):
            with self.subTest(page=page[-100:]):
                result = audit.inspect_html(page, expected=content.reviewed_document())
                self.assertEqual(result["state"], "PUBLIC_STALE_OR_DIFFERENT")

    def test_source_get_and_two_public_views_no_writes(self):
        calls = []
        def reader(*, bypass_cache=False):
            calls.append(bypass_cache)
            return public_page(), {"age": "0"}
        with patch.object(content, "wp_request") as writer:
            result = audit.audit(source_reader=lambda: [updated_post()],
                                 public_reader=reader)
            writer.assert_not_called()
        self.assertEqual(calls, [False, True])
        self.assertEqual(result["conclusion"], "ORDINARY_AND_BYPASS_PUBLIC_FRESH")
        self.assertEqual(result["wordpress_writes"], 0)
        self.assertEqual(result["affiliate_clicks"], 0)

    def test_stale_ordinary_cache_reported_even_when_no_cache_is_fresh(self):
        def reader(*, bypass_cache=False):
            return (public_page() if bypass_cache else
                    public_page(title=content.OLD_TITLE)), {"age": "42"}
        result = audit.audit(source_reader=lambda: [updated_post()],
                             public_reader=reader)
        self.assertEqual(result["conclusion"],
                         "PUBLIC_VIEW_DIVERGENCE_OR_UNAVAILABLE")
        self.assertEqual(result["views"]["ordinary_browser"]["state"],
                         "PUBLIC_STALE_OR_DIFFERENT")
        self.assertEqual(result["views"]["no_cache"]["state"],
                         "PUBLIC_EDITORIAL_FRESH")

    def test_public_read_errors_are_unknown_not_fresh(self):
        def reader(*, bypass_cache=False):
            if not bypass_cache:
                raise OSError("private target")
            return public_page(), {}
        result = audit.audit(source_reader=lambda: [updated_post()],
                             public_reader=reader)
        self.assertEqual(result["views"]["ordinary_browser"]["state"],
                         "PUBLIC_GET_UNKNOWN")
        self.assertNotIn("private target", str(result))

    def test_wp_drift_blocks_both_public_reads_and_all_writes(self):
        bad = updated_post()
        bad["content"]["raw"] = bad["content"]["raw"] + "<p>Another editor.</p>"
        with patch.object(content, "wp_request") as writer:
            with self.assertRaises(PublishError):
                audit.audit(source_reader=lambda: [bad],
                            public_reader=lambda **kwargs:
                            (_ for _ in ()).throw(AssertionError("unexpected public GET")))
            writer.assert_not_called()

    def test_workflow_readonly_only_one_commit_trigger(self):
        from pathlib import Path
        wf = Path(".github/workflows/xfit-creatine-ordinary-cache-readonly.yml").read_text(encoding="utf-8")
        self.assertIn("xfit_creatine_public_cache_readonly", wf)
        self.assertIn("if-no-files-found: error", wf)
        self.assertNotIn("schedule:", wf)
        self.assertNotIn("workflow_dispatch:", wf)
        self.assertNotIn(" snapshot", wf)
        self.assertNotIn(" apply", wf)


if __name__ == "__main__":
    unittest.main()
