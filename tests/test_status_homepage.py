"""Existing status lane now observes real public-home distribution without writes."""
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from scripts.xfit_status import (
    homepage_buyer_placement, render, HOMEPAGE_GUIDE_SLUGS,
)


def homepage(slugs=None):
    slugs = slugs or HOMEPAGE_GUIDE_SLUGS
    posts = list(slugs) + ["other-post-"+str(i) for i in range(1, 9)]
    return ("<html><body><main>" +
            "".join('<h3><a href="https://xfit.cz/'+slug+
                    '/">Článek</a></h3>' for slug in posts)
            + "</main><aside><a href='https://xfit.cz/'>Non-card link</a></aside>"
            + "</body></html>")


class HomepageStatusTests(unittest.TestCase):
    def test_existing_public_top3_observation_is_not_a_sales_claim(self):
        result=homepage_buyer_placement(reader=lambda:homepage())
        self.assertEqual(result["state"], "ORDINARY_PUBLIC_HOME_TOP3_VERIFIED")
        self.assertEqual((result["reader_first_rank"],result["whey_rank"],
                          result["creatine_rank"]), (1,2,3))
        self.assertEqual(result["wordpress_writes"],0)
        self.assertEqual(result["scope"],"ORDINARY_PUBLIC_HTML_NO_CACHE_BYPASS")
        body=render([],[],datetime(2026,11,22,tzinfo=timezone.utc),
                    homepage=result)
        self.assertIn("průvodce bez nákupu #1",body)
        self.assertIn("syrovátkový poradce #2",body)
        self.assertIn("kreatinový poradce #3",body)
        self.assertIn("neprokazuje globální cache ani nárůst kliknutí",body)
        self.assertNotIn("zvýšení tržeb",body)

    def test_stale_homepage_is_observed_not_called_wordpress_rollback(self):
        posts=[HOMEPAGE_GUIDE_SLUGS[0], "testosteronove-boostery",
               "jiny-clanek", HOMEPAGE_GUIDE_SLUGS[1]]
        result=homepage_buyer_placement(reader=lambda:homepage(posts))
        self.assertEqual(result["state"],"PUBLIC_HOME_ORDER_DIFFERS_OR_CACHE_STALE")
        self.assertEqual(result["reader_first_rank"],1)
        self.assertEqual(result["whey_rank"],4)
        self.assertIsNone(result["creatine_rank"])
        self.assertEqual(result["wordpress_writes"],0)
        body=render([],[],datetime.now(timezone.utc),homepage=result)
        self.assertIn("NEOVĚŘENO",body)

    def test_missing_or_malformed_public_response_keeps_unknown(self):
        for body in ("", "<h1>Title only</h1>",
                     "<script><h3><a href='https://xfit.cz/"+
                     HOMEPAGE_GUIDE_SLUGS[0]+"/'>fake</a></h3></script>"):
            with self.subTest(body=body[:20]):
                x=homepage_buyer_placement(reader=lambda:body)
                self.assertEqual(x["state"],"PUBLIC_HOME_READ_UNKNOWN")
                self.assertIsNone(x["reader_first_rank"])
        x=homepage_buyer_placement(reader=lambda:(_ for _ in ()).throw(
            OSError("secret config")))
        self.assertEqual(x["state"],"PUBLIC_HOME_READ_UNKNOWN")
        self.assertNotIn("secret",str(x))

    def test_no_network_when_reader_injected_and_no_tracking(self):
        with patch("scripts.xfit_status.urlopen",
                   side_effect=AssertionError("Must not fetch")) as fetch:
            x=homepage_buyer_placement(reader=lambda:homepage())
        fetch.assert_not_called()
        self.assertEqual(x["wordpress_writes"],0)
        self.assertFalse(any("namaximum.cz" in str(value) for value in x.values()))


if __name__=="__main__":
    unittest.main()
