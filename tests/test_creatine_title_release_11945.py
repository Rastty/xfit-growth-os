"""Single-post title-only WordPress contract; never retry uncertain writes."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import xfit_creatine_title_release_11945 as title
from scripts.wp_publish import PublishError


BODY = ('<p>Může kreatin pomoci nabrat svaly?</p>' +
        '<p>Jak kreatin souvisí se silou a růstem svalů.</p>' * 180 +
        '<h2>Zdroje, omezení a redakční metodika</h2>' +
        '<p>https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/</p>')


def post(name=title.OLD_TITLE, body=BODY, excerpt="", **changes):
    obj = {"id": title.POST_ID, "slug": title.SLUG,
           "link": title.URL, "status": "publish",
           "title": {"raw": name}, "content": {"raw": body},
           "excerpt": {"raw": excerpt}}
    obj.update(changes)
    return obj


class CreatineTitleReleaseTests(unittest.TestCase):
    def test_exact_post_and_clean_revision_required(self):
        self.assertTrue(title.classify(post())["needs_write"])
        self.assertFalse(title.classify(post(title.NEW_TITLE))["needs_write"])
        bad_posts = (
            post(id=11944), post(status="draft"), post(slug="other"),
            post(link="https://xfit.cz/other/"),
            post(name="Different SEO headline"),
            post(body="<p>Short page</p>"),
            post(body=BODY + "<!DOCTYPE html><html>"),
            post(body=BODY + "5NM2022"),
            post(excerpt=None),
        )
        for bad in bad_posts:
            with self.subTest(post=bad["id"]):
                with self.assertRaises(PublishError):
                    title.classify(bad)

    def test_snapshot_writes_local_backup_only(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "before.json"
            with patch.object(title, "BACKUP", file), \
                 patch.object(title, "get_post", return_value=post()), \
                 patch.object(title, "wp_request") as writer:
                title.snapshot()
                data = json.loads(file.read_text(encoding="utf-8"))
                self.assertEqual(data["original"]["title"], title.OLD_TITLE)
                self.assertEqual(data["original"]["content_sha256"], title.sha(BODY))
                self.assertEqual(data["remote_writes"], 0)
                self.assertNotIn(BODY, str(data))
                writer.assert_not_called()
                with self.assertRaises(PublishError):
                    title.snapshot()

    def test_one_title_write_only_with_public_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "before.json"
            with patch.object(title, "BACKUP", file), \
                 patch.object(title, "get_post", side_effect=[
                     post(), post(), post(title.NEW_TITLE)]), \
                 patch.object(title, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(title, "wp_request", return_value={
                     "id": 11945, "status": "publish"}) as writer, \
                 patch.object(title, "public_title_verified", return_value=True):
                title.snapshot()
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    title.apply()
                writer.assert_called_once_with(
                    "https://xfit.cz", "posts/11945",
                    payload={"title": title.NEW_TITLE})
                self.assertIn('"state": "PUBLIC_VERIFIED"', output.getvalue())

    def test_uncertain_post_never_repeated(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "before.json"
            with patch.object(title, "BACKUP", file), \
                 patch.object(title, "get_post", side_effect=[
                     post(), post(), post(title.NEW_TITLE)]), \
                 patch.object(title, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(title, "wp_request", side_effect=PublishError("503")) as writer, \
                 patch.object(title, "public_title_verified", return_value=True):
                title.snapshot()
                title.apply()
                writer.assert_called_once()

    def test_concurrent_edit_aborts_before_write(self):
        for changed in (post(body=BODY + "<p>new sentence</p>"),
                        post(excerpt="new excerpt"), post(title.NEW_TITLE)):
            with self.subTest(title=changed["title"]):
                with tempfile.TemporaryDirectory() as directory:
                    with patch.object(title, "BACKUP", Path(directory) / "b.json"), \
                         patch.object(title, "get_post", side_effect=[post(), changed]), \
                         patch.object(title, "wp_request") as writer:
                        title.snapshot()
                        with self.assertRaises(PublishError):
                            title.apply()
                        writer.assert_not_called()

    def test_already_applied_never_posts(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(title, "BACKUP", Path(directory) / "b.json"), \
                 patch.object(title, "get_post", return_value=post(title.NEW_TITLE)), \
                 patch.object(title, "wp_request") as writer, \
                 patch.object(title, "public_title_verified", return_value=True):
                title.snapshot()
                title.apply()
                writer.assert_not_called()

    def test_verify_command_read_only(self):
        with patch.object(title, "get_post", return_value=post(title.NEW_TITLE)), \
             patch.object(title, "wp_request") as writer, \
             patch.object(title, "public_title_verified", return_value=True):
            title.verify_only()
            writer.assert_not_called()

    def test_public_h1_not_meta_or_other_heading(self):
        expected = title.NEW_TITLE
        self.assertTrue(title.public_title_verified(
            reader=lambda _url: "<html><h1>" + expected + "</h1></html>"))
        for html in ("<title>" + expected + "</title><h1>Old</h1>",
                     "<h1>Old</h1>",
                     "<h1>" + expected + "</h1><h1>another</h1>"):
            self.assertFalse(title.public_title_verified(reader=lambda _url: html))


if __name__ == "__main__":
    unittest.main()
