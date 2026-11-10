"""Regression contract for the reproducible XFIT WordPress analytics plugin ZIP."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import build_xfit_wp_plugin as package


class AnalyticsPluginPackageTests(unittest.TestCase):
    def test_package_contains_only_three_approved_first_party_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "xfit-analytics-0.1.2.zip"
            receipt = package.build(zip_path)
            self.assertEqual(receipt["status"], "INSTALLABLE_PLUGIN_PACKAGE_BUILT")
            self.assertFalse(receipt["wp_installed"])
            self.assertFalse(receipt["ga4_events_observed"])
            self.assertEqual(receipt["wordpress_writes"], 0)
            self.assertTrue(zip_path.is_file())
            with zipfile.ZipFile(zip_path) as archive:
                names = archive.namelist()
                self.assertEqual(names, [
                    "xfit-analytics/xfit-analytics.php",
                    "xfit-analytics/assets/xfit-webtoffee-bridge.js",
                    "xfit-analytics/assets/xfit-outbound.js",
                ])
                for source, dest in package.MANIFEST:
                    self.assertEqual(
                        archive.read(dest),
                        (package.ROOT / source).read_bytes(),
                    )

    def test_wp_plugin_loads_only_approved_guides_and_never_injects_inline_js(self):
        php = (package.ROOT / "wordpress-plugin/xfit-analytics/xfit-analytics.php"
               ).read_text(encoding="utf-8")
        self.assertTrue(php.startswith("<?php"))
        self.assertIn("Version: 0.1.2", php)
        self.assertIn("$version = '0.1.2'", php)
        self.assertEqual(package.VERSION, "0.1.2")
        self.assertIn("Plugin Name: XFIT Verified Affiliate Click Analytics", php)
        self.assertIn("is_singular( 'post' )", php)
        self.assertIn("'xfit-os-kreatin-poradce'", php)
        self.assertIn("'xfit-os-syrovatkovy-protein-porovnani'", php)
        self.assertIn("in_array( $post->post_name, $approved_slugs, true )", php)
        self.assertIn("wp_enqueue_script(", php)
        self.assertIn("array( 'xfit-webtoffee-analytics-consent' )", php)
        self.assertNotIn("wp_add_inline_script(", php)
        self.assertNotIn("wp_remote_post(", php)

    def test_package_is_byte_for_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.zip", Path(tmp) / "b.zip"
            package.build(a)
            package.build(b)
            self.assertEqual(a.read_bytes(), b.read_bytes())


if __name__ == "__main__":
    unittest.main()
