"""Post-failure: source and public readback cannot be confused with POST."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import xfit_two_advisors_category_postfail_getonly as m
from scripts.xfit_supplements_two_advisors_category import PAGES


def post(row, *, categories=None):
    ident, slug, title = row
    body = ("<p>Bez rozhodnutí lze také nekupovat</p>" * 90 +
        "".join('<article class="xfit-product-card" '
                'data-xfit-product-id="' + str(i) + '">'
                '<a href="https://www.namaximum.cz/p/x">Nabídka</a></article>'
                for i in range(1,7)))
    return {
        "id":ident, "slug":slug, "status":"publish", "sticky":False,
        "link":"https://xfit.cz/"+slug+"/", "title":{"raw":title},
        "content":{"raw":body}, "excerpt":{"raw":"Poradce"},
        "categories":[3] if categories is None else categories,
        "modified_gmt":"2026-11-21T11:00:00",
    }


def archive(*, creatine=False, whey=False):
    paths = ["/xfit-os-doplnky-pro-zacatecniky/"]
    if creatine:
        paths.append("/"+PAGES[0][1]+"/")
    if whey:
        paths.append("/"+PAGES[1][1]+"/")
    paths += ["/old-guide-"+str(i)+"/" for i in range(1,12)]
    return ("<html><h1>Doplňky stravy</h1>"+ "".join(
        '<h3><a href="https://xfit.cz'+p+'">Guide</a></h3>' for p in paths)
        +"</html>")


def home():
    return ('<html><h3><a href="https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/">Guide</a></h3>'
            +''.join('<h3><a href="https://xfit.cz/old-'+str(i)+'/">Old</a></h3>'
                     for i in range(12))+'</html>')


class PostFailureReconcileTests(unittest.TestCase):
    def read(self, memberships, creatine=False, whey=False):
        def read_post(post_id):
            n=0 if post_id==PAGES[0][0] else 1
            return post(PAGES[n], categories=[3,44] if memberships[n] else [3])
        return m.state(get_category=lambda:[{
            "id":44, "slug":"doplnky-stravy",
            "name":"Doplňky stravy", "link":
                "https://xfit.cz/category/vyziva/doplnky-stravy/",
            "parent":5
        }], get_post=read_post,
        get_archive=lambda:archive(creatine=creatine,whey=whey),
        get_home=home)

    def test_both_post_changes_and_archive_top_three_are_proven(self):
        result=self.read((True,True),True,True)
        self.assertEqual(result["conclusion"], "TWO_ADVISORS_CATEGORY_AND_PUBLIC_VISIBLE")
        self.assertEqual(result["public_category_ranks"]["guide"],1)
        self.assertEqual(result["public_category_ranks"]["creatine_adviser"],2)
        self.assertEqual(result["public_category_ranks"]["whey_adviser"],3)
        self.assertEqual(result["wordpress_writes"],0)
        self.assertEqual(result["affiliate_clicks_sent"],0)
        self.assertTrue(all(p["commercial_source_shape_verified"] for p in result["post_statuses"]))

    def test_public_cache_stale_separate_from_wp_membership(self):
        result=self.read((True,True))
        self.assertEqual(result["conclusion"],
                         "BOTH_CATEGORIES_SET_PUBLIC_VISIBILITY_UNPROVEN")
        self.assertTrue(all(p["in_supplements_category"] is True
                            for p in result["post_statuses"]))

    def test_partial_membership_does_not_claim_full_success(self):
        result=self.read((True,False),True)
        self.assertEqual(result["conclusion"], "PARTIAL_POST_MEMBERSHIP_VERIFIED")

    def test_no_post_writes_no_automatic_retry(self):
        result=self.read((False,False))
        self.assertEqual(result["conclusion"],"BOTH_POSTS_STILL_OUTSIDE_CATEGORY")
        self.assertEqual(result["wordpress_writes"],0)
        self.assertEqual(result["post_attempts"],0)

    def test_source_missing_is_unknown_not_negative(self):
        result=m.state(get_category=lambda:[],get_post=lambda id:None,
                       get_archive=lambda:archive(),get_home=home)
        self.assertEqual(result["conclusion"],"POST_OUTCOME_UNCERTAIN")
        self.assertEqual(result["post_statuses"][0]["identity"],
                         "SOURCE_CHANGED_OR_UNAVAILABLE")

    def test_workflow_only_runs_get_and_does_not_mutate(self):
        workflow=Path(".github/workflows/xfit-two-advisors-postfail-getonly.yml").read_text()
        self.assertIn("xfit_two_advisors_category_postfail_getonly",workflow)
        self.assertNotIn("workflow_dispatch:",workflow)
        self.assertNotIn("schedule:",workflow)
        self.assertNotIn("snapshot",workflow)
        self.assertNotIn(" apply",workflow)
        self.assertNotIn("POST",workflow.split("steps:")[1])


if __name__=="__main__":
    unittest.main()
