"""Evidence-only check of paused two-adviser category placement."""
import unittest
from unittest.mock import patch

from scripts import xfit_supplements_category_reaudit as audit
from scripts.xfit_supplements_two_advisors_category import PAGES
from scripts.xfit_home_sticky_guide_onepost import (
    POST_ID, SLUG, TITLE, URL,
)
from scripts.wp_publish import PublishError
from tests.test_supplements_two_advisors_category import (
    category_html, home_html, source,
)


def guide():
    return {
        "id":POST_ID,"slug":SLUG,"status":"publish","link":URL,
        "sticky":True,"title":{"raw":TITLE},"excerpt":{"raw":"Průvodce pro začátečníky"},
        "content":{"raw":(
            '<p>Nekupujte bez ověření cíle. '
            '<a href="https://xfit.cz/xfit-os-kreatin-nebo-protein/">'
            'Výběr podle cíle</a>.</p>' * 36)},
        "categories":[3,44],"modified_gmt":"2026-11-22T08:01:00",
    }


class CategoryReadOnlyTests(unittest.TestCase):
    def test_real_scope_and_observational_positions_no_writes(self):
        items=[source(row) for row in PAGES]
        with patch("scripts.xfit_supplements_category_reaudit.read_all",
                   side_effect=AssertionError("no default")), \
             patch("scripts.xfit_supplements_category_reaudit.category_public_get",
                   side_effect=AssertionError("no default")), \
             patch("scripts.xfit_supplements_category_reaudit.homepage_get",
                   side_effect=AssertionError("no default")), \
             patch("scripts.xfit_supplements_category_reaudit.guide_get",
                   side_effect=AssertionError("no default")):
            data=audit.assess(
                source_reader=lambda:(44,items),
                archive_reader=lambda:category_html(),
                guide_reader=guide,
                home_reader=home_html)
        self.assertEqual(data["state"],"SOURCE_BACKED_CATEGORY_REVIEW_ONLY")
        self.assertEqual(data["category_id"],44)
        self.assertEqual(data["guide_category_rank"],1)
        self.assertEqual(data["homepage_guide_rank"],1)
        self.assertEqual(len(data["advisers"]),2)
        self.assertEqual(data["wordpress_post_attempts"],0)
        self.assertFalse(data["write_approved"])
        self.assertEqual([x["public_archive_rank"] for x in data["advisers"]],
                         [None,None])
        for item in data["advisers"]:
            self.assertFalse(item["already_in_supplement_category"])
            self.assertEqual(len(item["source_sha256"]),64)
            self.assertNotIn("namaximum",str(item))
            self.assertNotIn("a_aid",str(item))

    def test_state_reflects_previous_category_assignment_no_false_missing(self):
        items=[source(row,categories=[3,44]) for row in PAGES]
        data=audit.assess(
            source_reader=lambda:(44,items),
            archive_reader=lambda:category_html(include=True),
            guide_reader=guide,
            home_reader=home_html)
        self.assertTrue(all(x["already_in_supplement_category"]
                            for x in data["advisers"]))
        self.assertEqual([x["public_archive_rank"] for x in data["advisers"]],
                         [3,2])
        self.assertFalse(data["write_approved"])

    def test_wrong_identity_or_missing_protected_guide_does_not_bless(self):
        items=[source(row) for row in PAGES]
        for source_args in (
            lambda: (44,[dict(items[0],id=1234),items[1]]),
            lambda: (44,[items[0]]),
            lambda: (0,items),
        ):
            with self.subTest(case=str(source_args)):
                with self.assertRaises((PublishError,IndexError)):
                    audit.assess(source_reader=source_args,
                                 archive_reader=lambda:category_html(),
                                 guide_reader=guide,home_reader=home_html)
        badguide=guide()
        badguide["categories"]=[3]
        with self.assertRaises(PublishError):
            audit.assess(source_reader=lambda:(44,items),
                         archive_reader=lambda:category_html(),
                         guide_reader=lambda:badguide,home_reader=home_html)

    def test_category_or_homepage_guide_displacement_refuses_release(self):
        items=[source(row) for row in PAGES]
        bad_archive=category_html().replace(
            "/xfit-os-doplnky-pro-zacatecniky/",
            "/unapproved-hub/",1)
        with self.assertRaises(PublishError):
            audit.assess(source_reader=lambda:(44,items),
                         archive_reader=lambda:bad_archive,
                         guide_reader=guide,home_reader=home_html)
        with self.assertRaises(PublishError):
            audit.assess(source_reader=lambda:(44,items),
                         archive_reader=lambda:category_html(),
                         guide_reader=guide,
                         home_reader=lambda:home_html().replace(
                             "/xfit-os-doplnky-pro-zacatecniky/","/broken/"))

if __name__=="__main__":
    unittest.main()
