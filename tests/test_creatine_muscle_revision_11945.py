import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.wp_publish import PublishError
from scripts import xfit_creatine_muscle_revision_11945 as revision

OLD = ('<p><!DOCTYPE html><html><head></head><body>Vložený dokument.</body></html></p>'
       * 50)


def post(raw=OLD, **overrides):
    result = {"id": revision.POST_ID, "slug": revision.SLUG,
              "status": "publish", "link": revision.URL,
              "content": {"raw": raw}}
    result.update(overrides)
    return result


class Creatine11945RevisionTests(unittest.TestCase):
    def test_editorial_revision_is_source_led_and_no_old_html(self):
        text = revision.new_body()
        self.assertTrue(revision.clean_revision(text))
        self.assertIn("nekupujte nic", text.lower())
        self.assertNotIn("<!DOCTYPE", text)
        self.assertNotIn("5NM2022", text)

    def test_exact_existing_article_and_malformed_signature_required(self):
        self.assertEqual(revision.old_body(post()), OLD)
        for invalid in (post(id=11264), post(status="draft"),
                        post(slug="wrong-slug"), post(link="http://xfit.cz/"),
                        post(raw="<p>" + ("modern content " * 300) + "</p>")):
            with self.subTest(invalid=str(invalid.get("id"))):
                with self.assertRaises(PublishError):
                    revision.old_body(invalid)

    def test_snapshot_has_immutable_original_without_remote_write(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(revision, "BACKUP", Path(temp) / "before.json"), \
                 patch.object(revision, "get_post", return_value=post()), \
                 patch.object(revision, "wp_request") as writer:
                revision.snapshot()
                data = json.loads(revision.BACKUP.read_text(encoding="utf-8"))
                self.assertEqual(data["original_raw"], OLD)
                self.assertEqual(data["original_sha256"], revision.sha(OLD))
                self.assertEqual(data["remote_writes"], 0)
                writer.assert_not_called()
                with self.assertRaises(PublishError):
                    revision.snapshot()

    def test_one_pinned_content_write_and_public_proof(self):
        body = revision.new_body()
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(revision, "BACKUP", Path(temp) / "before.json"), \
                 patch.object(revision, "get_post", side_effect=[post(), post(), post(body)]), \
                 patch.object(revision, "wp_request", return_value={
                     "id": revision.POST_ID, "status": "publish"
                 }) as writer, \
                 patch.object(revision, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(revision, "public_verified", return_value=True) as public:
                revision.snapshot()
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    revision.deploy()
                self.assertIn("PUBLIC_VERIFIED", output.getvalue())
                writer.assert_called_once_with(
                    "https://xfit.cz", "posts/11945", payload={"content": body})
                public.assert_called_once()

    def test_ambiguous_error_is_reconciled_without_second_post(self):
        body = revision.new_body()
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(revision, "BACKUP", Path(temp) / "before.json"), \
                 patch.object(revision, "get_post", side_effect=[post(), post(), post(body)]), \
                 patch.object(revision, "wp_request", side_effect=PublishError("HTTP 502")) as writer, \
                 patch.object(revision, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(revision, "public_verified", return_value=True):
                revision.snapshot()
                revision.deploy()
                self.assertEqual(writer.call_count, 1)

    def test_unchanged_article_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(revision, "BACKUP", Path(temp) / "before.json"), \
                 patch.object(revision, "get_post", side_effect=[post(), post(), post()]), \
                 patch.object(revision, "wp_request", return_value={
                     "id": revision.POST_ID, "status": "publish"
                 }) as writer, \
                 patch.object(revision, "normalized_base", return_value="https://xfit.cz"):
                revision.snapshot()
                with self.assertRaises(PublishError):
                    revision.deploy()
                self.assertEqual(writer.call_count, 1)


if __name__ == "__main__":
    unittest.main()
