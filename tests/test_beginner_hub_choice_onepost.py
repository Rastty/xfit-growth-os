"""Backed-up XFIT homepage choice strip: no new articles or merchant links."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import xfit_beginner_hub_choice_onepost as m
from scripts.wp_publish import PublishError, article_visible, editorial_links


def old_post(*, modified="2026-11-21T11:00:00", sticky=True, categories=None):
    doc=m.ready()
    return {
        "id":m.POST_ID, "slug":m.SLUG, "link":m.URL,
        "status":"publish", "sticky":sticky,
        "title":{"raw":doc["title"]},
        "content":{"raw":doc["content"]},
        "excerpt":{"raw":doc["excerpt"]},
        "categories":[3,44] if categories is None else categories,
        "modified_gmt":modified,
    }


def updated_post():
    existing=old_post()
    revised=m.revised_from_original(existing,m.ready())
    after=dict(existing)
    after["content"]={"raw":revised}
    after["modified_gmt"]="2026-11-21T11:10:00"
    return after


class BeginnerHubChoiceTests(unittest.TestCase):
    def test_existing_source_matches_ready_and_only_one_navigation_block_replaced(self):
        old=old_post()
        new=m.revised_from_original(old,m.ready())
        a=old["content"]["raw"].index(m.OLD_START)
        b=old["content"]["raw"].index(m.END_NEXT_SECTION)
        self.assertTrue(new.startswith(old["content"]["raw"][:a]))
        self.assertTrue(new.endswith(old["content"]["raw"][b:]))
        self.assertEqual(new.count(m.REVISION_MARKER),1)
        self.assertNotIn(m.OLD_START,new)
        self.assertEqual(m.editorial_links(new).count(m.CHOICES[1]),2)
        self.assertEqual(m.editorial_links(new).count(m.CHOICES[2]),2)
        self.assertTrue(all("namaximum.cz" not in item
                            for item in editorial_links(new)))
        self.assertIn("Začínám cvičit – bez nákupu",new)
        self.assertIn("Hledám protein",new)
        self.assertIn("Hledám kreatin",new)
        self.assertIn("Ještě nevím",new)
        self.assertNotIn("<script",new)
        self.assertNotIn("<form",new)

    def test_refuse_unowned_edited_source_sticky_or_category_drift(self):
        for change in (
            {"id":1}, {"slug":"other"}, {"sticky":False},
            {"categories":[3]}, {"title":{"raw":"Different Title"}},
            {"content":{"raw":m.ready()["content"].replace("nejvíc", "nejméně")}},
        ):
            p=old_post()
            p.update(change)
            with self.subTest(change=change), self.assertRaises(PublishError):
                m.revised_from_original(p,m.ready())

    def test_no_duplicate_second_revision(self):
        p=updated_post()
        with self.assertRaises(PublishError):
            m.revised_from_original(p,m.ready())

    def test_three_way_public_anchor_collection_exact(self):
        parser=m.PublicChoiceLinks()
        parser.feed("<section id='other'><a href='https://evil.tld/'>X</a></section>"
                    +m.NEW_NAV+"<p><a href='#other'>Outside</a></p>")
        self.assertEqual(parser.hrefs,list(m.CHOICES))

    def test_snapshot_contains_full_original_before_remote_post(self):
        p=old_post()
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m,"BACKUP",Path(tmp)/"original.json"), \
             patch.object(m,"source_get",return_value=p), \
             patch.object(m,"homepage_get",return_value="homepage"), \
             patch.object(m,"category_public_get",return_value="category"), \
             patch.object(m,"card_rank",return_value=1), \
             patch.object(m,"archive_rank",return_value=1), \
             patch.object(m,"wp_request") as writer:
            out=StringIO()
            with redirect_stdout(out):
                m.snapshot()
            backup=json.loads(m.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(backup["before"],p)
            self.assertEqual(backup["raw_sha256"],m.sha(p["content"]["raw"]))
            self.assertEqual(backup["wordpress_writes"],0)
            self.assertEqual(backup["previous_home_rank"],1)
            self.assertEqual(backup["previous_category_rank"],1)
            writer.assert_not_called()
            with self.assertRaisesRegex(PublishError,"overwrite"):
                m.snapshot()

    def test_one_post_only_and_full_public_readback(self):
        before=old_post()
        after=updated_post()
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m,"BACKUP",Path(tmp)/"original.json"):
            with patch.object(m,"source_get",return_value=before), \
                 patch.object(m,"homepage_get",return_value="homepage"), \
                 patch.object(m,"category_public_get",return_value="category"), \
                 patch.object(m,"card_rank",return_value=1), \
                 patch.object(m,"archive_rank",return_value=1):
                m.snapshot()
            with patch.object(m,"source_get",side_effect=[before,after]), \
                 patch.object(m,"homepage_get",return_value="homepage"), \
                 patch.object(m,"category_public_get",return_value="category"), \
                 patch.object(m,"card_rank",return_value=1), \
                 patch.object(m,"archive_rank",return_value=1), \
                 patch.object(m,"normalized_base",return_value="https://xfit.cz"), \
                 patch.object(m,"wp_request",return_value={"id":m.POST_ID}) as writer, \
                 patch.object(m,"verify_public",return_value=True) as public_check, \
                 patch.object(m,"public_links",return_value=list(m.CHOICES)):
                out=StringIO()
                with redirect_stdout(out):
                    m.apply()
            writer.assert_called_once()
            self.assertEqual(list(writer.call_args.kwargs["payload"]),["content"])
            self.assertEqual(writer.call_args.args[1],"posts/"+str(m.POST_ID))
            public_check.assert_called_once()
            self.assertIn("PUBLIC_THREE_WAY_DECISION_VERIFIED",out.getvalue())
            self.assertTrue(m.preserve_unchanged(before,after))

    def test_uncertain_post_never_retried(self):
        before=old_post()
        after=updated_post()
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m,"BACKUP",Path(tmp)/"original.json"):
            with patch.object(m,"source_get",return_value=before), \
                 patch.object(m,"homepage_get",return_value="homepage"), \
                 patch.object(m,"category_public_get",return_value="category"), \
                 patch.object(m,"card_rank",return_value=1), \
                 patch.object(m,"archive_rank",return_value=1):
                m.snapshot()
            with patch.object(m,"source_get",side_effect=[before,after]), \
                 patch.object(m,"homepage_get",return_value="homepage"), \
                 patch.object(m,"category_public_get",return_value="category"), \
                 patch.object(m,"card_rank",return_value=1), \
                 patch.object(m,"archive_rank",return_value=1), \
                 patch.object(m,"normalized_base",return_value="https://xfit.cz"), \
                 patch.object(m,"wp_request",side_effect=PublishError("timeout")) as writer, \
                 patch.object(m,"verify_public",return_value=True), \
                 patch.object(m,"public_links",return_value=list(m.CHOICES)):
                m.apply()
            writer.assert_called_once()

    def test_source_drift_blocks_before_post(self):
        before=old_post()
        changed=old_post(modified="2026-11-21T11:10:00")
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m,"BACKUP",Path(tmp)/"original.json"):
            with patch.object(m,"source_get",return_value=before), \
                 patch.object(m,"homepage_get",return_value="homepage"), \
                 patch.object(m,"category_public_get",return_value="category"), \
                 patch.object(m,"card_rank",return_value=1), \
                 patch.object(m,"archive_rank",return_value=1):
                m.snapshot()
            with patch.object(m,"source_get",return_value=changed), \
                 patch.object(m,"wp_request") as writer:
                with self.assertRaisesRegex(PublishError,"Concurrent"):
                    m.apply()
                writer.assert_not_called()

    def test_all_content_except_navigation_is_same_when_revised(self):
        p=old_post()
        original=p["content"]["raw"]
        updated=m.revised_from_original(p,m.ready())
        before,after=original.split(m.OLD_START,1)
        _nav,rest=after.split(m.END_NEXT_SECTION,1)
        self.assertTrue(updated.startswith(before))
        self.assertTrue(updated.endswith(m.END_NEXT_SECTION+rest))
        self.assertEqual(updated.count(m.END_NEXT_SECTION),1)

    def test_one_time_workflow_backup_precedes_post_and_no_schedule(self):
        yml=Path(".github/workflows/xfit-beginner-hub-choice-onepost.yml").read_text()
        self.assertIn("xfit_beginner_hub_choice_onepost snapshot",yml)
        self.assertIn("xfit_beginner_hub_choice_onepost apply",yml)
        self.assertIn("if-no-files-found: error",yml)
        self.assertNotIn("workflow_dispatch:",yml)
        self.assertNotIn("schedule:",yml)


if __name__=="__main__":
    unittest.main()
