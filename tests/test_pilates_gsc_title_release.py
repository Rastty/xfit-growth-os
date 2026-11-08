"""Regression tests for GSC source-backed, title-only WP 3660 release."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import xfit_pilates_gsc_title_release as title
from scripts.wp_publish import PublishError

BODY = ("<p><strong>Rozdíl mezi klasickým pilates a power pilates</strong>"
        " se liší tempem a vedením.</p>"
        + "<p>Užitečné informace o cvičení a vhodnosti lekce.</p>" * 80
        + '<p><a href="https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/">'
          "Navazující redakční průvodce</a></p>")
EXCERPT = "Klasické pilates vs. power pilates: tempo a náročnost."


def post(t=title.OLD_TITLE, body=BODY, excerpt=EXCERPT, **changes):
    p = {"id": 3660, "slug": title.SLUG, "link": title.URL,
         "status": "publish", "title": {"raw": t},
         "excerpt": {"raw": excerpt}, "content": {"raw": body}}
    p.update(changes)
    return p


class SingleTitleReleaseTests(unittest.TestCase):
    def test_preflight_requires_one_exact_article_and_title_pair(self):
        before = title.classify(post())
        self.assertEqual(before["post_id"], 3660)
        self.assertTrue(before["write_needed"])
        self.assertEqual(before["old_title"], title.OLD_TITLE)
        self.assertFalse(title.classify(post(title.NEW_TITLE))["write_needed"])
        for bad in (post(id=3661), post(status="draft"),
                    post(link="https://xfit.cz/other/"),
                    post(slug="other"),
                    post(t="Completely different editorial title"),
                    post(body=BODY.replace("Rozdíl mezi klasickým pilates a power pilates", "")),
                    post(body="<p>Short</p>")):
            with self.subTest(variant=str(bad.get("id")) + str(bad.get("slug"))):
                with self.assertRaises(PublishError):
                    title.classify(bad)

    def test_snapshot_is_immutable_and_never_posts(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "rollback.json"
            with patch.object(title, "BACKUP", dest), \
                 patch.object(title, "get_post", return_value=post()), \
                 patch.object(title, "wp_request") as writer:
                title.snapshot()
                report = json.loads(dest.read_text(encoding="utf-8"))
                self.assertEqual(report["source_run"], 42470121265)
                self.assertEqual(report["original"]["content_sha256"], title.sha(BODY))
                self.assertEqual(report["remote_writes"], 0)
                self.assertNotIn(BODY, str(report))
                writer.assert_not_called()
                with self.assertRaises(PublishError):
                    title.snapshot()

    def test_single_title_only_post_with_public_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "rollback.json"
            with patch.object(title, "BACKUP", dest), \
                 patch.object(title, "get_post", side_effect=[
                     post(), post(), post(title.NEW_TITLE)
                 ]), \
                 patch.object(title, "wp_request", return_value={
                     "id": 3660, "status": "publish"
                 }) as writer, \
                 patch.object(title, "normalized_base",
                              return_value="https://xfit.cz"), \
                 patch.object(title, "public_title_verified",
                              return_value=True) as public:
                title.snapshot()
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    title.apply()
                writer.assert_called_once_with(
                    "https://xfit.cz", "posts/3660",
                    payload={"title": title.NEW_TITLE})
                public.assert_called_once_with()
                self.assertIn('"state": "PUBLIC_VERIFIED"', output.getvalue())
                self.assertIn('"existing_html_preserved": true', output.getvalue())

    def test_uncertain_post_may_have_saved_title_and_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "rollback.json"
            with patch.object(title, "BACKUP", dest), \
                 patch.object(title, "get_post", side_effect=[
                     post(), post(), post(title.NEW_TITLE)
                 ]), \
                 patch.object(title, "wp_request",
                              side_effect=PublishError("HTTP 503")) as writer, \
                 patch.object(title, "normalized_base",
                              return_value="https://xfit.cz"), \
                 patch.object(title, "public_title_verified", return_value=True):
                title.snapshot()
                title.apply()
                self.assertEqual(writer.call_count, 1)

    def test_failed_post_still_old_never_blind_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "rollback.json"
            with patch.object(title, "BACKUP", dest), \
                 patch.object(title, "get_post", return_value=post()), \
                 patch.object(title, "wp_request",
                              side_effect=PublishError("HTTP 503")) as writer, \
                 patch.object(title, "normalized_base",
                              return_value="https://xfit.cz"), \
                 patch.object(title, "public_title_verified") as public:
                title.snapshot()
                with self.assertRaises(PublishError):
                    title.apply()
                self.assertEqual(writer.call_count, 1)
                public.assert_not_called()

    def test_concurrent_content_or_excerpt_edit_blocks_before_post(self):
        for varied in (post(body=BODY+"<p>New sentence</p>"),
                       post(excerpt="Changed excerpt"),
                       post(t=title.NEW_TITLE)):
            with self.subTest(changed=str(varied["title"])):
                with tempfile.TemporaryDirectory() as directory:
                    dest = Path(directory) / "rollback.json"
                    with patch.object(title, "BACKUP", dest), \
                         patch.object(title, "get_post", side_effect=[
                             post(), varied
                         ]), \
                         patch.object(title, "wp_request") as writer:
                        title.snapshot()
                        with self.assertRaises(PublishError):
                            title.apply()
                        writer.assert_not_called()

    def test_already_applied_does_not_modify_wordpress(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "rollback.json"
            with patch.object(title, "BACKUP", dest), \
                 patch.object(title, "get_post", return_value=post(title.NEW_TITLE)), \
                 patch.object(title, "wp_request") as writer, \
                 patch.object(title, "public_title_verified", return_value=True):
                title.snapshot()
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    title.apply()
                writer.assert_not_called()
                self.assertIn("ALREADY_APPLIED_NO_WRITE", output.getvalue())

    def test_only_exact_visible_public_h1_counts(self):
        valid = "<html><h1>Co je <strong>power pilates?</strong> Rozdíl oproti klasickému pilates</h1></html>"
        self.assertTrue(title.public_title_verified(reader=lambda url: valid))
        for bad in (
            "<html><title>" + title.NEW_TITLE + "</title><h1>Starý název</h1></html>",
            "<html><h1>Wrong article</h1></html>",
            "<html><h1>" + title.NEW_TITLE + "</h1><h1>Another title</h1></html>",
        ):
            self.assertFalse(title.public_title_verified(reader=lambda url: bad))


if __name__ == "__main__":
    unittest.main()
