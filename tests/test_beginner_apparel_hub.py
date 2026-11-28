import unittest
from scripts.xfit_beginner_apparel_hub import V2_NAV, EXTRA_NAV, NEW_NAV, APPAREL_URL, revised, public_complete
from scripts.wp_publish import PublishError

class ApparelHubTests(unittest.TestCase):
    def test_append_ninth_route_without_changing_original_six_or_editorial(self):
        before="<p>Original.</p>\n"+V2_NAV+EXTRA_NAV+"<h2>Other material</h2>"
        after=revised(before)
        self.assertEqual(after.replace(NEW_NAV,EXTRA_NAV),before)
        self.assertTrue(public_complete(after))
        self.assertEqual(revised(after),after)
        self.assertEqual(NEW_NAV.count(APPAREL_URL),1)
        with self.assertRaises(PublishError):
            revised(before.replace("Jídlo a praktické pomůcky","Changed"))
