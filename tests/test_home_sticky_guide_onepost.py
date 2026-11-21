"""No-content-mutation and public-home confirmation of sticky reader-first guide."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import xfit_home_sticky_guide_onepost as m
from scripts.wp_publish import PublishError


def post(sticky=False, modified="2026-11-10T12:00:00"):
    return {
        "id": m.POST_ID, "slug": m.SLUG, "status": "publish",
        "link": m.URL, "sticky": sticky,
        "title": {"raw": m.TITLE},
        "content": {"raw": ("<p>Začátečník nekupuje hned všechny doplňky.</p>" * 40 +
                            '<a href="https://xfit.cz/xfit-os-kreatin-nebo-protein/">Průvodce</a>')},
        "excerpt": {"raw": "Výběr doplňků bez marketingu."},
        "modified_gmt": modified,
    }


def home(*, guide_rank=9):
    paths = ["/xfit-os-kreatin-poradce/"] + [
        f"/modelovy-testovaci-clanek-{i}/" for i in range(1, 13)
    ]
    if guide_rank is not None:
        paths.insert(guide_rank - 1, "/" + m.SLUG + "/")
    return "<html><body><main>" + "".join(
        '<h3><a href="https://xfit.cz' + path + '">Článek</a></h3>'
        for path in paths
    ) + "</main></body></html>"


class StickyGuideOnepostTests(unittest.TestCase):
    def test_exact_existing_guide_identity_and_body(self):
        self.assertEqual(m.selected(post())["id"], m.POST_ID)
        for change in (
            {"id": 1}, {"slug": "other"}, {"sticky": 1}, {"status": "draft"},
            {"link": "https://elsewhere.example/"}, {"title": {"raw": "Wrong"}},
            {"content": {"raw": "too short"}},
        ):
            value = post()
            value.update(change)
            with self.subTest(change=change), self.assertRaises(PublishError):
                m.selected(value)

    def test_sticky_inventory_one_owned_or_empty_only(self):
        self.assertEqual(m.sticky_ids([]), [])
        self.assertEqual(m.sticky_ids([{"id":m.POST_ID,"sticky":True}]), [m.POST_ID])
        for bad in ([{"id":1,"sticky":False}], [{"id":1,"sticky":1}],
                    [{"id":m.POST_ID,"sticky":True}]*2, ["broken"]):
            with self.subTest(bad=bad), self.assertRaises(PublishError):
                m.sticky_ids(bad)

    def test_home_card_ranks_real_headings_not_sidebar_nonheadings(self):
        self.assertEqual(m.card_rank(home(guide_rank=9)), 9)
        self.assertEqual(m.card_rank(home(guide_rank=1)), 1)
        self.assertIsNone(m.card_rank(home(guide_rank=None)))
        self.assertEqual(m.card_rank(
            home(guide_rank=None).replace("</main>",
                 '<div><a href="' + m.URL + '">Side panel</a></div></main>')), None)

    def test_snapshot_full_backup_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m, "BACKUP", Path(tmp)/"original.json"), \
             patch.object(m, "source_get", return_value=post()), \
             patch.object(m, "sticky_list", return_value=[]), \
             patch.object(m, "homepage_get", return_value=home()):
            m.snapshot()
            backed = json.loads(m.BACKUP.read_text(encoding="utf-8"))
            self.assertFalse(backed["before"]["sticky"])
            self.assertIn("nekupuje", backed["before"]["content"]["raw"])
            self.assertEqual(backed["before_home_card_rank"], 9)
            self.assertEqual(backed["wordpress_writes"], 0)
            with self.assertRaisesRegex(PublishError, "overwrite"):
                m.snapshot()

    def test_one_other_sticky_is_backed_up_not_deleted(self):
        other = {"id": 99, "sticky": True}
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m, "BACKUP", Path(tmp)/"original.json"), \
             patch.object(m, "source_get", return_value=post()), \
             patch.object(m, "sticky_list", return_value=[other]), \
             patch.object(m, "homepage_get", return_value=home()):
            m.snapshot()
            saved = json.loads(m.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(saved["previous_sticky_ids"], [99])
            self.assertEqual(saved["before_home_card_rank"], 9)
            self.assertEqual(saved["wordpress_writes"], 0)

    def test_four_existing_stickies_block_before_backup(self):
        other = [{"id": i, "sticky": True} for i in (1, 2, 3, 4)]
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m, "BACKUP", Path(tmp)/"original.json"), \
             patch.object(m, "source_get", return_value=post()), \
             patch.object(m, "sticky_list", return_value=other):
            with self.assertRaisesRegex(PublishError, "Too many"):
                m.snapshot()
            self.assertFalse(m.BACKUP.exists())

    def test_one_post_changes_only_sticky_and_home_rank(self):
        before = post()
        other = {"id": 928, "sticky": True}
        after = post(sticky=True, modified="2026-11-21T11:00:00")
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m, "BACKUP", Path(tmp)/"original.json"):
            with patch.object(m, "source_get", return_value=before), \
                 patch.object(m, "sticky_list", return_value=[other]), \
                 patch.object(m, "homepage_get", return_value=home(guide_rank=9)):
                m.snapshot()
            with patch.object(m, "source_get", side_effect=[before, after]), \
                 patch.object(m, "sticky_list", side_effect=[[other],[other,{"id":m.POST_ID,"sticky":True}]]), \
                 patch.object(m, "homepage_get",
                              side_effect=[home(guide_rank=9),home(guide_rank=1)]), \
                 patch.object(m, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(m, "wp_request", return_value={"id":m.POST_ID}) as writer:
                m.apply()
            writer.assert_called_once()
            self.assertEqual(writer.call_args.kwargs["payload"], {"sticky": True})

    def test_timeout_one_post_can_be_reconciled_but_never_retried(self):
        before = post()
        after = post(sticky=True, modified="2026-11-21T11:00:00")
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m, "BACKUP", Path(tmp)/"original.json"):
            with patch.object(m, "source_get", return_value=before), \
                 patch.object(m, "sticky_list", return_value=[]), \
                 patch.object(m, "homepage_get", return_value=home(guide_rank=9)):
                m.snapshot()
            with patch.object(m, "source_get", side_effect=[before, after]), \
                 patch.object(m, "sticky_list", side_effect=[[],[{"id":m.POST_ID,"sticky":True}]]), \
                 patch.object(m, "homepage_get",
                              side_effect=[home(guide_rank=9),home(guide_rank=1)]), \
                 patch.object(m, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(m, "wp_request", side_effect=PublishError("timeout")) as writer:
                m.apply()
            writer.assert_called_once()

    def test_editor_drift_prevents_post(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m, "BACKUP", Path(tmp)/"original.json"):
            with patch.object(m, "source_get", return_value=post()), \
                 patch.object(m, "sticky_list", return_value=[]), \
                 patch.object(m, "homepage_get", return_value=home()):
                m.snapshot()
            with patch.object(m, "source_get", return_value=post(modified="2026-11-21T11:00:00")), \
                 patch.object(m, "sticky_list", return_value=[]), \
                 patch.object(m, "wp_request") as writer:
                with self.assertRaisesRegex(PublishError, "drift"):
                    m.apply()
                writer.assert_not_called()

    def test_sticky_flag_without_home_promotion_not_claimed(self):
        before = post()
        after = post(sticky=True)
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m, "BACKUP", Path(tmp)/"original.json"):
            with patch.object(m, "source_get", return_value=before), \
                 patch.object(m, "sticky_list", return_value=[]), \
                 patch.object(m, "homepage_get", return_value=home()):
                m.snapshot()
            with patch.object(m, "source_get", side_effect=[before, after]), \
                 patch.object(m, "sticky_list", side_effect=[[],[{"id":m.POST_ID,"sticky":True}]]), \
                 patch.object(m, "homepage_get", return_value=home()), \
                 patch.object(m, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(m, "wp_request", return_value={"id":m.POST_ID}) as writer:
                with self.assertRaisesRegex(PublishError, "not proven"):
                    m.apply()
            writer.assert_called_once()

    def test_get_only_diagnostic_observes_source_and_public_without_post(self):
        import contextlib
        from io import StringIO
        out = StringIO()
        with patch.object(m, "source_get", return_value=post()), \
             patch.object(m, "sticky_list", return_value=[]), \
             patch.object(m, "homepage_get", return_value=home()), \
             patch.object(m, "wp_request") as writer, \
             contextlib.redirect_stdout(out):
            report = m.diagnose_readonly()
        self.assertEqual(report["wordpress_writes"], 0)
        self.assertEqual(report["post_attempts"], 0)
        self.assertEqual(report["homepage"]["guide_rank"], 9)
        self.assertFalse(report["source"]["sticky_is_true"])
        self.assertTrue(report["source"]["title_matches"])
        self.assertEqual(report["sticky_inventory"]["count"], 0)
        writer.assert_not_called()
        self.assertNotIn("Začátečník nekupuje", out.getvalue())

    def test_workflow_immutable_backup_and_no_auto_repeat(self):
        text = Path(".github/workflows/xfit-home-sticky-guide-onepost.yml").read_text(encoding="utf-8")
        self.assertIn("xfit_home_sticky_guide_onepost snapshot", text)
        self.assertIn("xfit_home_sticky_guide_onepost apply", text)
        self.assertIn("if-no-files-found: error", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("workflow_dispatch:", text)


if __name__ == "__main__":
    unittest.main()
