"""Regression tests for narrow legacy #10835 discovery: no WordPress mutations."""
import unittest
from scripts import xfit_legacy_target_preflight as audit


def post(*, body=None, **changes):
    if body is None:
        body = "<h2>Výběr podle ceny</h2>" + "<p>Praktické porovnání produktů.</p>" * 80
    data = {
        "id": 10835,
        "slug": audit.SLUG,
        "status": "publish",
        "link": audit.PUBLIC_URL,
        "title": {"raw": "Kde koupit nejlevnější kreatin pro fitness?"},
        "content": {"raw": body},
    }
    data.update(changes)
    return data


def public(url):
    assert url == audit.PUBLIC_URL
    return 200, url, "<html><h1>Kde koupit nejlevnější kreatin pro fitness?</h1></html>"


class LegacyTargetPreflightTests(unittest.TestCase):
    def test_verified_source_and_exact_public_permits_review_only(self):
        result = audit.review(post(), public_reader=public)
        self.assertEqual(result["source_state"], "PUBLISHED_SOURCE_VERIFIED")
        self.assertEqual(result["public_status"], "EXACT_PUBLIC_ARTICLE_CONFIRMED")
        self.assertEqual(result["decision"], "ELIGIBLE_FOR_MANUAL_ONEPOST_REVIEW")
        self.assertEqual(result["remote_writes"], 0)
        self.assertEqual(result["candidate_wp_id"], 10835)
        self.assertEqual(result["public_h2_preview"], ["Výběr podle ceny"])
        self.assertNotIn("Praktické porovnání produktů", str(result))

    def test_existing_advisor_anchor_skips_repeated_edit(self):
        raw = post()["content"]["raw"] + '<p><a href="' + audit.ADVISOR + '">Rady</a></p>'
        result = audit.review(post(body=raw), public_reader=public)
        self.assertTrue(result["advisor_link_already_present"])
        self.assertEqual(result["decision"], "ALREADY_LINKED")

    def test_plain_url_text_is_not_an_existing_link(self):
        raw = post()["content"]["raw"] + "<p>" + audit.ADVISOR + "</p>"
        result = audit.review(post(body=raw), public_reader=public)
        self.assertFalse(result["advisor_link_already_present"])

    def test_source_identity_or_intent_mismatch_fails_before_public_request(self):
        def never(_):
            self.fail("Unsafe public request for a nonmatching WordPress article")
        bad_changes = [
            {"id": 10836}, {"slug": "unrelated"},
            {"status": "draft"}, {"link": "https://evil.example/" + audit.SLUG + "/"},
            {"link": "https://xfit.cz/unrelated/"},
            {"title": {"raw": "Nejlevnější protein bez kreatinu?"}},
            {"content": {"raw": "short"}},
        ]
        for change in bad_changes:
            with self.subTest(change=change):
                result = audit.review(post(**change), public_reader=never)
                self.assertEqual(result["decision"], "BLOCKED_UNVERIFIED")
                self.assertEqual(result["remote_writes"], 0)

    def test_redirect_wrong_page_and_failed_public_read_block_release(self):
        for reader in (
            lambda _: (200, "https://xfit.cz/", "<h1>kreatin</h1>"),
            lambda _: (200, audit.PUBLIC_URL, "<h1>completely unrelated article</h1>"),
            lambda _: (404, audit.PUBLIC_URL, "<h1>kreatin</h1>"),
            lambda _: (_ for _ in ()).throw(OSError("secret query must not be printed")),
        ):
            with self.subTest(reader=reader):
                result = audit.review(post(), public_reader=reader)
                self.assertEqual(result["decision"], "BLOCKED_UNVERIFIED")
                self.assertNotIn("secret query", str(result))

    def test_strict_canonical_url_and_untrusted_domains(self):
        for url in (
            "http://xfit.cz/" + audit.SLUG + "/",
            "https://xfit.cz/" + audit.SLUG + "/?foo=bar",
            "https://other.example/" + audit.SLUG + "/",
            "https://xfit.cz:443/" + audit.SLUG + "/",
            "https://xfit.cz/" + audit.SLUG + "-other/",
            "https://user:pass@xfit.cz/" + audit.SLUG + "/",
        ):
            self.assertFalse(audit.exact_public_url(url), url)
        self.assertTrue(audit.exact_public_url(audit.PUBLIC_URL))
        self.assertTrue(audit.exact_public_url("https://www.xfit.cz/" + audit.SLUG))

    def test_heading_preview_redacts_email_and_urls(self):
        title = "https://example.com test@example.com"
        result = audit.clean_heading(title)
        self.assertNotIn("example.com", result)
        self.assertIn("[redacted]", result)

    def test_invalid_post_is_readonly_blocked(self):
        for source in (None, [], {}, "raw"):
            self.assertEqual(
                audit.review(source, public_reader=lambda _: self.fail("public GET")),
                {"candidate_wp_id": 10835, "candidate_slug": audit.SLUG,
                 "advisor_link_already_present": None, "public_status": "UNKNOWN",
                 "decision": "BLOCKED_UNVERIFIED", "remote_writes": 0,
                 "source_state": "IDENTITY_OR_STATUS_MISMATCH"})

if __name__ == "__main__":
    unittest.main()
