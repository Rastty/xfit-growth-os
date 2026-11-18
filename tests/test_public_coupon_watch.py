"""Offline, deterministic public proof tests: no WordPress calls or writes."""

import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError

from scripts.xfit_public_coupon_watch import (
    TARGETS, classify_html, exact_article_url, expected_url, probe, run,
)


def page(post_id, slug, body, *, canonical=True, body_id=True):
    link = ('<link rel="canonical" href="' + expected_url(slug) + '">') if canonical else ""
    cls = ' class="postid-' + str(post_id) + ' single-post"' if body_id else ""
    return '<!doctype html><html><head>' + link + '</head><body' + cls + '><main><article>' + body + '</article></main></body></html>'


class FakeResponse:
    status = 200
    headers = {"Content-Type": "text/html; charset=UTF-8"}

    def __init__(self, url, data, *, status=200, content_type=None, final_url=None):
        self.url = final_url or url
        self.data = data.encode("utf-8") if isinstance(data, str) else data
        self.status = status
        self.headers = {"Content-Type": content_type or "text/html; charset=UTF-8"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.data[:limit]

    def geturl(self):
        return self.url


class FakeOpener:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def open(self, request, timeout):
        url = request.full_url
        self.calls.append((url, timeout, request.get_header("Authorization")))
        value = self.payloads[url]
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, FakeResponse) else FakeResponse(url, value)


class PublicCouponWatchTests(unittest.TestCase):
    def setUp(self):
        self.pid, self.slug = TARGETS[0]

    def test_only_exact_known_xfit_permalink_accepted(self):
        good = expected_url(self.slug)
        self.assertTrue(exact_article_url(good, self.slug))
        self.assertTrue(exact_article_url(good.replace("xfit.cz", "www.xfit.cz"), self.slug))
        for url in (good + "?preview=true", good + "#coupon", good.replace("https:", "http:"),
                    good.replace("xfit.cz", "xfit.cz.evil.invalid"),
                    good.replace("/" + self.slug, "/wrong"),
                    good.replace("https://", "https://foo:bar@"),
                    good.replace("xfit.cz/", "xfit.cz:444/")):
            with self.subTest(url=url):
                self.assertFalse(exact_article_url(url, self.slug))

    def test_visible_expired_coupon_is_red_and_counts_multiple(self):
        markup = page(self.pid, self.slug,
                      '<p>Kód <strong>5NM2022</strong> a nabídka 5nm2022.</p>')
        self.assertEqual(classify_html(markup, self.pid, self.slug),
                         ("EXPIRED_COUPON_VISIBLE", 2))

    def test_hidden_script_meta_and_comments_do_not_create_false_alarm(self):
        markup = page(self.pid, self.slug,
                      '<script>const code="5NM2022";</script>'
                      '<style>.promo::after{content:"5NM2022"}</style>'
                      '<template>5NM2022</template><noscript>5NM2022</noscript>'
                      '<p aria-hidden="true">5NM2022</p>'
                      '<p hidden>5NM2022</p><p style="display:none">5NM2022</p>'
                      '<p style="visibility: hidden">5NM2022</p>'
                      '<!-- 5NM2022 --><p>Žádné platné promo.</p>')
        self.assertEqual(classify_html(markup, self.pid, self.slug),
                         ("PUBLIC_NO_COUPON_OBSERVED", 0))

    def test_page_identity_never_inferred_from_generic_200(self):
        for body in (
            "<body><p>Stránka nenalezena</p></body>",
            page(self.pid, self.slug, "Bez kupónu", canonical=False, body_id=False),
            page(self.pid + 1, self.slug, "Bez kupónu"),
            page(self.pid, self.slug, "Bez kupónu").replace(self.slug + '/', 'wrong/'),
            page(self.pid, self.slug, "Bez kupónu").replace('rel="canonical"', 'rel="canonical" href="https://evil.invalid"'),
        ):
            with self.subTest(html=body[:90]):
                self.assertEqual(classify_html(body, self.pid, self.slug)[0],
                                 "UNVERIFIED_IDENTITY")
        self.assertEqual(classify_html(page(self.pid, self.slug, "Bez kupónu", canonical=False),
                                       self.pid, self.slug)[0], "PUBLIC_NO_COUPON_OBSERVED")

    def test_http_redirect_error_invalid_utf8_and_non_html_are_unknown(self):
        url = expected_url(self.slug)
        valid = page(self.pid, self.slug, "Opraveno")
        for result, reason in (
            (URLError("unavailable"), "UNVERIFIED_FETCH"),
            (FakeResponse(url, valid, status=503), "UNVERIFIED_HTTP_RESPONSE"),
            (FakeResponse(url, valid, content_type="application/json"), "UNVERIFIED_HTTP_RESPONSE"),
            (FakeResponse(url, valid, final_url="https://other.invalid"), "UNVERIFIED_FINAL_URL"),
            (FakeResponse(url, b"\xff\xfe"), "UNVERIFIED_FETCH"),
            (FakeResponse(url, "x" * 3_000_001), "UNVERIFIED_RESPONSE_TOO_LARGE"),
        ):
            with self.subTest(reason=reason):
                self.assertEqual(probe(self.pid, self.slug, FakeOpener({url: result}))["state"], reason)

    def test_two_clean_public_pages_yield_observed_not_wp_verified(self):
        data = {expected_url(slug): page(pid, slug, "<p>Aktuální průvodce.</p>")
                for pid, slug in TARGETS}
        opener = FakeOpener(data)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            self.assertEqual(run(opener, report=path), 0)
            result = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(result["state"], "PUBLIC_ONLY_CLEAN_OBSERVED")
        self.assertEqual(result["counts"], {"still_visible": 0, "clean_observed": 2, "unverified": 0})
        self.assertEqual(result["wordpress_writes"], 0)
        self.assertFalse(result["authenticated_wp_verified"])
        self.assertTrue(all(auth is None for _, _, auth in opener.calls))

    def test_one_visible_and_one_unverified_must_not_pass(self):
        first, second = TARGETS
        data = {expected_url(first[1]): page(*first, "5NM2022"),
                expected_url(second[1]): URLError("blocked")}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            self.assertEqual(run(FakeOpener(data), report=path), 2)
            result = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(result["counts"], {"still_visible": 1, "clean_observed": 0, "unverified": 1})
        self.assertEqual(result["state"], "PUBLIC_COUPON_REQUIRES_ATTENTION")
        self.assertNotIn("blocked", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
