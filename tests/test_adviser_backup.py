import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.wp_publish import MARKER, PublishError
from scripts.xfit_adviser_backup import snapshot, TARGETS


class AdviserBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.destination = Path(self.temp.name) / "backup.json"

    def article(self, kind="whey"):
        ident, slug = TARGETS[kind]
        return {"id": ident, "slug": slug, "status": "publish",
                "modified_gmt": "2026-11-15T12:00:00",
                "link": f"https://xfit.cz/{slug}/",
                "content": {"raw": MARKER + "\n" + "<h2>Průvodce</h2>" + "<p>Důležité rozhodnutí.</p>"*100}}

    def test_snapshot_full_source_without_remote_write(self):
        for kind in TARGETS:
            with self.subTest(kind=kind):
                post = self.article(kind)
                file = Path(self.temp.name) / f"{kind}.json"
                with patch("scripts.xfit_adviser_backup.normalized_base", return_value="https://xfit.cz"):
                    calls = []
                    def read(base, route):
                        calls.append((base, route))
                        return post
                    result = snapshot(kind, wp_read=read, output=file)
                payload = json.loads(file.read_text())
                self.assertEqual(result["remote_writes"], 0)
                self.assertEqual(payload["original_raw"], post["content"]["raw"])
                self.assertEqual(payload["raw_sha256"], hashlib.sha256(
                    payload["original_raw"].encode()).hexdigest())
                self.assertEqual(len(calls), 1)
                self.assertIn("context=edit", calls[0][1])

    def test_rejects_identity_redirect_unowned_and_existing_backup(self):
        post = self.article()
        for changed in (
            {**post, "id": 1},
            {**post, "status": "draft"},
            {**post, "link": "https://elsewhere.example/"},
            {**post, "content": {"raw": "<p>not owned</p>"*100}},
        ):
            with self.subTest(changed=list(changed.keys())):
                with patch("scripts.xfit_adviser_backup.normalized_base", return_value="https://xfit.cz"):
                    with self.assertRaises(PublishError):
                        snapshot("whey", wp_read=lambda *args: changed,
                                 output=self.destination)
                self.assertFalse(self.destination.exists())
        with patch("scripts.xfit_adviser_backup.normalized_base", return_value="https://xfit.cz"):
            snapshot("whey", wp_read=lambda *args: post, output=self.destination)
            with self.assertRaisesRegex(PublishError, "cannot be overwritten"):
                snapshot("whey", wp_read=lambda *args: post, output=self.destination)

    def test_other_post_id_never_allowed(self):
        with self.assertRaisesRegex(PublishError, "Unsupported"):
            snapshot("other", wp_read=lambda *args: None, output=self.destination)


if __name__ == "__main__":
    unittest.main()
