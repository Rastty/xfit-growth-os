import unittest
from datetime import datetime, timezone, timedelta
import json
from scripts.xfit_multishop_readiness import profile, valid_gtin, explicit_brand
from scripts.wp_publish import PublishError
from test_equipment_comparison import item as gear_item
from test_plant_comparison import item as plant_item

NOW = datetime(2026, 11, 27, 16, tzinfo=timezone.utc)

def gtin(prefix):
    total = sum(int(digit) * (3 if i % 2 == 0 else 1)
                for i, digit in enumerate(reversed(prefix)))
    return prefix + str((10-total%10)%10)

def fixture(*rows):
    return {"merchant": "namaximum.cz", "merchant_match": True,
            "fetched_at_utc": NOW.isoformat(), "products": list(rows)}

def source(row, code, brand="Demo výrobce"):
    return {**row, "ean": code, "manufacturer": brand}

class MultiShopReadinessTests(unittest.TestCase):
    def test_checksum_preserves_leading_zero_and_rejects_bad_codes(self):
        for prefix in ("1234567", "01234567890", "859123456789", "0859123456789"):
            code = gtin(prefix)
            self.assertTrue(valid_gtin(code))
            self.assertFalse(valid_gtin(code[:-1] + str((int(code[-1])+1)%10)))
        for bad in (None, 8591234567890, "0000000000000", "11111111", " 12345670", "ABC12345"):
            self.assertFalse(valid_gtin(bad))
        for bad in (None, "", "Unknown", "bez značky", "-"):
            self.assertFalse(explicit_brand(bad))

    def test_actual_scope_and_ambiguity_screen_never_claims_multishop(self):
        first = gtin("859123456789")
        second = gtin("859123456788")
        third = gtin("859123456787")
        rows = [
            source(plant_item(11, "Sójový protein 500 g", 249, path="soja"), first),
            source(gear_item(21, "Yoga Mat", 499, path="mat"), second),
            source(gear_item(22, "Resistance Band", 349, path="band"), third, "unknown"),
            source(gear_item(23, "Yoga Mat", 599, path="mat2"), "0" + second),
        ]
        report = profile(fixture(*rows), now=NOW)
        self.assertEqual(report["scopes"]["all"]["source_rows"], 4)
        self.assertEqual(report["scopes"]["all"]["gtin_checksum_valid"], 4)
        self.assertEqual(report["scopes"]["all"]["ambiguous_gtin_or_source_id"], 2)
        self.assertEqual(report["scopes"]["all"]["unique_gtin_brand_price_dispatch_screen"], 1)
        self.assertEqual(report["scopes"]["plant_protein"]["unique_gtin_brand_price_dispatch_screen"], 1)
        self.assertEqual(report["scopes"]["equipment_mat"]["ambiguous_gtin_or_source_id"], 2)
        self.assertEqual(report["scopes"]["equipment_band"]["explicit_brand_field"], 0)
        self.assertFalse(report["price_comparison_publish_ready"])
        self.assertEqual(report["same_product_cross_merchant_matches"], "UNKNOWN")
        self.assertNotIn(first, json.dumps(report))
        self.assertNotIn("Demo výrobce", json.dumps(report))

    def test_stale_catalog_and_foreign_identity_stop(self):
        row = source(gear_item(21, "Yoga Mat", 499, path="mat"), gtin("859123456788"))
        for catalog in (dict(fixture(row), merchant_match=False),
                        dict(fixture(row), fetched_at_utc=(NOW-timedelta(days=1)).isoformat()),
                        fixture(dict(row, merchant="Other"))):
            with self.assertRaises(PublishError):
                profile(catalog, now=NOW)

    def test_slow_dispatch_is_not_publish_ready_and_duplicate_id_excluded(self):
        row = source(gear_item(21, "Yoga Mat", 499, path="mat"), gtin("859123456788"))
        rows = [dict(row, delivery_date="10")]
        out = profile(fixture(*rows), now=NOW)
        self.assertEqual(out["scopes"]["equipment_mat"]["unique_gtin_brand_price_dispatch_screen"], 0)
        out = profile(fixture(row, dict(row, ean=gtin("859123456787"))), now=NOW)
        self.assertEqual(out["scopes"]["all"]["ambiguous_gtin_or_source_id"], 2)

if __name__ == "__main__":
    unittest.main()
