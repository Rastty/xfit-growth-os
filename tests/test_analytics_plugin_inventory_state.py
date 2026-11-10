"""Read-only discovery of a preinstalled XFIT analytics package.

Plugin upload/activation is NOT performed here and requires its own authority.
"""
import unittest
from unittest.mock import patch

from scripts import xfit_analytics_cmp_preflight as probe


def row(name, status, version="0.1.0"):
    return {"plugin": name, "status": status, "version": version}


class InstalledPluginReadinessTests(unittest.TestCase):
    def inspect(self, rows):
        calls = []
        def reader(base, path):
            calls.append((base, path))
            return rows
        with patch.object(probe, "normalized_base", return_value="https://xfit.cz"):
            result = probe.inspect_plugins(wp_fetch=reader)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("status=active", calls[0][1])
        self.assertIn("_fields=plugin,status,version", calls[0][1])
        return result

    def test_inactive_custom_package_can_be_distinguished_from_absent(self):
        for status in ("active", "inactive"):
            with self.subTest(status=status):
                result = self.inspect([
                    row("cookie-law-info/cookie-law-info.php", "active", "3.0.0"),
                    row("xfit-analytics/xfit-analytics.php", status),
                ])
                self.assertEqual(
                    result["xfit_analytics_plugin_state"],
                    "INSTALLED_" + status.upper(),
                )
                self.assertIn("webtoffee", result["recognized_active_providers"])
                self.assertEqual(result["active_plugin_count"],
                                 2 if status == "active" else 1)
                self.assertNotIn("xfit-analytics/xfit-analytics.php", str(result))

    def test_complete_inventory_absence_is_not_confused_with_inactive(self):
        result = self.inspect([
            row("cookie-law-info/cookie-law-info.php", "active", "3.0.0"),
            row("private-plugin/private.php", "inactive", "42.0"),
        ])
        self.assertEqual(result["xfit_analytics_plugin_state"], "NOT_INSTALLED")
        self.assertNotIn("private-plugin", str(result))

    def test_unknown_or_duplicate_plugin_records_fail_closed(self):
        duplicates = [
            row("xfit-analytics/xfit-analytics.php", "active"),
            row("xfit-analytics/xfit-analytics.php", "inactive"),
        ]
        for rows in (duplicates,
                     [row("xfit-analytics/xfit-analytics.php", "unknown")]):
            with self.subTest(rows=rows):
                self.assertEqual(
                    self.inspect(rows)["xfit_analytics_plugin_state"],
                    "UNKNOWN_PLUGIN_INVENTORY_CONFLICT",
                )
        full_page = [
            row(f"other-plugin-{i}/plugin.php", "active")
            for i in range(100)
        ]
        self.assertEqual(
            self.inspect(full_page)["xfit_analytics_plugin_state"],
            "UNKNOWN_INVENTORY_MAY_BE_PAGINATED",
        )

    def test_inventory_failure_never_claims_no_package(self):
        with patch.object(probe, "normalized_base", return_value="https://xfit.cz"):
            result = probe.inspect_plugins(
                wp_fetch=lambda *_: (_ for _ in ()).throw(
                    probe.PublishError("permission denied")
                )
            )
        self.assertEqual(result["xfit_analytics_plugin_state"],
                         "UNKNOWN_NO_AUTHORIZED_INVENTORY")


if __name__ == "__main__":
    unittest.main()
