"""Single-post legacy creatine SEO link release must be reversible and idempotent."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import xfit_legacy_creatine_handoff_release as release
from scripts.wp_publish import PublishError


def example(*, body=None, post_id=release.POST_ID, slug=release.SLUG,
            status="publish", link=release.URL, modified="2026-11-09T14:30:00"):
    if body is None:
        body = "<h2>Ověřený starší článek</h2>" + (
            "<p>Jak lze kombinovat kreatin s dalšími běžnými doplňky a cvičením.</p>" * 42
        )
    return {
        "id": post_id, "slug": slug, "status": status, "link": link,
        "title": {"raw": "Nejlepší způsoby, jak kombinovat kreatin"},
        "content": {"raw": body}, "modified_gmt": modified,
    }


class LegacyCreatineHandoffTests(unittest.TestCase):
    def test_one_safe_paragraph_preserves_entire_legacy_source(self):
        old = example()
        state = release.prepare(old)
        self.assertEqual(state["state"], "update")
        self.assertTrue(state["after"].startswith(state["before"] + "\n"))
        self.assertEqual(state["after"].count(release.MARK), 1)
        self.assertEqual(state["after"].count(release.TARGET), 1)
        self.assertIn(release.TARGET, release.hrefs(state["after"]))
        self.assertNotIn(release.TARGET, release.hrefs(state["before"]))
        self.assertIn("nemusíte nic kupovat", state["after"])

    def test_second_run_is_no_write_if_exact_link_already_present(self):
        original = release.prepare(example())
        actual = example(body=original["after"])
        state = release.prepare(actual)
        self.assertEqual(state["state"], "already_linked")
        self.assertEqual(state["after"], state["before"])

    def test_printed_url_does_not_count_as_an_html_link(self):
        post = example(body=example()["content"]["raw"] +
                       "<p>" + release.TARGET + "</p>")
        state = release.prepare(post)
        self.assertEqual(state["state"], "update")

    def test_wrong_identity_and_short_source_cannot_be_published(self):
        for changed in (
            {"id": release.POST_ID + 1},
            {"slug": "wrong-slug"},
            {"status": "draft"},
            {"link": "https://other.example/" + release.SLUG + "/"},
            {"link": "http://xfit.cz/" + release.SLUG + "/"},
            {"content": {"raw": "<p>Short legacy source</p>"}},
            {"title": {"raw": "Nesouvisející článek"}},
            {"modified_gmt": ""},
        ):
            with self.subTest(changed=changed):
                p = example()
                p.update(changed)
                with self.assertRaises(PublishError):
                    release.prepare(p)

    def test_public_verification_needs_exact_anchor_and_visible_guidance(self):
        body = release.PARAGRAPH
        self.assertTrue(release.public_verified(reader=lambda _: body))
        self.assertFalse(release.public_verified(reader=lambda _: body.replace(
            'href="' + release.TARGET + '"', 'href="https://xfit.cz/other/"'
        )))
        self.assertFalse(release.public_verified(reader=lambda _: body.replace(
            release.VISIBLE, "Nesouvisející text"
        )))

    def test_prewrite_artifact_then_exact_one_post_and_public_proof(self):
        source = example()
        updated = example(body=release.prepare(source)["after"],
                          modified="2026-11-09T15:15:00")
        with tempfile.TemporaryDirectory() as root, patch.object(
                release, "BACKUP", Path(root) / "backup.json"):
            with patch.object(release, "remote", return_value=source):
                release.snapshot()
            manifest = json.loads(release.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(manifest["original_raw"], source["content"]["raw"])
            self.assertEqual(manifest["remote_writes"], 0)
            with patch.object(release, "remote", side_effect=[source, updated]), \
                 patch.object(release, "normalized_base",
                              return_value="https://xfit.cz"), \
                 patch.object(release, "wp_request",
                              return_value={"id": release.POST_ID, "status": "publish"}) as writer, \
                 patch.object(release, "public_verified", return_value=True) as public:
                release.apply()
            writer.assert_called_once()
            self.assertEqual(writer.call_args.kwargs["payload"],
                             {"content": updated["content"]["raw"]})
            public.assert_called_once_with()

    def test_drift_after_snapshot_blocks_every_wordpress_post(self):
        source = example()
        drifted = example(body=source["content"]["raw"] + "<p>Late editor edit.</p>")
        with tempfile.TemporaryDirectory() as root, patch.object(
                release, "BACKUP", Path(root) / "backup.json"):
            with patch.object(release, "remote", return_value=source):
                release.snapshot()
            with patch.object(release, "remote", return_value=drifted), \
                 patch.object(release, "wp_request") as writer:
                with self.assertRaises(PublishError):
                    release.apply()
            writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
