"""The host gate never trusts redirects, source mismatches or external hosts."""

import unittest
from urllib.error import URLError

from scripts import xfit_protein_price_host_preflight as host


BASE = "https://xfit.cz/wp-content/uploads/xfit-static/protein-price/v1/"


def local_asset(url):
    name = url.rsplit("/", 1)[-1]
    source = host.ROOT / "assets/tools/protein-price" / name
    mime = "text/css" if name.endswith(".css") else "application/javascript"
    return source.read_bytes(), mime, url


class HostPreflightTests(unittest.TestCase):
    def test_two_exact_first_party_assets_can_be_verified_readonly(self):
        report = host.verify_host(BASE, getter=local_asset)
        self.assertEqual(report["status"], "FIRST_PARTY_ASSETS_BYTE_VERIFIED")
        self.assertFalse(report["wordpress_changed"])
        self.assertFalse(report["ready_to_edit_wordpress"])
        self.assertEqual([a["name"] for a in report["assets"]], ["calculator.js", "calculator.css"])
        self.assertTrue(all(len(a["sha256"]) == 64 for a in report["assets"]))

    def test_reject_external_redirect_and_ambiguous_paths(self):
        for url in (
            "http://xfit.cz/static/", "https://other.cz/static/",
            "https://xfit.cz.evil.com/static/", "https://xfit.cz@evil.cz/static/",
            "https://xfit.cz/static/?campaign=test", "https://xfit.cz/static/#script",
            "https://xfit.cz:443/static/", "https://xfit.cz/static/%2e%2e/",
            "https://xfit.cz/static/../assets/", "https://xfit.cz//static/",
            "https://xfit.cz/static"
        ):
            with self.subTest(url=url), self.assertRaises(host.HostingGateError):
                host.asset_urls(url)

    def test_changed_bytes_wrong_mime_or_redirect_do_not_pass(self):
        for getter in (
            lambda url: (b"unexpected", "application/javascript", url),
            lambda url: (*local_asset(url)[:1], "text/html", url),
            lambda url: (*local_asset(url)[:2], "https://other.cz/a.js"),
        ):
            with self.assertRaises(host.HostingGateError):
                host.verify_host(BASE, getter=getter)

    def test_unavailable_asset_fails_closed(self):
        def unavailable(_url):
            raise URLError("offline")
        with self.assertRaises(host.HostingGateError):
            host.verify_host(BASE, getter=unavailable)


if __name__ == "__main__":
    unittest.main()
