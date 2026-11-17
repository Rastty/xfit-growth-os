import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.wp_publish import PublishError
from scripts import xfit_creatine_protein_refresh_4813 as release


class OnePostReleaseTests(unittest.TestCase):
    def public(self):
        return {"id": release.POST_ID, "slug": release.SLUG,
                "status": "publish", "link": release.URL,
                "title": {"rendered": release.TITLE},
                "modified_gmt": release.MODIFIED_GMT,
                "content": {"rendered": "Legacy 5NM2022"}}

    def auth(self):
        p = self.public()
        p["title"]["raw"] = release.TITLE
        p["content"] = {"raw": "5NM2022 " + "some original document text " * 250}
        return p

    def test_editorial_full_refresh_passes(self):
        body = release.revision()
        self.assertIn(release.DESTINATION, body)
        self.assertIn(release.SOURCE, body)
        self.assertNotIn("5NM2022", body)

    def test_identity_rejects_any_drift(self):
        for key, value in (("id", 4814), ("slug", "other"),
                           ("status", "draft"), ("modified_gmt", "2023-05-04T00:00:00"),
                           ("link", "https://evil.example/post")):
            p = self.auth()
            p[key] = value
            with self.subTest(key=key), self.assertRaises(PublishError):
                release.identity(p)

    def test_preflight_public_sha_drift_blocks(self):
        with patch.object(release, "public_rest", return_value=self.public()):
            with self.assertRaisesRegex(PublishError, "changed since pinned"):
                release.before_public()

    def test_snapshot_emits_exact_original_before_write(self):
        with TemporaryDirectory() as td, \
                patch.object(release, "BACKUP", Path(td) / "backup.json"), \
                patch.object(release, "before_public", return_value=self.public()), \
                patch.object(release, "remote", return_value=self.auth()), \
                patch.object(release, "wp_request") as write:
            release.snapshot()
            saved = json.loads(release.BACKUP.read_text())
            self.assertEqual(saved["post_id"], 4813)
            self.assertIn("5NM2022", saved["original_authenticated_post"]["content"]["raw"])
            self.assertEqual(saved["remote_writes"], 0)
            write.assert_not_called()

    def test_apply_aborts_on_live_raw_drift_without_post(self):
        with TemporaryDirectory() as td, \
                patch.object(release, "BACKUP", Path(td) / "backup.json"), \
                patch.object(release, "before_public", return_value=self.public()), \
                patch.object(release, "remote") as remote, \
                patch.object(release, "wp_request") as write:
            release.BACKUP.write_text(json.dumps({
                "schema": 1, "post_id": 4813, "slug": release.SLUG,
                "modified_gmt": release.MODIFIED_GMT,
                "public_rendered_sha": release.PUBLIC_RENDERED_SHA,
                "remote_writes": 0,
                "original_authenticated_post": self.auth(),
                "original_sha": release.sha(release.raw(self.auth())),
                "revision_sha": release.sha(release.revision())}))
            changed = self.auth()
            changed["content"]["raw"] += " modified"
            remote.return_value = changed
            with self.assertRaisesRegex(PublishError, "changed after snapshot"):
                release.apply()
            write.assert_not_called()

    def test_apply_exactly_one_write_and_verified_readback(self):
        with TemporaryDirectory() as td, \
                patch.object(release, "BACKUP", Path(td) / "backup.json"), \
                patch.object(release, "before_public", return_value=self.public()), \
                patch.object(release, "remote") as remote, \
                patch.object(release, "normalized_base", return_value="https://xfit.cz"), \
                patch.object(release, "verify_public", return_value=True), \
                patch.object(release, "wp_request") as write:
            original = self.auth()
            release.BACKUP.write_text(json.dumps({
                "schema": 1, "post_id": 4813, "slug": release.SLUG,
                "modified_gmt": release.MODIFIED_GMT,
                "public_rendered_sha": release.PUBLIC_RENDERED_SHA,
                "remote_writes": 0,
                "original_authenticated_post": original,
                "original_sha": release.sha(release.raw(original)),
                "revision_sha": release.sha(release.revision())}))
            after = self.auth()
            after["content"]["raw"] = release.revision()
            remote.side_effect = [original, after]
            write.return_value = {"id": 4813, "status": "publish"}
            release.apply()
            self.assertEqual(write.call_count, 1)
            self.assertEqual(write.call_args.kwargs["payload"], {"content": release.revision()})

    def test_ambiguous_post_response_never_retries(self):
        with TemporaryDirectory() as td, \
                patch.object(release, "BACKUP", Path(td) / "backup.json"), \
                patch.object(release, "before_public", return_value=self.public()), \
                patch.object(release, "remote", return_value=self.auth()), \
                patch.object(release, "normalized_base", return_value="https://xfit.cz"), \
                patch.object(release, "wp_request", side_effect=OSError("timeout")) as write:
            original = self.auth()
            release.BACKUP.write_text(json.dumps({
                "schema": 1, "post_id": 4813, "slug": release.SLUG,
                "modified_gmt": release.MODIFIED_GMT,
                "public_rendered_sha": release.PUBLIC_RENDERED_SHA,
                "remote_writes": 0,
                "original_authenticated_post": original,
                "original_sha": release.sha(release.raw(original)),
                "revision_sha": release.sha(release.revision())}))
            with self.assertRaisesRegex(PublishError, "mismatch"):
                release.apply()
            self.assertEqual(write.call_count, 1)


if __name__ == "__main__":
    unittest.main()
