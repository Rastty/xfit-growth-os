"""Reviewed SEO-visible Pilates 3660 -> existing mat guide, onepost no-repeat proof."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from scripts import xfit_pilates_mat_handoff_3660 as bridge
from scripts.wp_publish import PublishError


def sample_body():
    before = ("<h2>Pilates podle intenzity</h2>"
              "<p>Rozhodujte se podle zkušeností a konkrétní lekce.</p>" * 36)
    after = ("<h2>Časté otázky</h2>"
             "<p>Cvičení musí vyhovovat skutečnému prostoru doma.</p>" * 35)
    return before + "<p>" + bridge.OLD + "</p>" + after


def post(raw=None, modified="2026-11-21T09:00:00"):
    return {
        "id": bridge.POST_ID, "slug": bridge.SLUG, "status": "publish",
        "link": bridge.URL, "title": {"raw": bridge.NEW_TITLE},
        "excerpt": {"raw": "Pilates porovnání dvou typů lekcí."},
        "content": {"raw": sample_body() if raw is None else raw},
        "modified_gmt": modified,
    }


class PilatesMatBridgeTests(unittest.TestCase):
    def test_exact_url_and_related_existing_guide_no_new_content(self):
        self.assertEqual(bridge.POST_ID, 3660)
        self.assertEqual(bridge.TARGET, "https://xfit.cz/xfit-os-vyber-podlozky-na-cviceni/")
        self.assertIn("nemusíte kupovat", bridge.NEW)
        self.assertIn("nikoli srovnávač aktuálních cen", bridge.NEW)
        self.assertNotIn("a_aid", bridge.NEW)

    def test_transform_replaces_one_precise_stale_paragraph(self):
        raw = sample_body()
        new, mode = bridge.change_one_paragraph(raw)
        self.assertEqual(mode, "update")
        self.assertNotIn("Výběr vybavení připravujeme", new)
        self.assertEqual(new.count(bridge.TARGET), 1)
        self.assertEqual(new.count(bridge.MARKER), 1)
        self.assertEqual(len(bridge.links(new)), 1)
        prefix, suffix = raw.split("<p>" + bridge.OLD + "</p>")
        self.assertEqual(new, prefix + "<p>" + bridge.NEW + "</p>" + suffix)

    def test_exact_replay_is_noop(self):
        new, _ = bridge.change_one_paragraph(sample_body())
        result, mode = bridge.change_one_paragraph(new)
        self.assertEqual(result, new)
        self.assertEqual(mode, "already_applied")

    def test_rejects_changed_paragraph_marked_or_target_already_linked(self):
        raw = sample_body()
        cases = (
            raw.replace("produktové feedy", "nabídkové feedy"),
            raw.replace(bridge.OLD, "<strong>" + bridge.OLD + "</strong>"),
            raw.replace("<p>" + bridge.OLD + "</p>", "<p>Text o výběru.</p>"),
            raw + "<p>" + bridge.OLD + "</p>",
            raw + '<p><a href="' + bridge.TARGET + '">Další odkaz</a></p>',
        )
        for source in cases:
            with self.subTest(source=source[-90:]), self.assertRaises(PublishError):
                bridge.change_one_paragraph(source)

    def test_public_proof_requires_correct_h1_link_and_no_old_placeholder(self):
        new, _ = bridge.change_one_paragraph(sample_body())
        document = '<html><h1>' + bridge.NEW_TITLE + '</h1><main>' + new + '</main></html>'
        self.assertTrue(bridge.checked_public(bridge.URL, reader=lambda _: document))
        self.assertFalse(bridge.checked_public(
            bridge.URL, reader=lambda _: document.replace(bridge.TARGET, "https://xfit.cz/")))
        self.assertFalse(bridge.checked_public(
            bridge.URL, reader=lambda _: document.replace(
                bridge.NEW_TITLE, "Nějaký jiný článek")))
        self.assertFalse(bridge.checked_public(
            bridge.URL, reader=lambda _: document + "<p>" + bridge.OLD + "</p>"))
        target_page = '<h1>' + bridge.TARGET_TITLE + '</h1><p>Vybírejte podle pohybu.</p>'
        self.assertTrue(bridge.checked_public(bridge.TARGET, require_article=True,
                                              reader=lambda _: target_page))

    def test_backup_before_at_most_one_post_and_public_readback(self):
        source = post()
        new_body, _ = bridge.change_one_paragraph(source["content"]["raw"])
        updated = post(new_body, modified="2026-11-21T09:02:00")
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(bridge, "BACKUP", Path(folder) / "rollback.json"):
            with patch.object(bridge, "post_get", return_value=source), \
                 patch.object(bridge, "checked_public", return_value=True):
                bridge.snapshot()
            backup = json.loads(bridge.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(backup["original_raw"], source["content"]["raw"])
            self.assertEqual(backup["remote_writes"], 0)
            with patch.object(bridge, "post_get", side_effect=[source, updated]), \
                 patch.object(bridge, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(bridge, "wp_request", return_value={"id": 3660}) as write, \
                 patch.object(bridge, "checked_public", return_value=True):
                bridge.apply()
            write.assert_called_once()
            self.assertEqual(write.call_args.kwargs["payload"], {"content": new_body})

    def test_source_drift_after_backup_blocks_all_writes(self):
        source = post()
        drift = post(source["content"]["raw"] + "<p>Another writer updated this.</p>",
                     modified="2026-11-21T09:03:00")
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(bridge, "BACKUP", Path(folder) / "rollback.json"):
            with patch.object(bridge, "post_get", return_value=source), \
                 patch.object(bridge, "checked_public", return_value=True):
                bridge.snapshot()
            with patch.object(bridge, "post_get", return_value=drift), \
                 patch.object(bridge, "wp_request") as write:
                with self.assertRaisesRegex(PublishError, "source drift"):
                    bridge.apply()
            write.assert_not_called()

    def test_ambiguous_post_can_only_be_reconciled_by_readback(self):
        original = post()
        new_body, _ = bridge.change_one_paragraph(original["content"]["raw"])
        revised = post(new_body, modified="2026-11-21T09:04:00")
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(bridge, "BACKUP", Path(folder) / "rollback.json"):
            with patch.object(bridge, "post_get", return_value=original), \
                 patch.object(bridge, "checked_public", return_value=True):
                bridge.snapshot()
            with patch.object(bridge, "post_get", side_effect=[original, revised]), \
                 patch.object(bridge, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(bridge, "wp_request",
                              side_effect=PublishError("WordPress REST request failed (URLError)")) as write, \
                 patch.object(bridge, "checked_public", return_value=True):
                bridge.apply()
            write.assert_called_once()

    def test_no_blind_retry_when_post_outcome_not_reflected_in_source(self):
        original = post()
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(bridge, "BACKUP", Path(folder) / "rollback.json"):
            with patch.object(bridge, "post_get", return_value=original), \
                 patch.object(bridge, "checked_public", return_value=True):
                bridge.snapshot()
            with patch.object(bridge, "post_get", side_effect=[original, original]), \
                 patch.object(bridge, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(bridge, "wp_request", side_effect=PublishError("HTTP 503")) as write:
                with self.assertRaisesRegex(PublishError, "not confirmed"):
                    bridge.apply()
            write.assert_called_once()

    def test_exact_onepost_workflow_never_runs_on_unrelated_commit(self):
        wf = Path(".github/workflows/xfit-pilates-mat-onepost.yml").read_text(encoding="utf-8")
        self.assertIn("xfit_pilates_mat_handoff_3660 snapshot", wf)
        self.assertIn("xfit_pilates_mat_handoff_3660 apply", wf)
        self.assertIn("actions/upload-artifact@v4", wf)
        self.assertIn("if-no-files-found: error", wf)
        self.assertNotIn("content/ready/*.json", wf)
        self.assertNotIn("schedule:", wf)


if __name__ == "__main__":
    unittest.main()
