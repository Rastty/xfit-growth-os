"""Regress actual beginner decision links, real WordPress body safety and one write."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.wp_publish import MARKER, PublishError
from scripts import xfit_beginner_goal_release as g


def live():
    original=json.loads(Path(
        "content/ready/xfit-os-doplnky-pro-zacatecniky.json"
    ).read_text(encoding="utf-8"))["content"]
    return MARKER+"\n"+original+"\n<p>Další dříve schválené doplnění webu.</p>"


def post(raw, *, status="publish", slug=g.SLUG, modified="2026-11-08T08:00:00",
         url=g.URL):
    return {
        "id":g.POST_ID,"slug":slug,"status":status,"link":url,
        "modified_gmt":modified,"content":{"raw":raw},
    }


class GoalReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.change=g.proposal()
        cls.before=live()
        cls.after=cls.before.replace(cls.change["original"],
                                     cls.change["replacement"],1)

    def test_reviewed_patch_preserves_entire_prior_content_and_link_order(self):
        self.assertEqual(self.before.count(self.change["original"]),1)
        self.assertEqual(self.after.count(self.change["replacement"]),1)
        self.assertEqual(self.after.replace(self.change["replacement"],
                                            self.change["original"],1),self.before)
        self.assertIn("0 Kč",self.after)
        self.assertIn("<details open>",self.after)
        self.assertEqual(self.after.count("<details open>"),1)
        self.assertEqual(g.prepare(post(self.before),self.change)["after"],self.after)

    def test_one_write_and_public_receipt_requires_immutable_backup(self):
        with tempfile.TemporaryDirectory() as d, \
             patch.object(g,"BACKUP",Path(d)/"rollback.json"), \
             patch.object(g,"remote",side_effect=[
                 post(self.before),post(self.before),post(self.after)]), \
             patch.object(g,"wp_request",return_value={
                 "id":g.POST_ID,"status":"publish"}) as writer, \
             patch.object(g,"normalized_base",return_value="https://xfit.cz"), \
             patch.object(g,"verify_public",return_value=True) as public:
            g.snapshot()
            saved=json.loads(g.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(saved["original_raw"],self.before)
            self.assertEqual(saved["remote_writes"],0)
            self.assertEqual(saved["after_sha"],g.digest(self.after))
            g.apply()
            writer.assert_called_once_with(
                "https://xfit.cz","posts/25458",
                payload={"content":self.after})
            public.assert_called_once_with()

    def test_timeout_after_committed_update_never_retries(self):
        with tempfile.TemporaryDirectory() as d, \
             patch.object(g,"BACKUP",Path(d)/"rollback.json"), \
             patch.object(g,"remote",side_effect=[
                 post(self.before),post(self.before),post(self.after)]), \
             patch.object(g,"wp_request",
                          side_effect=PublishError("network timeout")) as writer, \
             patch.object(g,"normalized_base",return_value="https://xfit.cz"), \
             patch.object(g,"verify_public",return_value=True):
            g.snapshot()
            g.apply()
            self.assertEqual(writer.call_count,1)

    def test_content_drift_before_update_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as d, \
             patch.object(g,"BACKUP",Path(d)/"rollback.json"), \
             patch.object(g,"remote",side_effect=[
                 post(self.before),
                 post(self.before+"<p>Concurrent editorial change.</p>")]), \
             patch.object(g,"wp_request") as writer:
            g.snapshot()
            with self.assertRaises(PublishError):
                g.apply()
            writer.assert_not_called()

    def test_wordpress_unchanged_after_failed_write_never_counts(self):
        with tempfile.TemporaryDirectory() as d, \
             patch.object(g,"BACKUP",Path(d)/"rollback.json"), \
             patch.object(g,"remote",side_effect=[
                 post(self.before),post(self.before),post(self.before)]), \
             patch.object(g,"wp_request",
                          side_effect=PublishError("HTTP 503")) as writer, \
             patch.object(g,"normalized_base",return_value="https://xfit.cz"):
            g.snapshot()
            with self.assertRaises(PublishError):
                g.apply()
            writer.assert_called_once()

    def test_already_applied_returns_no_new_write(self):
        with tempfile.TemporaryDirectory() as d, \
             patch.object(g,"BACKUP",Path(d)/"rollback.json"), \
             patch.object(g,"remote",return_value=post(self.after)), \
             patch.object(g,"wp_request") as writer, \
             patch.object(g,"verify_public",return_value=True):
            g.snapshot()
            g.apply()
            writer.assert_not_called()

    def test_unexpected_post_status_slug_url_and_old_section_block_release(self):
        for bad in (
            post(self.before,status="draft"),
            post(self.before,slug="unknown"),
            post(self.before,url="https://evil.example/"+g.SLUG+"/"),
            post(self.before,url=g.URL+"?preview=1"),
            post(self.before.replace(MARKER,"")),
            post(self.before.replace(self.change["original"],"")),
            post(self.before.replace(
                self.change["original"],self.change["original"]*2)),
        ):
            with self.subTest(status=bad["status"],url=bad["link"]):
                with self.assertRaises(PublishError):
                    g.prepare(bad,self.change)

    def test_public_page_has_all_goals_and_no_buy_answer_visible(self):
        snippet=self.change["replacement"]
        good="<html><h1>Pro začátečníky</h1><main>"+snippet+(
            "<p>Trénink a strava nejsou závislé na doplňcích.</p>"*7
        )+"</main></html>"
        self.assertTrue(g.verify_public(reader=lambda _:good))
        self.assertFalse(g.verify_public(reader=lambda _:
            good.replace("<details open>","<details>",1)))
        self.assertFalse(g.verify_public(reader=lambda _:
            good.replace(g.LINKS[1],"https://xfit.cz/other/",1)))
        self.assertFalse(g.verify_public(reader=lambda _:
            good.replace("První odpověď je otevřená","Vše je skryté",1)))

    def test_reviewed_manifest_rejects_external_or_unreviewed_links(self):
        # An unapproved revision must never add merchant redirects.
        self.assertEqual(len(g.LINKS),4)
        self.assertFalse(any("namaximum.cz" in x for x in g.LINKS))


if __name__=="__main__":
    unittest.main()
