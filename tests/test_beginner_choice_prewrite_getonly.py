"""GET-only prewrite diagnosis: no article leaks, no writes."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import xfit_beginner_hub_choice_prewrite_getonly as d
from scripts import xfit_beginner_hub_choice_onepost as b
from scripts.wp_publish import PublishError


def post():
    doc=b.ready()
    return {
        "id":b.POST_ID, "slug":b.SLUG, "link":b.URL,
        "status":"publish", "sticky":True, "title":{"raw":doc["title"]},
        "content":{"raw":doc["content"]},
        "excerpt":{"raw":doc["excerpt"]},
        "categories":[3,b.CATEGORY_ID],
        "modified_gmt":"2026-11-21T11:30:00",
    }


class HubPrewriteDiagnosisTests(unittest.TestCase):
    def setUp(self):
        # Synthetic offline WordPress source is not the authenticated live
        # production source. Never alter the real SHA pin to suit tests.
        self.pin=patch.object(
            b, "REVIEWED_CURRENT_SOURCE_SHA256",
            b.sha(post()["content"]["raw"]))
        self.pin.start()
        self.addCleanup(self.pin.stop)

    def test_normal_published_git_source_and_public_rank(self):
        with patch.object(d,"card_rank",return_value=1), \
             patch.object(d,"archive_rank",return_value=1), \
             patch.object(b,"wp_request") as writer:
            result=d.run(read_post=post,read_home=lambda:"home",
                         read_category=lambda:"category")
        self.assertEqual(result["failure_stage"],"ALL_PREWRITE_CHECKS_PASS")
        self.assertTrue(result["ready_git_body_and_links_match_live_wp"])
        self.assertTrue(result["intro_navigation_rewrite_eligible"])
        self.assertEqual(result["wordpress_writes"],0)
        self.assertEqual(result["post_attempts"],0)
        self.assertEqual(result["expected_old_nav_marker_count"],1)
        writer.assert_not_called()

    def test_edited_wp_source_is_reported_as_git_drift_not_overwritten(self):
        p=post()
        p["content"]["raw"]=p["content"]["raw"].replace("Nejvíc", "Nejméně")
        result=d.run(read_post=lambda:p)
        self.assertEqual(result["failure_stage"],"GIT_APPROVED_SOURCE_DRIFT")
        self.assertEqual(result["wordpress_writes"],0)
        self.assertNotIn("Nejméně",json.dumps(result))

    def test_invalid_post_cannot_elevate_to_edits(self):
        p=post()
        p["sticky"]=False
        result=d.run(read_post=lambda:p)
        self.assertEqual(result["failure_stage"],"WORDPRESS_IDENTITY")
        self.assertEqual(result["post_attempts"],0)

    def test_public_path_mismatch_does_not_warrant_post(self):
        with patch.object(d,"card_rank",return_value=4), \
             patch.object(d,"archive_rank",return_value=1):
            result=d.run(read_post=post,read_home=lambda:"home",
                         read_category=lambda:"category")
        self.assertEqual(result["failure_stage"],"PUBLIC_DISCOVERY_DRIFT")
        self.assertEqual(result["wordpress_writes"],0)

    def test_source_unavailable_unknown_not_previous_source_false(self):
        result=d.run(read_post=lambda: (_ for _ in ()).throw(PublishError("private")))
        self.assertEqual(result["failure_stage"],"WORDPRESS_IDENTITY")
        self.assertEqual(result["published_wp_identity"],"UNKNOWN")
        self.assertNotIn("private",json.dumps(result))

    def test_workflow_only_get_no_post_or_dispatch(self):
        y=Path(".github/workflows/xfit-beginner-choice-prewrite-getonly.yml").read_text()
        self.assertIn("xfit_beginner_hub_choice_prewrite_getonly",y)
        self.assertNotIn("workflow_dispatch:",y)
        self.assertNotIn("schedule:",y)
        self.assertNotIn(" onepost apply",y)


if __name__=="__main__":
    unittest.main()
