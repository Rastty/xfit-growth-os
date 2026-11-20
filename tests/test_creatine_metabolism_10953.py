"""Content-only onepost rescue must fail before writing on unknown source."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.wp_publish import PublishError
from scripts import xfit_creatine_metabolism_10953 as r


def damaged():
    # Exact structural/claim markers, enough text to test the source guard.
    return ("<p>" + "Kreatin je součástí svalů a energetického systému. " * 120 + "</p>"
            + "<!DOCTYPE html>" * 4
            + '<link rel="canonical" href="' + r.BAD_LINK + '">'
            + '<a href="' + r.BAD_LINK + '">článek</a>'
            + '<script src="script.js"></script><link href="styles.css">'
            + "".join("<p>" + sentence + "</p>" for sentence in r.OLD_SENTENCES))


def post(body=None, *, post_id=r.POST_ID, slug=r.SLUG, title=r.TITLE,
         status="publish", link=r.URL, modified=r.REVIEWED_MODIFIED_GMT,
         rendered=False):
    return {"id": post_id, "slug": slug, "title": {"raw": title},
            "status": status, "link": link, "modified_gmt": modified,
            "content": {"rendered" if rendered else "raw": damaged() if body is None else body}}


class CreatineMetabolismTests(unittest.TestCase):
    def test_real_public_source_matches_reviewed_four_document_guard(self):
        # Tests use fixtures; the real live source was separately checked by GET.
        self.assertTrue(r.old_source(damaged()))

    def test_science_depth_navigation_and_canonical_safety(self):
        source = r.revision()
        self.assertIn("Nejde o spalovač tuku", source)
        self.assertEqual(source.count(r.MARK), 1)
        self.assertEqual(source.count("min-height:48px"), 3)
        for link in r.TARGETS + r.SOURCES:
            self.assertIn('href="' + link + '"', source)
        for unsafe in ("<!DOCTYPE", "<html", "<script", "<iframe", "example.com", "5NM2022"):
            self.assertNotIn(unsafe, source)

    def test_exact_article_and_reviewed_timestamp_only(self):
        for change in (
            {"post_id": 10954}, {"slug": "changed"}, {"title": "Nový článek"},
            {"status": "draft"}, {"link": "https://example.com/" + r.SLUG + "/"},
            {"link": r.URL + "?test=1"}, {"modified": "2026-11-20T18:38:53"},
            {"body": damaged().replace("script.js", "app.js")},
            {"body": damaged().replace(r.BAD_LINK, "https://example.org", 1)},
            {"body": damaged() + "5NM2022"},
            {"body": damaged() + r.MARK},
        ):
            with self.subTest(change=change), self.assertRaises(PublishError):
                r.classify(post(**change))

    def test_already_applied_is_no_write_even_with_new_timestamp(self):
        after = post(r.revision(), modified="2026-11-20T19:01:00")
        self.assertEqual(r.classify(after)["mode"], "already_applied")
        with tempfile.TemporaryDirectory() as path, \
                patch.object(r, "BACKUP", Path(path) / "snapshot.json"), \
                patch.object(r, "remote", return_value=after), \
                patch.object(r, "verify_public", return_value=True), \
                patch.object(r, "wp_request") as request:
            r.snapshot()
            r.apply()
            request.assert_not_called()

    def test_legacy_source_and_public_backup_before_one_post(self):
        baseline = post()
        final = post(r.revision(), modified="2026-11-20T19:01:00")
        stamp = {"rendered_sha": r.sha(damaged()), "modified_gmt": r.REVIEWED_MODIFIED_GMT}
        with tempfile.TemporaryDirectory() as path, \
                patch.object(r, "BACKUP", Path(path) / "snapshot.json"), \
                patch.object(r, "old_public_fingerprint", return_value=stamp):
            with patch.object(r, "remote", return_value=baseline):
                r.snapshot()
            backup = json.loads(r.BACKUP.read_text())
            self.assertEqual(backup["original_authenticated_post"], baseline)
            self.assertEqual(backup["public_before"], stamp)
            with patch.object(r, "remote", side_effect=[baseline, final]), \
                    patch.object(r, "wp_request", return_value={"id": r.POST_ID}) as request, \
                    patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
                    patch.object(r, "verify_public", return_value=True):
                r.apply()
            request.assert_called_once_with("https://xfit.cz", "posts/10953",
                                            payload={"content": r.revision()})

    def test_concurrent_edited_timestamp_blocks_any_write(self):
        before = post()
        stamp = {"rendered_sha": "old", "modified_gmt": r.REVIEWED_MODIFIED_GMT}
        with tempfile.TemporaryDirectory() as path, \
                patch.object(r, "BACKUP", Path(path) / "snapshot.json"), \
                patch.object(r, "old_public_fingerprint", return_value=stamp):
            with patch.object(r, "remote", return_value=before):
                r.snapshot()
            with patch.object(r, "remote", return_value=post(modified="2026-11-20T19:12:00")), \
                    patch.object(r, "wp_request") as request:
                with self.assertRaises(PublishError):
                    r.apply()
                request.assert_not_called()

    def test_public_drift_blocks_any_write(self):
        stamp = {"rendered_sha": "old", "modified_gmt": r.REVIEWED_MODIFIED_GMT}
        with tempfile.TemporaryDirectory() as path, \
                patch.object(r, "BACKUP", Path(path) / "snapshot.json"), \
                patch.object(r, "old_public_fingerprint", side_effect=[stamp, {**stamp, "rendered_sha": "changed"}]), \
                patch.object(r, "remote", return_value=post()), \
                patch.object(r, "wp_request") as request:
            r.snapshot()
            with self.assertRaises(PublishError):
                r.apply()
            request.assert_not_called()

    def test_backup_never_overwritten(self):
        with tempfile.TemporaryDirectory() as path, \
                patch.object(r, "BACKUP", Path(path) / "snapshot.json"), \
                patch.object(r, "remote", return_value=post()), \
                patch.object(r, "old_public_fingerprint", return_value={}):
            r.snapshot()
            with self.assertRaises(PublishError):
                r.snapshot()

    def test_uncertain_wp_response_does_not_repeat_post(self):
        before = post()
        after = post(r.revision(), modified="2026-11-20T19:01:00")
        with tempfile.TemporaryDirectory() as path, \
                patch.object(r, "BACKUP", Path(path) / "snapshot.json"), \
                patch.object(r, "old_public_fingerprint", return_value={}):
            with patch.object(r, "remote", return_value=before):
                r.snapshot()
            with patch.object(r, "remote", side_effect=[before, after]), \
                    patch.object(r, "wp_request", side_effect=PublishError("timeout")) as request, \
                    patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
                    patch.object(r, "verify_public", return_value=True):
                r.apply()
            self.assertEqual(request.call_count, 1)

    def test_auth_success_public_failure_is_not_reported_as_shipped(self):
        before = post()
        after = post(r.revision(), modified="2026-11-20T19:01:00")
        with tempfile.TemporaryDirectory() as path, \
                patch.object(r, "BACKUP", Path(path) / "snapshot.json"), \
                patch.object(r, "old_public_fingerprint", return_value={}):
            with patch.object(r, "remote", return_value=before):
                r.snapshot()
            with patch.object(r, "remote", side_effect=[before, after]), \
                    patch.object(r, "wp_request", return_value={"id": r.POST_ID}) as request, \
                    patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
                    patch.object(r, "verify_public", return_value=False):
                with self.assertRaises(PublishError):
                    r.apply()
            self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
