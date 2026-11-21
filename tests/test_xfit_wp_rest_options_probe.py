"""No-write transport probe regression tests, including WAF/timeout responses."""
import contextlib
from io import BytesIO, StringIO
import json
import os
import unittest
from unittest.mock import patch

from urllib.error import HTTPError
from scripts import xfit_wp_rest_options_probe as p
from scripts.wp_publish import PublishError


class Response:
    def __init__(self, url, *, status=200, body=b"{}", headers=None):
        self.url = url
        self.status = status
        self.body = BytesIO(body)
        self.headers = headers or {}

    def geturl(self):
        return self.url

    def read(self, count):
        return self.body.read(count)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class OptionsProbeTests(unittest.TestCase):
    def setUp(self):
        self.base = "https://xfit.cz"
        self.url = self.base + "/wp-json/wp/v2/posts/9371"

    def test_only_reviewed_post_ids_and_exact_target(self):
        for post_id in (-1, 1, 9999, "9371", True, 9371.0):
            with self.subTest(post_id=post_id), self.assertRaises(PublishError):
                p.endpoint(self.base, post_id)
        self.assertEqual(p.endpoint(self.base, 9462)[1], "/wp-json/wp/v2/posts/9462")
        for url in (self.url + "?bad=1", "http://xfit.cz/wp-json/wp/v2/posts/9371",
                    "https://evil.example/wp-json/wp/v2/posts/9371",
                    "https://xfit.cz@evil.example/wp-json/wp/v2/posts/9371",
                    "https://xfit.cz:443/wp-json/wp/v2/posts/9371",
                    "https://xfit.cz/wp-json/wp/v2/posts/9462"):
            with self.subTest(url=url):
                self.assertFalse(p.known_rest_target(url, "/wp-json/wp/v2/posts/9371"))

    def test_authenticated_options_sends_no_body_or_mutating_method(self):
        def transport(req, timeout):
            self.assertEqual(req.get_method(), "OPTIONS")
            self.assertIsNone(req.data)
            self.assertEqual(timeout, 25)
            self.assertIn("Authorization", req.headers)
            self.assertIn("Content-type", req.headers)
            return Response(self.url, headers={"Allow": "GET, POST, PUT, PATCH"})
        with patch.dict(os.environ, {"WP_USERNAME": "user", "WP_APP_PASSWORD": "secret"}), \
             patch.object(p, "urlopen", side_effect=transport) as urlopen:
            result = p.probe(9371, base=self.base)
        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(result["state"], "READ_ONLY_OPTIONS_OBSERVED")
        self.assertTrue(result["advertises_post"])
        self.assertTrue(result["advertises_get"])
        self.assertEqual(result["wordpress_writes"], 0)
        self.assertFalse(result["post_success_proven"])
        self.assertNotIn("secret", json.dumps(result))

    def test_wordpress_endpoint_schema_methods(self):
        schema = {"endpoints": [{"methods": ["GET"]}, {"methods": ["POST", "PUT"]}]}
        with patch.dict(os.environ, {"WP_USERNAME": "u", "WP_APP_PASSWORD": "p"}), \
             patch.object(p, "urlopen", return_value=Response(
                 self.url, body=json.dumps(schema).encode())):
            result = p.probe(9371, base=self.base)
        self.assertTrue(result["advertises_post"])
        self.assertTrue(result["advertises_get"])

    def test_http_403_block_is_not_reported_as_post_success(self):
        with patch.dict(os.environ, {"WP_USERNAME": "u", "WP_APP_PASSWORD": "p"}), \
             patch.object(p, "urlopen", side_effect=HTTPError(self.url, 403, "Forbidden", {}, None)):
            result = p.probe(9371, base=self.base)
        self.assertEqual(result["http_status"], 403)
        self.assertEqual(result["problem_category"], "HTTP_403")
        self.assertEqual(result["state"], "READ_ONLY_OPTIONS_BLOCKED")
        self.assertEqual(result["wordpress_writes"], 0)

    def test_timeout_no_post_retry(self):
        with patch.dict(os.environ, {"WP_USERNAME": "u", "WP_APP_PASSWORD": "p"}), \
             patch.object(p, "urlopen", side_effect=TimeoutError("private token")) as call:
            result = p.probe(9371, base=self.base)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(result["problem_category"], "TRANSPORT_TIMEOUT")
        self.assertNotIn("private token", json.dumps(result))
        self.assertEqual(result["method_used"], "OPTIONS")

    def test_redirect_and_large_response_fail_closed(self):
        with patch.dict(os.environ, {"WP_USERNAME": "u", "WP_APP_PASSWORD": "p"}):
            with patch.object(p, "urlopen", return_value=Response("https://evil.example/")):
                self.assertEqual(p.probe(9371, base=self.base)["state"], "READ_ONLY_OPTIONS_BLOCKED")
            with patch.object(p, "urlopen", return_value=Response(
                    self.url, body=b"x" * (p.MAX_RESPONSE_BYTES + 1))):
                self.assertEqual(p.probe(9371, base=self.base)["problem_category"],
                                 "UNEXPECTED_RESPONSE")

    def test_missing_credentials_fails_before_network(self):
        with patch.dict(os.environ, {"WP_USERNAME": "", "WP_APP_PASSWORD": ""}), \
             patch.object(p, "urlopen") as network:
            result = p.probe(9371, base=self.base)
        self.assertEqual(result["state"], "READ_ONLY_OPTIONS_BLOCKED")
        network.assert_not_called()

    def test_run_records_both_ids_without_authorizing_publish(self):
        calls = []
        def get(pid, *, base):
            calls.append(pid)
            return {"state": "READ_ONLY_OPTIONS_OBSERVED", "advertises_post": True,
                    "wordpress_writes": 0, "post_success_proven": False}
        out = StringIO()
        with patch.object(p, "normalized_base", return_value=self.base), \
             patch.object(p, "probe", side_effect=get), \
             contextlib.redirect_stdout(out):
            p.run()
        result = json.loads(out.getvalue())
        self.assertEqual(calls, [9371, 9462])
        self.assertEqual(result["post_attempts"], 0)
        self.assertIs(result["permits_post_release"], False)

    def test_blocked_options_fails_job_after_recording_evidence(self):
        output = StringIO()
        with patch.object(p, "normalized_base", return_value=self.base), \
             patch.object(p, "probe", return_value={"state": "READ_ONLY_OPTIONS_BLOCKED",
                                                   "advertises_post": False, "wordpress_writes": 0}), \
             contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as ctx:
                p.run()
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("READ_ONLY_WP_ROUTE_PREFLIGHT", output.getvalue())


if __name__ == "__main__":
    unittest.main()
