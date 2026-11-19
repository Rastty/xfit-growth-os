"""Offline privacy and ownership tests for XFIT live analytics preflight."""
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from scripts import xfit_analytics_cmp_preflight as probe


class ReadOnlyPreflightTests(unittest.TestCase):
    def test_public_read_retries_only_transient_failures(self):
        url = probe.public_url("xfit-os-kreatin-poradce")

        class Page:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def geturl(self):
                return url

            def read(self, maximum):
                return b"<html>verified</html>"[:maximum]

        temporary = HTTPError(url, 503, "temporary PRIVATE TOKEN", {}, None)
        with patch.object(probe.urllib.request, "urlopen",
                          side_effect=[temporary, Page()]) as fetch, \
                patch.object(probe.time, "sleep") as pause:
            self.assertEqual(probe.get_public_html(url), "<html>verified</html>")
            self.assertEqual(fetch.call_count, 2)
            pause.assert_called_once_with(1)

        denied = HTTPError(url, 403, "no permission PRIVATE TOKEN", {}, None)
        with patch.object(probe.urllib.request, "urlopen", side_effect=denied) as fetch, \
                patch.object(probe.time, "sleep") as pause:
            with self.assertRaises(HTTPError):
                probe.get_public_html(url)
            fetch.assert_called_once()
            pause.assert_not_called()

        class WrongDestination(Page):
            def geturl(self):
                return "https://xfit.cz/unrelated-page/"

        with patch.object(probe.urllib.request, "urlopen",
                          return_value=WrongDestination()) as fetch, \
                patch.object(probe.time, "sleep") as pause:
            with self.assertRaises(ValueError):
                probe.get_public_html(url)
            fetch.assert_called_once()
            pause.assert_not_called()

        with patch.object(probe.urllib.request, "urlopen",
                          side_effect=URLError("PRIVATE TOKEN")) as fetch, \
                patch.object(probe.time, "sleep") as pause:
            with self.assertRaises(URLError):
                probe.get_public_html(url)
            self.assertEqual(fetch.call_count, 3)
            self.assertEqual(pause.call_count, 2)

    def test_failure_categories_are_useful_but_never_expose_private_errors(self):
        url = probe.public_url("xfit-os-kreatin-poradce")
        for error, expected in (
            (HTTPError(url, 403, "private", {}, None), "HTTP_ACCESS_DENIED"),
            (HTTPError(url, 429, "private", {}, None), "HTTP_TRANSIENT_EXHAUSTED"),
            (HTTPError(url, 404, "private", {}, None), "HTTP_OTHER_FAILURE"),
            (URLError("private"), "NETWORK_UNAVAILABLE"),
            (ValueError("private"), "UNEXPECTED_RESPONSE"),
        ):
            with self.subTest(error=type(error).__name__):
                category = probe.public_failure_category(error)
                self.assertEqual(category, expected)
                self.assertNotIn("private", category)

    def test_sanitized_provider_detection_and_no_identity_leak(self):
        snippet = (
            '<script src="https://www.googletagmanager.com/gtag/js?id=G-PRIVATE"></script>'
            '<script src="/wp-content/plugins/complianz-gdpr/cookieblocker.js"></script>'
            '<script>function someTag(){return "gtag";}</script>'
            '<article class="xfit-product-card">'
            '<a href="https://www.namaximum.cz/product?'
            'a_aid=SECRET&a_bid=HIDDEN" data-xfit-product-id="392">Buy</a></article>'
        )
        report = probe.scan_public_html(snippet)
        self.assertEqual(report["cmp_html_fingerprints"], ["complianz"])
        self.assertEqual(report["analytics_html_fingerprints"], ["google_tag"])
        self.assertEqual(report["catalog_cta_metadata_count"], 1)
        self.assertFalse(report["first_party_analytics_script_reference"])
        for confidential in ("G-PRIVATE", "SECRET", "HIDDEN", "392", "namaximum"):
            self.assertNotIn(confidential, str(report))

    def test_no_html_detection_is_not_proof_of_no_cmp(self):
        report = probe.scan_public_html("<html><p>Anonymous page</p></html>")
        self.assertEqual(report["cmp_html_fingerprints"], [])
        self.assertEqual(report["analytics_html_fingerprints"], [])
        self.assertFalse(report["consent_decision_observed"])
        self.assertFalse(report["analytics_event_observed"])

    def test_public_scanner_does_not_mistake_repo_file_for_live_deploy(self):
        source = '<script src="/assets/analytics/xfit-outbound.js"></script>'
        report = probe.scan_public_html(source)
        self.assertTrue(report["first_party_analytics_script_reference"])
        self.assertFalse(report["consent_bridge_symbol_in_html"])
        self.assertFalse(report["analytics_event_observed"])

    def test_script_load_order_is_explicitly_checked_not_inferred(self):
        correct = (
            '<script src="/wp-content/plugins/xfit-analytics/assets/'
            'xfit-webtoffee-bridge.js"></script>'
            '<script src="/wp-content/plugins/xfit-analytics/assets/'
            'xfit-outbound.js"></script>'
        )
        report = probe.scan_public_html(correct)
        self.assertTrue(report["first_party_consent_bridge_script_reference"])
        self.assertTrue(report["first_party_analytics_script_reference"])
        self.assertTrue(report["bridge_precedes_outbound_script"])
        reverse = probe.scan_public_html(
            correct.replace("xfit-webtoffee-bridge.js", "placeholder.js", 1)
            .replace("xfit-outbound.js", "xfit-webtoffee-bridge.js", 1)
            .replace("placeholder.js", "xfit-outbound.js", 1)
        )
        self.assertFalse(reverse["bridge_precedes_outbound_script"])

    def test_plugin_inventory_requires_permission_and_redacts_names(self):
        plugins = [
            {"plugin": "complianz-gdpr/complianz-gpdr.php", "status": "active"},
            {"plugin": "cookie-law-info/cookie-law-info.php", "status": "active", "version": "3.4.9"},
            {"plugin": "google-site-kit/google-site-kit.php", "status": "active"},
            {"plugin": "sensitive-fake-plugin/example.php", "status": "inactive"},
            {"plugin": "private-vendor-secret-plugin/example.php", "status": "active"},
        ]
        with patch.object(probe, "normalized_base",
                                        return_value="https://xfit.cz"):
            result = probe.inspect_plugins(
                wp_fetch=lambda base, path: plugins
            )
        self.assertEqual(result["inventory_status"], "READ_ONLY_VISIBLE")
        self.assertIn("complianz", result["recognized_active_providers"])
        self.assertIn("google_site_kit", result["recognized_active_providers"])
        self.assertEqual(result["active_plugin_count"], 4)
        self.assertEqual(result["webtoffee_major_version"], 3)
        self.assertNotIn("3.4.9", str(result))
        self.assertNotIn("private-vendor", str(result))

    def test_plugin_inventory_denied_does_not_report_no_plugins(self):
        with patch.object(probe, "normalized_base",
                                        return_value="https://xfit.cz"):
            result = probe.inspect_plugins(
                wp_fetch=lambda base, path: (_ for _ in ()).throw(
                    probe.PublishError("HTTP 403 private password TOKEN")
                )
            )
        self.assertEqual(result["inventory_status"],
                         "UNKNOWN_NO_AUTHORIZED_INVENTORY")
        self.assertIsNone(result["active_plugin_count"])
        self.assertIsNone(result["webtoffee_major_version"])
        self.assertNotIn("TOKEN", str(result))

    def test_report_never_exposes_raw_html_or_claims_measured_clicks(self):
        html = (
            '<script src="https://www.googletagmanager.com/gtm.js?id=SECRET"></script>'
            '<a data-xfit-product-id="392">Sample</a>'
        )
        result = probe.run(
            public_reader=lambda url: html,
            plugin_reader=lambda: {"inventory_status":"UNKNOWN_NO_AUTHORIZED_INVENTORY",
                                   "active_plugin_count":None,
                                   "recognized_active_providers":[]},
        )
        self.assertEqual(len(result["pages"]), 2)
        self.assertEqual(result["wordpress_writes"], 0)
        self.assertEqual(result["browser_events_sent"], 0)
        self.assertEqual(result["affiliate_commission"], "UNKNOWN")
        self.assertNotIn("SECRET", str(result))
        self.assertNotIn("392", str(result))

    def test_network_failure_on_one_page_keeps_unknown_state(self):
        def reader(url):
            if "kreatin" in url:
                raise OSError("network secret token")
            return '<html></html>'
        result = probe.run(
            public_reader=reader,
            plugin_reader=lambda: {"inventory_status":"UNKNOWN_NO_AUTHORIZED_INVENTORY",
                                   "active_plugin_count":None,
                                   "recognized_active_providers":[]},
        )
        self.assertEqual(result["pages"][0]["read_status"], "PUBLIC_READ_UNAVAILABLE")
        self.assertEqual(result["pages"][0]["read_failure_category"], "NETWORK_UNAVAILABLE")
        self.assertNotIn("secret", str(result))
        self.assertEqual(result["pages"][1]["read_status"], "PUBLIC_HTTP_VERIFIED")


if __name__ == "__main__":
    unittest.main()
