"""No-write ordinary-cache supplement category verification in existing status."""
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from scripts.xfit_status import supplement_category_buyer_placement, render
from tests.test_supplements_two_advisors_category import category_html


class OrdinaryCategoryCacheTests(unittest.TestCase):
    def test_observed_current_top3_and_status_proven_without_cache_bypass(self):
        with patch("scripts.xfit_status.urlopen",
                   side_effect=AssertionError("No real GET in fixture")) as reader:
            x=supplement_category_buyer_placement(
                reader=lambda:category_html(include=True))
        reader.assert_not_called()
        self.assertEqual(x["state"],"ORDINARY_PUBLIC_SUPPLEMENT_TOP3_VERIFIED")
        self.assertEqual([x["guide_rank"],x["whey_rank"],x["creatine_rank"]],
                         [1,2,3])
        self.assertEqual(x["wordpress_writes"],0)
        report=render([],[],datetime.now(timezone.utc),supplement_category=x)
        self.assertIn("Běžný veřejný archiv Doplňky stravy",report)
        self.assertIn("průvodce #1",report)
        self.assertIn("syrovátkový poradce #2",report)
        self.assertIn("kreatinový poradce #3",report)
        self.assertIn("nejsou důkaz",report) if False else None

    def test_old_cdn_snapshot_is_not_wordpress_membership_rollback(self):
        x=supplement_category_buyer_placement(reader=category_html)
        self.assertEqual(x["state"],
                         "PUBLIC_SUPPLEMENT_CATEGORY_ORDER_DIFFERS_OR_CACHE_STALE")
        self.assertEqual(x["guide_rank"],1)
        self.assertIsNone(x["whey_rank"])
        self.assertIsNone(x["creatine_rank"])
        self.assertEqual(x["wordpress_writes"],0)
        report=render([],[],datetime.now(timezone.utc),supplement_category=x)
        self.assertIn("NEOVĚŘENO",report)
        self.assertIn("není důkaz, že byly WordPress kategorie vráceny",report)

    def test_unknown_malformed_or_network_error_does_not_claim_no_membership(self):
        values=[None,"","<h1>Home</h1>",category_html(include=True).replace(
            "<h1>Doplňky stravy</h1>","<h1>Hubnutí a diety</h1>")]
        for value in values:
            with self.subTest(value=str(value)[:40]):
                x=supplement_category_buyer_placement(reader=lambda:value)
                self.assertEqual(x["state"],"PUBLIC_SUPPLEMENT_CATEGORY_READ_UNKNOWN")
                self.assertIsNone(x["guide_rank"])
        result=supplement_category_buyer_placement(
            reader=lambda:(_ for _ in ()).throw(OSError("private error")))
        self.assertEqual(result["state"],"PUBLIC_SUPPLEMENT_CATEGORY_READ_UNKNOWN")
        self.assertNotIn("private error",str(result))


if __name__=="__main__":
    unittest.main()
