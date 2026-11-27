import unittest
from scripts.xfit_beginner_extra_lanes_hub import (
    V2_NAV, EXTRA_NAV, DRINK_URL, BUTTER_URL, revised, public_complete,
)
from scripts.wp_publish import PublishError

class ExtraLanesHubTests(unittest.TestCase):
    def test_exact_insert_preserves_existing_navigation_and_content(self):
        before = "<p>Original.</p>\n" + V2_NAV + "<h2>Other material</h2>"
        after = revised(before)
        self.assertEqual(after.replace(EXTRA_NAV,""),before)
        self.assertTrue(public_complete(after))
        self.assertEqual(revised(after),after)
        self.assertIn(DRINK_URL,EXTRA_NAV)
        self.assertIn(BUTTER_URL,EXTRA_NAV)
        with self.assertRaises(PublishError):
            revised(before.replace("Hledám kreatin","Changed"))
