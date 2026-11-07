"""Offline privacy and ownership tests for XFIT live analytics preflight."""
import unittest
from unittest.mock import patch

from scripts import xfit_analytics_cmp_preflight as probe


class ReadOnlyPreflightTests(unittest.TestCase):
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

    def test_plugin_inventory_requires_permission_and_redacts_names(self):
        plugins = [
            {"plugin": "complianz-gdpr/complianz-gpdr.php", "status": "active"},
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
        self.assertEqual(result["active_plugin_count"], 3)
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
        self.assertNotIn("secret", str(result))
        self.assertEqual(result["pages"][1]["read_status"], "PUBLIC_HTTP_VERIFIED")


if __name__ == "__main__":
    unittest.main()
