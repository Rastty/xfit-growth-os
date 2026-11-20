"""Japanese exercise #9462 onepost must not overwrite unreviewed source."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.wp_publish import PublishError
from scripts import xfit_japanese_exercise_9462 as r


def legacy():
    return ("<p>" + "Japonské cvičení pro začátečníky obsahuje pohybové sestavy. " * 105 + "</p>"
            + "<!DOCTYPE html>" * 4
            + '<link rel="canonical" href="' + r.BAD_LINK + '">'
            + '<a href="' + r.BAD_LINK + '">Odkaz</a>'
            + '<a href="https://xfit.cz/ketomix">Keto</a>'
            + "".join("<p>" + sentence + "</p>" for sentence in r.OLD_SENTENCES))


def post(body=None, *, post_id=r.POST_ID, slug=r.SLUG, title=r.TITLE_RAW,
         status="publish", link=r.URL, modified=r.REVIEWED_MODIFIED_GMT,
         rendered=False, rendered_title="&#8211; Japonské cvičení na hubnutí: Objasňujeme základní principy"):
    return {"id": post_id, "slug": slug, "status": status, "link": link,
            "modified_gmt": modified, "title": ({"rendered": rendered_title} if rendered
                                                      else {"raw": title, "rendered": rendered_title}),
            "content": {"rendered" if rendered else "raw": legacy() if body is None else body}}


class JapaneseExerciseTests(unittest.TestCase):
    def test_readonly_diagnostic_never_mutates(self):
        import contextlib
        from io import StringIO
        output = StringIO()
        with patch.object(r, "remote", return_value=post()), \
                patch.object(r, "wp_request") as write, \
                contextlib.redirect_stdout(output):
            r.diagnose()
        result = json.loads(output.getvalue())
        self.assertEqual(result["state"], "READ_ONLY_AUTH_IDENTITY")
        self.assertTrue(result["old_source_matches"])
        self.assertTrue(result["title_matches"])
        self.assertEqual(result["remote_writes"], 0)
        write.assert_not_called()

    def test_revision_is_substantial_sourced_and_no_pseudo_science(self):
        body = r.revision()
        self.assertEqual(body.count(r.MARK), 1)
        self.assertEqual(body.count("min-height:48px"), 3)
        self.assertIn("není tajnou metodou", body)
        for url in r.TARGETS + r.SOURCES:
            self.assertIn('href="' + url + '"', body)
        for bad in ("<!DOCTYPE", "example.com", "ketomix", "<script", "<iframe", "5NM2022"):
            self.assertNotIn(bad, body)

    def test_reviewed_legacy_source_is_pinned(self):
        self.assertTrue(r.old_source(legacy()))
        self.assertEqual(r.classify(post())["mode"], "update")

    def test_strict_identity_timestamp_and_source_drift(self):
        changes = (
            {"post_id": 9463}, {"slug": "changed"}, {"title": "New headline"},
            {"rendered_title": "Changed visible title"},
            {"status": "draft"}, {"link": "https://example.org/" + r.SLUG + "/"},
            {"link": r.URL + "?from=bad"}, {"modified": "2026-11-20T20:00:00"},
            {"body": legacy().replace(r.BAD_LINK, "https://changed.test", 1)},
            {"body": legacy().replace("Harmonizace energie", "Opraveno")},
            {"body": legacy() + "5NM2022"}, {"body": legacy() + r.MARK},
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises(PublishError):
                r.classify(post(**change))

    def test_public_rendered_and_auth_raw_title_both_pinned(self):
        self.assertTrue(r.title_matches(post(), authenticated=True))
        self.assertTrue(r.title_matches(post(rendered=True), authenticated=False))
        self.assertFalse(r.title_matches(post(rendered_title="New"), authenticated=True))
        self.assertFalse(r.title_matches(post(title="New"), authenticated=True))

    def test_reviewed_body_missing_fails_before_mutation(self):
        with patch.object(r, "SOURCE", Path("/nonexistent")):
            with self.assertRaises(OSError):
                r.revision()

    def test_already_applied_has_no_repeat_write(self):
        done = post(r.revision(), modified="2026-11-20T20:01:00")
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(r, "BACKUP", Path(folder) / "snap.json"), \
                patch.object(r, "remote", return_value=done), \
                patch.object(r, "verify_public", return_value=True), \
                patch.object(r, "wp_request") as write:
            r.snapshot(); r.apply(); write.assert_not_called()

    def test_backup_before_one_post_with_exact_content_only_payload(self):
        initial = post()
        final = post(r.revision(), modified="2026-11-20T20:01:00")
        fingerprint = {"rendered_sha": r.sha(legacy()),
                       "modified_gmt": r.REVIEWED_MODIFIED_GMT}
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(r, "BACKUP", Path(folder) / "snap.json"), \
                patch.object(r, "old_public_fingerprint", return_value=fingerprint):
            with patch.object(r, "remote", return_value=initial):
                r.snapshot()
            saved = json.loads(r.BACKUP.read_text())
            self.assertEqual(saved["original_authenticated_post"], initial)
            self.assertEqual(saved["public_before"], fingerprint)
            self.assertEqual(saved["remote_writes"], 0)
            with patch.object(r, "remote", side_effect=[initial, final]), \
                    patch.object(r, "wp_request", return_value={"id": r.POST_ID}) as write, \
                    patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
                    patch.object(r, "verify_public", return_value=True):
                r.apply()
            write.assert_called_once_with("https://xfit.cz", "posts/9462",
                                          payload={"content": r.revision()})

    def test_concurrent_edit_prevents_post(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(r, "BACKUP", Path(folder) / "snap.json"), \
                patch.object(r, "old_public_fingerprint", return_value={}):
            with patch.object(r, "remote", return_value=post()):
                r.snapshot()
            with patch.object(r, "remote", return_value=post(modified="2026-11-20T20:03:00")), \
                    patch.object(r, "wp_request") as write:
                with self.assertRaises(PublishError):
                    r.apply()
                write.assert_not_called()

    def test_public_source_change_prevents_post(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(r, "BACKUP", Path(folder) / "snap.json"), \
                patch.object(r, "old_public_fingerprint", side_effect=[{"sha": "a"}, {"sha": "b"}]), \
                patch.object(r, "remote", return_value=post()), \
                patch.object(r, "wp_request") as write:
            r.snapshot()
            with self.assertRaises(PublishError):
                r.apply()
            write.assert_not_called()

    def test_immutable_backup_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(r, "BACKUP", Path(folder) / "snap.json"), \
                patch.object(r, "remote", return_value=post()), \
                patch.object(r, "old_public_fingerprint", return_value={}):
            r.snapshot()
            with self.assertRaises(PublishError):
                r.snapshot()

    def test_ambiguous_wp_timeout_never_retries_post(self):
        initial = post()
        after = post(r.revision(), modified="2026-11-20T20:01:00")
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(r, "BACKUP", Path(folder) / "snap.json"), \
                patch.object(r, "old_public_fingerprint", return_value={}):
            with patch.object(r, "remote", return_value=initial):
                r.snapshot()
            with patch.object(r, "remote", side_effect=[initial, after]), \
                    patch.object(r, "wp_request", side_effect=PublishError("timeout")) as write, \
                    patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
                    patch.object(r, "verify_public", return_value=True):
                r.apply()
            self.assertEqual(write.call_count, 1)

    def test_auth_success_public_unverified_never_claims_release(self):
        initial = post()
        after = post(r.revision(), modified="2026-11-20T20:01:00")
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(r, "BACKUP", Path(folder) / "snap.json"), \
                patch.object(r, "old_public_fingerprint", return_value={}):
            with patch.object(r, "remote", return_value=initial):
                r.snapshot()
            with patch.object(r, "remote", side_effect=[initial, after]), \
                    patch.object(r, "wp_request", return_value={"id": r.POST_ID}) as write, \
                    patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
                    patch.object(r, "verify_public", return_value=False):
                with self.assertRaises(PublishError):
                    r.apply()
            self.assertEqual(write.call_count, 1)


if __name__ == "__main__":
    unittest.main()
