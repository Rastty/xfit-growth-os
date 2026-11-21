"""No-write, exact-Pilates-source regressions for GSC supporting article."""
import contextlib
from io import StringIO
import json
import unittest
from unittest.mock import patch

from scripts import xfit_pilates_sibling_source as audit
from scripts.wp_publish import PublishError


def source(body=None, *, post_id=1234, slug=audit.SLUG):
    if body is None:
        body = "<p>Jak si vybrat pilates a klasické cvičení.</p>" * 30
    return [{
        "id": post_id,
        "slug": slug,
        "status": "publish",
        "link": "https://xfit.cz/" + slug + "/",
        "title": {"raw": "Pilates vs. klasické cvičení"},
        "content": {"raw": body},
        "modified_gmt": "2026-11-19T10:00:00",
    }]


def public(*, extra_title="", canonical=None, noindex=""):
    canonical = canonical or audit.URL
    return (
        '<html><head><title>Pilates vs klasické cvičení</title>' +
        extra_title + '<link rel="canonical" href="' + canonical + '">'
        + noindex + '</head><body><h1>Pilates vs. klasické cvičení</h1>'
        + '<p>Základy a rozdíly pro začátečníky.</p></body></html>'
    ), ""


class SupportingPilatesSourceTests(unittest.TestCase):
    def test_source_exact_identity_and_structural_proof(self):
        result = audit.source_assess(source())
        self.assertEqual(result["post_id"], 1234)
        self.assertEqual(result["raw_embedded_complete_document_markers"], False)
        self.assertFalse(result["source_link_to_primary"])
        self.assertEqual(len(result["raw_sha256"]), 64)
        self.assertNotIn("Jak si vybrat", json.dumps(result))
        self.assertTrue(result["title_contains_pilates"])

    def test_preflight_is_candidate_without_auto_authorization(self):
        report = audit.evidence(authenticated_reader=lambda: source(),
                                public_reader=lambda slug: public())
        self.assertEqual(report["state"], "SOURCE_VERIFIED_LINK_REVIEW_CANDIDATE")
        self.assertFalse(report["release_permitted"])
        self.assertEqual(report["wordpress_post_attempts"], 0)
        self.assertEqual(report["public"]["head_title_tag_count"], 1)

    def test_duplicate_public_title_hold_not_falsely_called_link_gap(self):
        extra = "<title>Duplicate embedded title</title>"
        report = audit.evidence(authenticated_reader=lambda: source(),
                                public_reader=lambda slug: public(extra_title=extra))
        self.assertEqual(report["state"], "HOLD_LEGACY_MARKUP_REVIEW")
        self.assertEqual(report["public"]["head_title_tag_count"], 2)

    def test_source_embedded_document_hold(self):
        html = "<!DOCTYPE html><html><head><title>Old copy</title></head></html>"
        report = audit.evidence(
            authenticated_reader=lambda: source(
                "<p>Pilates pravidla.</p>" * 40 + html),
            public_reader=lambda slug: public(),
        )
        self.assertEqual(report["state"], "HOLD_LEGACY_MARKUP_REVIEW")
        self.assertTrue(report["source"]["raw_embedded_complete_document_markers"])

    def test_noindex_or_nonself_canonical_hold(self):
        for html in (
            public(canonical="https://evil.example/a/"),
            public(noindex='<meta name="robots" content="noindex,follow">'),
        ):
            report = audit.evidence(
                authenticated_reader=lambda: source(),
                public_reader=lambda slug, page=html: page,
            )
            self.assertEqual(report["state"], "HOLD_LEGACY_MARKUP_REVIEW")

    def test_exact_slug_only_and_no_overbroad_lookup(self):
        for bad in (
            [], source(post_id=0),
            source(slug="unrelated-article"),
            source() * 2,
            source(body="short"),
        ):
            with self.subTest(bad=str(bad)[:90]), self.assertRaises(PublishError):
                audit.source_assess(bad)

    def test_missing_auth_or_network_fails_closed_and_redacted(self):
        output = StringIO()
        with patch.object(audit, "evidence", side_effect=PublishError("SECRET")), \
             contextlib.redirect_stdout(output), \
             self.assertRaises(SystemExit):
            audit.main()
        report = json.loads(output.getvalue())
        self.assertEqual(report["state"], "READ_ONLY_SIBLING_SOURCE_INCOMPLETE")
        self.assertNotIn("SECRET", output.getvalue())
        self.assertFalse(report["release_permitted"])


if __name__ == "__main__":
    unittest.main()
