"""Static GA4 vs Google Ads vs GTM; no fake attribution or network calls."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import xfit_ga4_native_outbound_readonly as m

G4 = "G-TESTABCDE"
AW = "AW-12345678"
GTM = "GTM-ABCDEF"


def page(*, script_src="", script_inline="", cta_count=8):
    tags = ('<script src="' + script_src + '"></script>') if script_src else ""
    tags += '<script>' + script_inline + '</script>'
    anchors = "".join(
        '<a href="https://www.namaximum.cz/p/real-item?variant=' + str(i) + '" ' +
        'rel="sponsored nofollow" data-xfit-partner="namaximum" ' +
        'data-xfit-engine="creatine" data-xfit-product-id="' + str(i) + '">' +
        'Ověřit cenu</a>'
        for i in range(100, 100 + cta_count)
    )
    return "<html><head>"+tags+"</head><body>" + (
        "<p>Important decision content with real article body.</p>" * 12) + anchors + "</body></html>"


class NativeOutboundAuditTests(unittest.TestCase):
    def test_native_ga4_load_and_inline_config_only_capability_not_events(self):
        result = m.classify(page(
            script_src="https://www.googletagmanager.com/gtag/js?id=" + G4,
            script_inline="gtag('js', new Date()); gtag('config', '" + G4 + "');"
        ), m.SLUGS[0])
        self.assertTrue(result["ga4_loader_static"])
        self.assertTrue(result["ga4_config_inline_static"])
        self.assertEqual(result["existing_tag_readiness"],
                         "STATIC_GA4_LOAD_AND_CONFIG_FOUND_EVENTS_UNPROVEN")
        self.assertEqual(result["merchant_external_anchor_count"], 8)
        self.assertEqual(result["catalog_identified_external_anchor_count"], 8)
        self.assertEqual(result["external_sponsored_rel_count"], 8)
        self.assertFalse(result["events_observed"])
        self.assertFalse(result["enhanced_measurement_enabled_proven"])
        self.assertFalse(result["cmp_consent_effectively_enforced_proven"])
        self.assertNotIn(G4, json.dumps(result))
        self.assertNotIn("namaximum.cz/p", json.dumps(result))

    def test_google_ads_tag_is_not_ga4(self):
        result = m.classify(page(
            script_src="https://www.googletagmanager.com/gtag/js?id=" + AW,
            script_inline='gtag("config", "' + AW + '");'
        ), m.SLUGS[0])
        self.assertEqual(result["existing_tag_readiness"],
                         "GOOGLE_ADS_TAG_ONLY_GA4_UNKNOWN")
        self.assertFalse(result["ga4_loader_static"])
        self.assertFalse(result["ga4_config_inline_static"])

    def test_gtm_presence_not_ga4_runtime_proof(self):
        result = m.classify(page(
            script_src="https://www.googletagmanager.com/gtm.js?id=" + GTM,
        ), m.SLUGS[0])
        self.assertEqual(result["existing_tag_readiness"],
                         "GTM_PRESENT_GA4_RUNTIME_UNKNOWN")
        self.assertFalse(result["enhanced_measurement_enabled_proven"])

    def test_ordinary_external_anchors_without_consent_do_not_prove_measurement(self):
        result = m.classify(page(), m.SLUGS[0])
        self.assertEqual(result["existing_tag_readiness"],
                         "NO_STATIC_GA4_EVIDENCE_RUNTIME_UNKNOWN")
        self.assertEqual(result["merchant_external_anchor_count"], 8)
        self.assertFalse(result["events_observed"])

    def test_consent_default_presence_does_not_mean_consent_proven(self):
        result = m.classify(page(
            script_src="https://www.googletagmanager.com/gtag/js?id=" + G4,
            script_inline=("gtag('consent', 'default', {analytics_storage:'denied'});"
                           "gtag('config','" + G4 + "');")
        ), m.SLUGS[0])
        self.assertTrue(result["consent_default_call_static"])
        self.assertFalse(result["cmp_consent_effectively_enforced_proven"])

    def test_untrusted_domains_and_invalid_metadata_not_counted_as_catalog(self):
        body = page(cta_count=0) + (
            '<a href="http://www.namaximum.cz/foo">x</a>'
            '<a href="https://attacker.test/p/1" data-xfit-product-id="123">x</a>'
            '<a href="https://www.namaximum.cz/p/1" '
            'data-xfit-product-id="NaN" data-xfit-engine="creatine" '
            'data-xfit-partner="namaximum">x</a>'
        )
        result = m.classify(body, m.SLUGS[0])
        self.assertEqual(result["merchant_external_anchor_count"], 1)
        self.assertEqual(result["catalog_identified_external_anchor_count"], 0)

    def test_report_redacts_ids_urls_and_does_not_send_events(self):
        calls = []
        def reader(url):
            calls.append(url)
            return page(script_src="https://www.googletagmanager.com/gtag/js?id=" + G4,
                        script_inline="gtag('config', '" + G4 + "');")
        report = m.run(public_reader=reader, plugins_reader=lambda: {
            "xfit_analytics_plugin_state": "NOT_INSTALLED",
            "inventory_status": "READ_ONLY_VISIBLE",
            "recognized_active_providers": ["webtoffee"],
        })
        self.assertEqual(calls, [m.public_url(x) for x in m.SLUGS])
        self.assertEqual(report["wordpress_writes"], 0)
        self.assertEqual(report["browser_analytics_events_sent"], 0)
        self.assertEqual(report["affiliate_clicks_sent"], 0)
        self.assertEqual(report["ga4_actual_clicks"], "UNKNOWN")
        self.assertEqual(report["xfit_plugin_inventory_state"], "NOT_INSTALLED")
        self.assertEqual(report["known_active_cmp_provider_count"], 1)
        serial = json.dumps(report)
        self.assertNotIn(G4, serial)
        self.assertNotIn("a_aid", serial)

    def test_public_failure_never_becomes_zero_events_or_valid_configuration(self):
        report = m.run(
            public_reader=lambda _url: (_ for _ in ()).throw(OSError("blocked 403")),
            plugins_reader=lambda: {"inventory_status": "UNKNOWN"},
        )
        self.assertEqual(report["pages"][0]["read_status"], "PUBLIC_HTML_UNKNOWN")
        self.assertEqual(report["pages"][0]["existing_tag_readiness"], "UNKNOWN")
        self.assertNotIn("blocked 403", json.dumps(report))

    def test_reject_untrusted_slug_and_oversized_html(self):
        with self.assertRaises(ValueError):
            m.classify(page(), "private-slug")
        with self.assertRaises(ValueError):
            m.classify("x" * (m.MAX_BYTES + 1), m.SLUGS[0])

    def test_one_time_workflow_never_mutates_wordpress(self):
        src = Path(".github/workflows/xfit-ga4-native-outbound-getonly.yml").read_text()
        self.assertIn("xfit_ga4_native_outbound_readonly", src)
        self.assertNotIn("schedule:", src)
        self.assertNotIn("workflow_dispatch:", src)
        self.assertNotIn("wp_publish.py --publish", src)
        self.assertNotIn("plugin-install", src)
        self.assertNotIn("apply", src)


if __name__ == "__main__":
    unittest.main()
