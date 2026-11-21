"""One-published-post, category-only XFIT navigation upgrade. No bulk archive edits."""
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import xfit_supplements_category_hub_onepost as m
from scripts.wp_publish import PublishError


CAT = {"id":22, "slug":m.CAT_SLUG, "name":m.CAT_NAME,
       "link":m.CAT_URL, "parent":5, "count":1456}


def guide(*, categories=None, modified="2026-11-21T10:45:53", sticky=True):
    return {
        "id": m.POST_ID, "slug":m.SLUG, "status":"publish",
        "sticky":sticky, "link":m.URL,
        "title":{"raw":m.TITLE},
        "content":{"raw": "<p>Začátečník může nakupovat, nebo nekupovat.</p>" * 80
                   + '<a href="https://xfit.cz/xfit-os-kreatin-nebo-protein/">Pomocník</a>'},
        "excerpt":{"raw":"Odborný výběr doplňků bez zbytečných nákupů."},
        "categories": [3] if categories is None else categories,
        "modified_gmt":modified,
    }


def archive(*, guide_rank=None):
    paths = ["/stary-supplement-clanek-" + str(i) + "/"
             for i in range(1, 13)]
    if guide_rank is not None:
        paths.insert(guide_rank - 1, "/" + m.SLUG + "/")
    return ("<html><head><link rel='canonical' href='" + m.CAT_URL + "'></head>"
            "<body><h1>Doplňky stravy</h1><main>" +
            "".join('<h3><a href="https://xfit.cz' + url + '">Článek</a></h3>'
                    for url in paths) +
            "</main><aside><p>Nejnovější příspěvky</p></aside></body></html>")


class SupplementsCategoryUpgradeTests(unittest.TestCase):
    def test_term_identity_exact_name_child_slug_and_canonical(self):
        self.assertEqual(m.category_identity([CAT]), 22)
        for rows in ([], [CAT, CAT],
                     [dict(CAT, link="https://xfit.cz/category/other/")],
                     [dict(CAT, parent=0)],
                     [dict(CAT, slug="other")]):
            with self.subTest(rows=rows), self.assertRaises(PublishError):
                m.category_identity(rows)

    def test_guide_identity_requires_existing_featured_no_buy_content(self):
        self.assertEqual(m.guide_identity(guide())["id"], m.POST_ID)
        for change in (
            {"id":1}, {"slug":"something"}, {"status":"draft"},
            {"sticky":False}, {"link":"https://other.tld/foo/"},
            {"title":{"raw":"Different"}},
            {"content":{"raw":"too short"}},
            {"categories":[3,3]}, {"categories":[True]},
        ):
            with self.subTest(change=change), self.assertRaises(PublishError):
                m.guide_identity(dict(guide(), **change))

    def test_category_rank_is_real_heading_list_and_not_footer_card(self):
        self.assertIsNone(m.archive_rank(archive()))
        self.assertEqual(m.archive_rank(archive(guide_rank=1)), 1)
        self.assertEqual(m.archive_rank(archive(guide_rank=2)), 2)
        self.assertEqual(m.archive_rank(archive(guide_rank=12)), 12)
        with self.assertRaisesRegex(PublishError, "H1"):
            m.archive_rank(archive().replace("Doplňky stravy", "Ostatní"))

    def test_snapshot_pins_original_categories_and_all_wp_source_before_write(self):
        before = guide()
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(m, "BACKUP", Path(temp)/"original.json"), \
             patch.object(m, "checked_source", return_value=(22,before)), \
             patch.object(m, "category_public_get", return_value=archive()), \
             patch.object(m, "homepage_get",
                          return_value=_homepage()), \
             patch.object(m, "wp_request") as writer:
            m.snapshot()
            saved = json.loads(m.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(saved["old_post"], before)
            self.assertEqual(saved["old_categories"], [3])
            self.assertEqual(saved["mode"], "add_term")
            self.assertIsNone(saved["old_archive_card_rank"])
            self.assertEqual(saved["old_home_card_rank"], 1)
            self.assertEqual(saved["wordpress_writes"], 0)
            writer.assert_not_called()
            with self.assertRaisesRegex(PublishError, "overwrite"):
                m.snapshot()

    def test_new_taxonomy_only_post_and_public_archive_rank_one(self):
        before = guide()
        after = guide(categories=[3,22],modified="2026-11-21T10:59:00")
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(m, "BACKUP", Path(temp)/"original.json"):
            with patch.object(m, "checked_source", return_value=(22,before)), \
                 patch.object(m, "category_public_get", return_value=archive()), \
                 patch.object(m, "homepage_get", return_value=_homepage()):
                m.snapshot()
            with patch.object(m, "checked_source", return_value=(22,before)), \
                 patch.object(m, "category_public_get",
                              side_effect=[archive(), archive(guide_rank=1)]), \
                 patch.object(m, "homepage_get", return_value=_homepage()), \
                 patch.object(m, "guide_get", return_value=after), \
                 patch.object(m, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(m, "wp_request", return_value={"id":m.POST_ID}) as writer:
                out = StringIO()
                with contextlib.redirect_stdout(out):
                    m.apply()
            writer.assert_called_once()
            self.assertEqual(writer.call_args.kwargs["payload"], {"categories":[3,22]})
            self.assertIn("PUBLIC_SUPPLEMENTS_CATEGORY_PROMOTED", out.getvalue())
            self.assertTrue(m._same_post_other_than_category_and_timestamp(before,after))

    def test_all_other_original_categories_preserved_even_with_reordered_list(self):
        before = guide(categories=[7,3])
        after = guide(categories=[22,3,7],modified="2026-11-21T10:59:00")
        self.assertTrue(m._same_post_other_than_category_and_timestamp(before,after))
        self.assertEqual(sorted(after["categories"]), sorted([3,7,22]))

    def test_source_drift_before_post_is_absolute_blocker(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(m, "BACKUP", Path(temp)/"original.json"):
            with patch.object(m, "checked_source", return_value=(22,guide())), \
                 patch.object(m, "category_public_get", return_value=archive()), \
                 patch.object(m, "homepage_get", return_value=_homepage()):
                m.snapshot()
            with patch.object(m, "checked_source",
                              return_value=(22,guide(modified="2026-11-21T11:00:00"))), \
                 patch.object(m, "wp_request") as writer:
                with self.assertRaisesRegex(PublishError,"drift"):
                    m.apply()
                writer.assert_not_called()

    def test_timeout_must_never_trigger_second_post(self):
        after = guide(categories=[3,22],modified="2026-11-21T10:59:00")
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(m, "BACKUP", Path(temp)/"original.json"):
            with patch.object(m, "checked_source", return_value=(22,guide())), \
                 patch.object(m, "category_public_get", return_value=archive()), \
                 patch.object(m, "homepage_get", return_value=_homepage()):
                m.snapshot()
            with patch.object(m, "checked_source", return_value=(22,guide())), \
                 patch.object(m, "category_public_get",
                              side_effect=[archive(),archive(guide_rank=1)]), \
                 patch.object(m, "homepage_get", return_value=_homepage()), \
                 patch.object(m, "guide_get", return_value=after), \
                 patch.object(m, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(m, "wp_request", side_effect=PublishError("timeout")) as writer:
                m.apply()
                writer.assert_called_once()

    def test_no_false_deployment_when_archive_cache_stale_after_wp_update(self):
        after = guide(categories=[3,22],modified="2026-11-21T10:59:00")
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(m, "BACKUP", Path(temp)/"original.json"):
            with patch.object(m, "checked_source", return_value=(22,guide())), \
                 patch.object(m, "category_public_get", return_value=archive()), \
                 patch.object(m, "homepage_get", return_value=_homepage()):
                m.snapshot()
            with patch.object(m, "checked_source", return_value=(22,guide())), \
                 patch.object(m, "category_public_get", return_value=archive()), \
                 patch.object(m, "homepage_get", return_value=_homepage()), \
                 patch.object(m, "guide_get", return_value=after), \
                 patch.object(m, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(m, "wp_request", return_value={"id":m.POST_ID}) as writer, \
                 patch.object(m.time, "sleep", return_value=None):
                with self.assertRaisesRegex(PublishError, "not proven"):
                    m.apply()
                writer.assert_called_once()

    def test_release_workflow_uploads_rollback_before_one_post(self):
        wf = Path(".github/workflows/xfit-supplements-category-onepost.yml").read_text()
        self.assertIn("xfit_supplements_category_hub_onepost snapshot", wf)
        self.assertIn("xfit_supplements_category_hub_onepost apply", wf)
        self.assertIn("actions/upload-artifact@v4", wf)
        self.assertIn("if-no-files-found: error", wf)
        self.assertNotIn("schedule:", wf)
        self.assertNotIn("workflow_dispatch:", wf)


def _homepage():
    paths = ["/"+m.SLUG+"/"]+["/others-"+str(i)+"/" for i in range(1,12)]
    return ("<html><body>" + "".join(
        '<h3><a href="https://xfit.cz'+p+'">Post</a></h3>' for p in paths
    )+"</body></html>")


if __name__ == "__main__":
    unittest.main()
