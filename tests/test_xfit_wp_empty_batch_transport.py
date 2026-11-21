"""Exactly one empty batch POST and before/after source identity safeguards."""
import contextlib
from io import BytesIO, StringIO
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import os

from scripts import xfit_wp_empty_batch_transport as b
from scripts.wp_publish import PublishError


class Response:
    def __init__(self, *, status=207, url="https://xfit.cz/wp-json/batch/v1",
                 body=b'{"responses":[]}'):
        self.status = status
        self.url = url
        self.source = BytesIO(body)

    def geturl(self):
        return self.url

    def read(self, limit):
        return self.source.read(limit)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class EmptyBatchTransportTests(unittest.TestCase):
    def test_single_exact_noop_post_no_mutating_child_request(self):
        def transport(req, timeout):
            self.assertEqual(req.get_method(), "POST")
            self.assertEqual(req.full_url, "https://xfit.cz/wp-json/batch/v1")
            self.assertEqual(req.data, b'{"requests":[]}')
            self.assertEqual(json.loads(req.data), {"requests": []})
            self.assertEqual(timeout, 25)
            self.assertIn("Authorization", req.headers)
            return Response()
        with patch.dict(os.environ, {"WP_USERNAME": "u", "WP_APP_PASSWORD": "secret"}), \
             patch.object(b, "urlopen", side_effect=transport) as call:
            result = b.empty_batch_transport("https://xfit.cz")
        self.assertEqual(call.call_count, 1)
        self.assertEqual(result["http_status"], 207)
        self.assertTrue(result["empty_batch_response"])
        self.assertEqual(result["wordpress_child_requests"], 0)
        self.assertEqual(result["wordpress_content_mutations_requested"], 0)
        self.assertEqual(result["http_post_attempts"], 1)
        self.assertFalse(result["post_retry"])
        self.assertNotIn("secret", json.dumps(result))

    def test_waf_http_403_no_retry(self):
        with patch.dict(os.environ, {"WP_USERNAME": "u", "WP_APP_PASSWORD": "p"}), \
             patch.object(b, "urlopen", side_effect=HTTPError(
                 "https://xfit.cz/wp-json/batch/v1", 403, "Private WAF rule", {}, None)) as call:
            result = b.empty_batch_transport("https://xfit.cz")
        self.assertEqual(call.call_count, 1)
        self.assertEqual(result["problem_category"], "HTTP_403")
        self.assertFalse(result["empty_batch_response"])
        self.assertNotIn("Private WAF", json.dumps(result))

    def test_network_timeout_no_retry_or_secret(self):
        with patch.dict(os.environ, {"WP_USERNAME": "u", "WP_APP_PASSWORD": "p"}), \
             patch.object(b, "urlopen", side_effect=TimeoutError("private secret")) as call:
            result = b.empty_batch_transport("https://xfit.cz")
        self.assertEqual(call.call_count, 1)
        self.assertEqual(result["problem_category"], "TRANSPORT_TIMEOUT")
        self.assertNotIn("private secret", json.dumps(result))

    def test_rejects_redirect_nonempty_batch_and_oversized_response(self):
        with patch.dict(os.environ, {"WP_USERNAME": "u", "WP_APP_PASSWORD": "p"}):
            for response in (
                    Response(url="https://evil.example/wp-json/batch/v1"),
                    Response(body=b'{"responses":[{"status":200}]}'),
                    Response(body=b'0' * (b.MAX_RESPONSE_BYTES + 1))):
                with self.subTest(response=response), patch.object(
                        b, "urlopen", return_value=response):
                    result = b.empty_batch_transport("https://xfit.cz")
                    self.assertNotEqual(result["problem_category"], "NONE")

    def test_route_identity_rejects_query_credentials_and_wrong_path(self):
        urls = (
            "http://xfit.cz/wp-json/batch/v1",
            "https://evil.example/wp-json/batch/v1",
            "https://xfit.cz@evil.example/wp-json/batch/v1",
            "https://xfit.cz:443/wp-json/batch/v1",
            "https://xfit.cz/wp-json/batch/v1?bad=1",
            "https://xfit.cz/wp-json/wp/v2/posts/9371",
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertFalse(b.exact_response_path(url, b.BATCH_PATH))

    def test_source_digest_pin_and_public_identity_must_agree(self):
        slug = "a-test-post"
        raw, rendered = "<p>raw unmodified content</p>", "<p>rendered</p>"
        exp = {"slug": slug, "raw_sha256": b.sha(raw),
               "modified_gmt": "2023-10-21T07:44:55"}
        src = {"id": 9371, "slug": slug, "link": "https://xfit.cz/" + slug + "/",
               "status": "publish", "modified_gmt": exp["modified_gmt"],
               "content": {"raw": raw}}
        public = dict(src, content={"rendered": rendered})
        with patch.dict(b.EXPECTED, {9371: exp}, clear=True), \
             patch.object(b.read_only, "wp_authenticated", return_value=src), \
             patch.object(b.read_only, "public_get", return_value=json.dumps(public)):
            result = b.fingerprint(9371)
        self.assertEqual(result["raw_sha256"], b.sha(raw))
        self.assertEqual(result["public_rendered_sha256"], b.sha(rendered))
        self.assertEqual(result["post_id"], 9371)

    def test_changed_raw_source_refuses_batch_before_any_post(self):
        out = StringIO()
        with patch.object(b, "normalized_base", return_value="https://xfit.cz"), \
             patch.object(b, "all_fingerprints", side_effect=PublishError("drift")), \
             patch.object(b, "empty_batch_transport") as write, \
             contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                b.run()
        self.assertEqual(ctx.exception.code, 2)
        write.assert_not_called()
        self.assertIn("SOURCE_DRIFT_NO_POST", out.getvalue())
        self.assertIn('"http_post_attempts": 0', out.getvalue())

    def test_run_one_batch_and_readback_stable_never_permits_article_release(self):
        before = [{"post_id": 9371, "raw_sha256": "stable"}]
        out = StringIO()
        with patch.object(b, "normalized_base", return_value="https://xfit.cz"), \
             patch.object(b, "all_fingerprints", side_effect=[before, before]) as reads, \
             patch.object(b, "empty_batch_transport", return_value={
                 "http_status": 207, "empty_batch_response": True,
                 "problem_category": "NONE", "http_post_attempts": 1,
                 "wordpress_content_mutations_requested": 0,
                 "wordpress_child_requests": 0, "post_retry": False}) as call, \
             contextlib.redirect_stdout(out):
            b.run()
        self.assertEqual(reads.call_count, 2)
        self.assertEqual(call.call_count, 1)
        doc = json.loads(out.getvalue())
        self.assertEqual(doc["state"], "EMPTY_BATCH_TRANSPORT_CONFIRMED_NO_ARTICLE_CHANGE")
        self.assertIs(doc["sources_unchanged"], True)
        self.assertIs(doc["release_allowed"], False)

    def test_ambiguous_batch_result_still_reads_but_never_retries(self):
        out = StringIO()
        before = [{"post_id": 9462, "raw_sha256": "before"}]
        with patch.object(b, "normalized_base", return_value="https://xfit.cz"), \
             patch.object(b, "all_fingerprints", side_effect=[before, before]) as reads, \
             patch.object(b, "empty_batch_transport", return_value={
                 "http_status": None, "empty_batch_response": False,
                 "problem_category": "TRANSPORT_TIMEOUT", "http_post_attempts": 1,
                 "wordpress_content_mutations_requested": 0,
                 "wordpress_child_requests": 0, "post_retry": False}) as call, \
             contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit):
                b.run()
        self.assertEqual(call.call_count, 1)
        self.assertEqual(reads.call_count, 2)
        self.assertIn("EMPTY_BATCH_TRANSPORT_UNVERIFIED", out.getvalue())

    def test_readback_drift_marks_failure_despite_207_response(self):
        out = StringIO()
        with patch.object(b, "normalized_base", return_value="https://xfit.cz"), \
             patch.object(b, "all_fingerprints", side_effect=[
                 [{"post_id": 9371, "raw_sha256": "a"}],
                 [{"post_id": 9371, "raw_sha256": "b"}]]), \
             patch.object(b, "empty_batch_transport", return_value={
                 "http_status": 207, "empty_batch_response": True,
                 "problem_category": "NONE", "http_post_attempts": 1}) as call, \
             contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit):
                b.run()
        self.assertEqual(call.call_count, 1)
        self.assertIn('"sources_unchanged": false', out.getvalue())


if __name__ == "__main__":
    unittest.main()
