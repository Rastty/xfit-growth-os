"""Two current monetizable advisers into natural supplement category, no duplicate posts."""
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import xfit_supplements_two_advisors_category as m
from scripts.wp_publish import PublishError


def source(approved, *, categories=None, modified="2026-11-21T11:00:00"):
    ident, slug, title = approved
    cards = "".join(
        '<article class="xfit-product-card"><a href="https://www.namaximum.cz/p/'
        + str(i) + '" data-xfit-product-id="' + str(i) +
        '" data-xfit-partner="namaximum">Ověřit</a></article>'
        for i in range(1, 7)
    )
    content = (
        '<p>Výběr doplňků je dobrovolný: nekupovat nic má někdy smysl.</p>' * 60
        + cards)
    return {
        "id": ident, "slug": slug, "status": "publish",
        "link": "https://xfit.cz/" + slug + "/",
        "sticky": False, "title": {"raw":title},
        "content":{"raw": content}, "excerpt":{"raw":"Poradce z katalogu."},
        "categories":[3] if categories is None else categories,
        "modified_gmt": modified,
    }


def category_html(*, include=False):
    guide_path = "/xfit-os-doplnky-pro-zacatecniky/"
    advisor_paths = ["/"+p[1]+"/" for p in m.PAGES]
    head = [guide_path]
    if include:
        head += [advisor_paths[1], advisor_paths[0]]
    rest = ["/legacy-supplement-"+str(i)+"/" for i in range(12)]
    paths = head + rest
    return ("<html><body><h1>Doplňky stravy</h1><main>" +
            "".join('<h3><a href="https://xfit.cz'+path+'">Článek</a></h3>'
                    for path in paths) +
            "</main><aside><p>Nejnovější příspěvky</p></aside></body></html>")


def home_html():
    paths = ["/xfit-os-doplnky-pro-zacatecniky/"] + [
        "/legacy-post-"+str(i)+"/" for i in range(1,12)
    ]
    return ("<html><body>" + "".join(
        '<h3><a href="https://xfit.cz'+path+'">Článek</a></h3>' for path in paths)
        + "</body></html>")


class TwoAdvisorsCategoryTests(unittest.TestCase):
    def test_authorized_ids_and_strict_article_structure(self):
        for approved in m.PAGES:
            self.assertEqual(m.page_identity(source(approved), approved)["id"],
                             approved[0])
            for alteration in (
                {"id":999}, {"slug":"wrong"}, {"status":"draft"},
                {"title":{"raw":"Another title"}},
                {"categories":[1,1]}, {"categories":[True]},
                {"content":{"raw":"short"}},
            ):
                with self.subTest(approved=approved,alteration=alteration), \
                     self.assertRaises(PublishError):
                    m.page_identity(dict(source(approved),**alteration), approved)
        with self.assertRaises(PublishError):
            m.source_get(1)

    def test_public_category_archive_positions_without_sidebar_pollution(self):
        before=m.positions(category_html())
        self.assertEqual(before["xfit-os-doplnky-pro-zacatecniky"],1)
        self.assertIsNone(before[m.PAGES[0][1]])
        self.assertIsNone(before[m.PAGES[1][1]])
        after=m.positions(category_html(include=True))
        self.assertEqual(after["xfit-os-doplnky-pro-zacatecniky"],1)
        self.assertEqual(after[m.PAGES[1][1]],2)
        self.assertEqual(after[m.PAGES[0][1]],3)
        with self.assertRaisesRegex(PublishError,"Wrong public category"):
            m.positions(category_html().replace("Doplňky stravy","Hubnutí"))

    def test_snapshot_full_sources_and_no_remote_mutations(self):
        before=[source(p) for p in m.PAGES]
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(m,"BACKUP",Path(temp)/"original.json"), \
             patch.object(m,"read_all",return_value=(44,before)), \
             patch.object(m,"category_public_get",return_value=category_html()), \
             patch.object(m,"homepage_get",return_value=home_html()), \
             patch.object(m,"wp_request") as writer:
            m.snapshot()
            saved=json.loads(m.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(saved["category_id"],44)
            self.assertEqual(saved["archive_before"][m.PAGES[0][1]],None)
            self.assertEqual([x["original_post"] for x in saved["before"]],before)
            self.assertEqual(saved["wordpress_writes"],0)
            writer.assert_not_called()
            with self.assertRaisesRegex(PublishError,"overwrite"):
                m.snapshot()

    def test_two_post_assignments_keep_all_commercial_bodies_and_categories(self):
        before=[source(p) for p in m.PAGES]
        after=[source(p,categories=[3,44],modified="2026-11-21T11:10:00")
               for p in m.PAGES]
        def remote_get(post_id):
            remote_get.count[post_id]=remote_get.count.get(post_id,0)+1
            return before[[x[0] for x in m.PAGES].index(post_id)] if remote_get.count[post_id]==1 \
                else after[[x[0] for x in m.PAGES].index(post_id)]
        remote_get.count={}
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(m,"BACKUP",Path(temp)/"original.json"):
            with patch.object(m,"read_all",return_value=(44,before)), \
                 patch.object(m,"category_public_get",return_value=category_html()), \
                 patch.object(m,"homepage_get",return_value=home_html()):
                m.snapshot()
            with patch.object(m,"read_all",side_effect=[(44,before),(44,after)]), \
                 patch.object(m,"source_get",side_effect=remote_get), \
                 patch.object(m,"category_public_get",
                              side_effect=[category_html(),category_html(include=True)]), \
                 patch.object(m,"homepage_get",return_value=home_html()), \
                 patch.object(m,"normalized_base",return_value="https://xfit.cz"), \
                 patch.object(m,"wp_request",return_value={"id":25455}) as writer:
                result=StringIO()
                with contextlib.redirect_stdout(result):
                    m.apply()
            self.assertEqual(writer.call_count,2)
            self.assertTrue(all(call.kwargs["payload"]=={"categories":[3,44]}
                                for call in writer.call_args_list))
            self.assertIn("PUBLIC_TWO_ADVISORS_IN_SUPPLEMENT_TOP3",result.getvalue())
            self.assertIn('"creatine_advisor_rank": 3',result.getvalue())
            self.assertIn('"whey_advisor_rank": 2',result.getvalue())

    def test_source_drift_before_batch_prevents_any_post(self):
        before=[source(p) for p in m.PAGES]
        changed=[source(m.PAGES[0],modified="2026-11-21T11:12:00"),
                 source(m.PAGES[1])]
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(m,"BACKUP",Path(temp)/"original.json"):
            with patch.object(m,"read_all",return_value=(44,before)), \
                 patch.object(m,"category_public_get",return_value=category_html()), \
                 patch.object(m,"homepage_get",return_value=home_html()):
                m.snapshot()
            with patch.object(m,"read_all",return_value=(44,changed)), \
                 patch.object(m,"wp_request") as writer:
                with self.assertRaisesRegex(PublishError,"Concurrent"):
                    m.apply()
            writer.assert_not_called()

    def test_timeout_after_first_post_does_not_repeat_and_get_verifies(self):
        before=[source(p) for p in m.PAGES]
        after=[source(p,categories=[3,44],modified="2026-11-21T11:10:00")
               for p in m.PAGES]
        get_counts={}
        def get(post_id):
            get_counts[post_id]=get_counts.get(post_id,0)+1
            idx=0 if post_id==m.PAGES[0][0] else 1
            return before[idx] if get_counts[post_id]==1 else after[idx]
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(m,"BACKUP",Path(temp)/"original.json"):
            with patch.object(m,"read_all",return_value=(44,before)), \
                 patch.object(m,"category_public_get",return_value=category_html()), \
                 patch.object(m,"homepage_get",return_value=home_html()):
                m.snapshot()
            with patch.object(m,"read_all",side_effect=[(44,before),(44,after)]), \
                 patch.object(m,"source_get",side_effect=get), \
                 patch.object(m,"category_public_get",
                              side_effect=[category_html(),category_html(include=True)]), \
                 patch.object(m,"homepage_get",return_value=home_html()), \
                 patch.object(m,"normalized_base",return_value="https://xfit.cz"), \
                 patch.object(m,"wp_request",side_effect=PublishError("timeout")) as writer:
                m.apply()
            self.assertEqual(writer.call_count,2)

    def test_workflow_requires_single_prewrite_backup_and_is_nonrecurring(self):
        y=Path(".github/workflows/xfit-supplements-two-advisors-onepost.yml").read_text()
        self.assertIn("xfit_supplements_two_advisors_category snapshot",y)
        self.assertIn("xfit_supplements_two_advisors_category apply",y)
        self.assertIn("if-no-files-found: error",y)
        self.assertNotIn("schedule:",y)
        self.assertNotIn("workflow_dispatch:",y)


if __name__=="__main__":
    unittest.main()
