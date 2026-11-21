"""Source/public GSC Pilates preflight must remain read-only and fail closed."""
import contextlib
from io import StringIO
import json
import unittest
from unittest.mock import patch

from scripts import xfit_pilates_gsc_preflight as p
from scripts import xfit_pilates_gsc_title_release as title
from scripts.wp_publish import PublishError


def html_for(slug, heading, *, canonical=None, link=False, noindex=False):
    canonical = canonical if canonical is not None else "https://xfit.cz/" + slug + "/"
    robots = '<meta name="robots" content="noindex">' if noindex else ""
    return (
        "<!DOCTYPE html><html><head><title>" + heading + " | XFIT</title>"
        '<link rel="canonical" href="' + canonical + '">' + robots +
        "</head><body><h1>" + heading + "</h1>"
        + ('<p><a href="' + title.URL + '">Klasické a power pilates</a></p>'
           if link else "") +
        "</body></html>"
    )


def post(source_title):
    # Reuse the real classifier but isolate network via source-bound fixture.
    return {
        "id": title.POST_ID, "slug": title.SLUG, "status": "publish",
        "link": title.URL, "title": {"raw": source_title},
        "content": {"raw": (
            "<p>Rozdíl mezi klasickým pilates a power pilates</p>"
            + "<p>Popis různých lekcí a praktických rozdílů.</p>" * 100)},
        "excerpt": {"raw": "Stručné rozlišení lekcí"},
    }


def reader_factory(primary_title, *, secondary_link=True,
                   canonical=None, robot_header=""):
    def reader(slug):
        if slug == title.SLUG:
            return html_for(slug, primary_title, canonical=canonical), robot_header
        return html_for(slug, "Jiný související článek",
                        link=secondary_link), ""
    return reader


class PilatesGSCReadOnlyTests(unittest.TestCase):
    def test_title_already_live_does_not_ask_for_second_post(self):
        result = p.audit(post_get=lambda: post(title.NEW_TITLE),
                         public_get=reader_factory(title.NEW_TITLE))
        self.assertEqual(result["state"], "TITLE_ALREADY_LIVE_NO_WRITE")
        self.assertEqual(result["observed_source_title"], "NEW")
        self.assertEqual(result["related_pages_linking_to_primary"], 2)
        self.assertFalse(result["release_approved"])
        self.assertEqual(result["wp_post_attempts"], 0)
        self.assertEqual(result["seo_mutations"], 0)
        self.assertNotIn("Popis různých lekcí", json.dumps(result))

    def test_old_title_is_review_candidate_not_automatic_post(self):
        result = p.audit(post_get=lambda: post(title.OLD_TITLE),
                         public_get=reader_factory(title.OLD_TITLE))
        self.assertEqual(result["state"], "OLD_TITLE_CONFIRMED_REVIEW_ONEPOST")
        self.assertEqual(result["observed_source_title"], "OLD")
        self.assertFalse(result["release_approved"])

    def test_public_title_mismatch_canonical_or_noindex_hold(self):
        variants = (
            (title.OLD_TITLE, "https://evil.example/other/", ""),
            (title.NEW_TITLE, None, "noindex, follow"),
            (title.OLD_TITLE, None, ""),
        )
        for heading, canonical, robot_header in variants:
            with self.subTest(heading=heading, canonical=canonical):
                actual = title.NEW_TITLE if heading == title.OLD_TITLE else title.OLD_TITLE
                report = p.audit(
                    post_get=lambda: post(actual),
                    public_get=reader_factory(
                        heading, canonical=canonical,
                        robot_header=robot_header,
                    ),
                )
                self.assertEqual(report["state"], "HOLD_SOURCE_PUBLIC_MISMATCH")

    def test_noindex_meta_and_duplicate_canonical_and_script_decoys(self):
        html = html_for(title.SLUG, title.NEW_TITLE, noindex=True)
        parsed = p.parse_public(title.SLUG, html)
        self.assertEqual(parsed["robots"], "NOINDEX_OBSERVED")
        html = (html_for(title.SLUG, title.NEW_TITLE).replace(
            "</head>", '<link rel="canonical" href="' + title.URL +
            '"></head>'))
        self.assertEqual(p.parse_public(title.SLUG, html)["canonical"],
                         "MULTIPLE_CANONICALS")
        decoy = ('<html><head><title>Valid</title></head><body>'
                 '<script><h1>Fake</h1></script><h1>Actual</h1>'
                 '<template><a href="' + title.URL + '">Fake</a></template>'
                 '</body></html>')
        parsed = p.parse_public(p.RELATED[0], decoy)
        self.assertEqual(parsed["h1"], ["Actual"])
        self.assertFalse(parsed["links_to_primary"])

    def test_only_exact_owned_https_canonical_is_allowed(self):
        for value in (
            "http://xfit.cz/" + title.SLUG + "/",
            "https://xfit.cz:443/" + title.SLUG + "/",
            "https://evil.example/" + title.SLUG + "/",
            "https://xfit.cz@evil.example/" + title.SLUG + "/",
            title.URL + "?token=SECRET",
            title.URL + "#anchor",
            "https://xfit.cz/xfit-os-protein-guide/",
        ):
            with self.subTest(value=value):
                self.assertFalse(p.canonical_path(value, title.SLUG))
        self.assertTrue(p.canonical_path(title.URL, title.SLUG))

    def test_unrelated_slug_rejected_without_fetch(self):
        with self.assertRaises(ValueError):
            p.parse_public("xfit-os-protein-guide", "<html></html>")
        with self.assertRaises(ValueError):
            p.read_public("xfit-os-protein-guide")

    def test_incomplete_report_has_no_secrets_or_content(self):
        out = StringIO()
        with patch.object(p, "get_post", side_effect=PublishError("private token")), \
             patch.object(p, "audit", side_effect=PublishError("private token")), \
             contextlib.redirect_stdout(out), \
             self.assertRaises(SystemExit):
            p.main()
        result = json.loads(out.getvalue())
        self.assertEqual(result["state"], "READ_ONLY_PILATES_PREFLIGHT_INCOMPLETE")
        self.assertEqual(result["wp_post_attempts"], 0)
        self.assertNotIn("private token", out.getvalue())


if __name__ == "__main__":
    unittest.main()
