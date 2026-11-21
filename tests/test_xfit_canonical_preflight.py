"""Offline regression tests: source fingerprinting cannot mutate WordPress."""
import contextlib
from io import StringIO
import json
import os
import unittest
from unittest.mock import patch

from scripts import xfit_canonical_preflight as p


POST_ID = 9371
URL = "https://xfit.cz/bcaa-pruvodce/"
RAW = ('<!DOCTYPE html><html><body><link rel="canonical" '
       'href="https://www.example.com/irrelevant"> 5NM2022 '
       'Private body marker do not log </body></html>')


def post(content=RAW, *, rendered=False, post_id=POST_ID, link=URL, slug="bcaa-pruvodce"):
    return {
        "id": post_id, "slug": slug, "status": "publish", "link": link,
        "modified_gmt": "2023-10-21T07:44:55",
        "content": {"rendered" if rendered else "raw": content},
    }


PAGE = ('<html><head><link rel="canonical" href="' + URL
        + '"></head><body><main>Visible article</main>'
        + RAW + (' more text' * 30) + "</body></html>")


class ReadOnlyPreflightTests(unittest.TestCase):
    def test_expected_article_fingerprints_and_no_raw_content(self):
        record = p.summarize(post(), post(), post(rendered=True), PAGE, POST_ID)
        self.assertEqual(record["state"], "READ_ONLY_SOURCE_STABLE")
        self.assertEqual(record["raw_body_canonical_count"], 1)
        self.assertEqual(record["public_page_canonical_count"], 2)
        self.assertEqual(record["nested_doctype_count"], 1)
        self.assertEqual(record["raw_coupon_5nm2022_count"], 1)
        self.assertEqual(record["remote_post_attempts"], 0)
        self.assertEqual(len(record["auth_raw_sha256"]), 64)
        self.assertNotIn("Private body marker", json.dumps(record))

    def test_public_source_divergence_fails_closed(self):
        changed = post(link="https://xfit.cz/changed/")
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            p.summarize(post(), post(), post(rendered=True, link=changed["link"]),
                        PAGE, POST_ID)

    def test_auth_concurrent_change_fails_closed(self):
        changed = post(content=RAW.replace("5NM2022", "changed"))
        with self.assertRaisesRegex(ValueError, "changed between reads"):
            p.summarize(post(), changed, post(rendered=True), PAGE, POST_ID)

    def test_wrong_id_and_draft_fail_closed(self):
        with self.assertRaises(ValueError):
            p.summarize(post(), post(), post(rendered=True, post_id=9372), PAGE, POST_ID)
        draft = post()
        draft["status"] = "draft"
        with self.assertRaises(ValueError):
            p.summarize(draft, post(), post(rendered=True), PAGE, POST_ID)

    def test_rejects_non_site_or_ambiguous_permalink(self):
        for url in ("http://xfit.cz/a/", "https://evil.example.com/a/",
                    "https://xfit.cz@evil.example.com/a/",
                    "https://xfit.cz:443/a/", "https://xfit.cz/a/?p=1",
                    "https://xfit.cz/a/#frag", "https://xfit.cz/"):
            with self.subTest(url=url):
                self.assertFalse(p.exact_site_url(url))

    def test_htmlparser_handles_unquoted_attribute_and_self_closing(self):
        html = ('<link rel=canonical href="/a/">'
                '<link rel="alternate canonical" href="/b/" />'
                '<a href="https://xfit.cz/">anchor</a>')
        self.assertEqual(p.canonical_links(html), ["/a/", "/b/"])

    def test_disallowed_post_id_prevents_all_remote_requests(self):
        with patch.dict(os.environ, {"XFIT_PREFLIGHT_POST_ID": "1"}), \
                patch.object(p, "wp_authenticated") as wp, \
                patch.object(p, "public_get") as public:
            with self.assertRaisesRegex(ValueError, "not in source-reviewed"):
                p.run()
            wp.assert_not_called()
            public.assert_not_called()

    def test_network_auth_function_is_get_without_payload(self):
        with patch.object(p, "wp_request", return_value={}) as request, \
                patch.object(p, "normalized_base", return_value="https://xfit.cz"):
            p.wp_authenticated(9371, cache_bust=True)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(len(request.call_args.args), 2)
        self.assertIn("context=edit", request.call_args.args[1])
        self.assertIn("xfit_preflight=", request.call_args.args[1])
        self.assertEqual(request.call_args.kwargs, {})

    def test_run_emits_only_public_metadata_and_no_private_body(self):
        with patch.dict(os.environ, {"XFIT_PREFLIGHT_POST_ID": "9371"}), \
                patch.object(p, "wp_authenticated", side_effect=[post(), post()]) as auth, \
                patch.object(p, "public_get",
                             side_effect=[json.dumps(post(rendered=True)), PAGE]) as public:
            output = StringIO()
            with contextlib.redirect_stdout(output):
                p.run()
        record = json.loads(output.getvalue())
        self.assertTrue(record["same_authenticated_source"])
        self.assertEqual(record["remote_post_attempts"], 0)
        self.assertEqual(auth.call_count, 2)
        self.assertEqual(public.call_count, 2)
        self.assertNotIn("Private body marker", output.getvalue())


if __name__ == "__main__":
    unittest.main()
