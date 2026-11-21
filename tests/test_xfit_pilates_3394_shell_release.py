"""No-duplicate, rollback-first, exact-source Pilates #3394 SEO rescue tests."""
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import xfit_pilates_3394_shell_release as p
from scripts.wp_publish import PublishError


def fixture():
    parts = []
    for i in range(15):
        parts.append("<p>Čtenáři porovnávají pilates s běžným cvičením. "
                     + ("Praktický průvodce základními rozdíly a výběrem lekce. " * 5)
                     + f" Příklad {i}.</p>")
    for i in range(6):
        parts.insert(i * 2, f"<h2>Praktické srovnání typu lekce {i}</h2>")
    body = "\n".join(parts)
    shell = ('<!DOCTYPE html><html lang="cs"><head>'
             '<meta charset="UTF-8"><title>Pilates vs. běžné cvičení</title>'
             '</head><body>' + body + '</body></html>')
    return shell, body


def post(raw):
    return {
        "id": 3394, "slug": p.SLUG, "status": "publish",
        "link": p.URL, "modified_gmt": p.EXPECTED_MODIFIED,
        "title": {"raw": "Pilates vs klasické cvičení"},
        "excerpt": {"raw": "Redakční popis porovnání lekcí"},
        "content": {"raw": raw},
        "featured_media": 77, "author": 11,
        "categories": [2], "tags": [3],
    }


class Pilates3394OnepostTests(unittest.TestCase):
    def test_exact_shell_surgery_preserves_body_h2_and_original_links(self):
        old, body = fixture()
        result = p.transform(old)
        self.assertIn(body[:220], result)
        self.assertIn(body[-220:], result)
        self.assertEqual(result.count(p.TARGET), 1)
        self.assertEqual(result.count(p.MARKER), 1)
        self.assertEqual(result.count("<h2>"), 6)
        self.assertEqual(result.count("<p"), 16)
        self.assertNotIn("<title", result.lower())
        self.assertNotIn("<head", result.lower())
        self.assertNotIn("<html", result.lower())
        self.assertNotIn("<!DOCTYPE", result)
        self.assertLess(result.index(p.MARKER), result.index("<h2>"))
        self.assertIn("min-height:44px", result)
        self.assertIn("Klasické a power pilates", result)

    def test_surgery_fails_closed_on_changed_markup_and_source_fragments(self):
        old, body = fixture()
        invalid = (
            old.replace("<!DOCTYPE html>", ""),
            old + "<p>Trailing unreviewed content</p>",
            old.replace("<title>", "<title><title>"),
            old.replace("<body>", "<body><script>hidden()</script>"),
            old.replace("<body>", "<body><link rel='canonical' href='https://evil.example/'>"),
            old.replace(body, body + '<p><a href="' + p.TARGET + '">Already linked</a></p>'),
            old.replace("</body>", "<h2>Extra section</h2></body>"),
            old.replace("</head>", '<style>bad</style></head>'),
        )
        for value in invalid:
            with self.subTest(value=value[-80:]), self.assertRaises(PublishError):
                p.transform(value)

    def test_requires_reviewed_original_hash_and_last_modified(self):
        old, _ = fixture()
        with patch.object(p, "EXPECTED_SHA", p.sha(old)):
            self.assertEqual(p.identify(post(old)), old)
            with self.assertRaises(PublishError):
                p.identify(post(old+"x"))
            with self.assertRaises(PublishError):
                p.identify(dict(post(old), modified_gmt="2023-04-19T05:28:00"))
            with self.assertRaises(PublishError):
                p.identify(dict(post(old), id=3395))
            with self.assertRaises(PublishError):
                p.identify(dict(post(old), link="https://evil.example/post/"))

    def test_snapshot_immutable_with_backup_before_any_remote_write(self):
        old, _ = fixture()
        with tempfile.TemporaryDirectory() as d, \
             patch.object(p, "BACKUP", Path(d)/"original.json"), \
             patch.object(p, "EXPECTED_SHA", p.sha(old)), \
             patch.object(p, "source", return_value=post(old)), \
             patch.object(p, "wp_request") as writer:
            p.snapshot()
            data = json.loads(p.BACKUP.read_text())
            self.assertEqual(data["source_sha"], p.sha(old))
            self.assertEqual(data["replacement_sha"], p.sha(p.transform(old)))
            self.assertEqual(data["original"]["content"]["raw"], old)
            self.assertEqual(data["remote_writes"], 0)
            writer.assert_not_called()
            with self.assertRaises(PublishError):
                p.snapshot()

    def test_only_one_exact_wordpress_post_and_verified_independent_public(self):
        old, _ = fixture()
        new = p.transform(old)
        with tempfile.TemporaryDirectory() as d, \
             patch.object(p, "BACKUP", Path(d)/"original.json"), \
             patch.object(p, "EXPECTED_SHA", p.sha(old)), \
             patch.object(p, "source", side_effect=[post(old), post(old), post(new)]) as reads, \
             patch.object(p, "wp_request", return_value={
                 "id": 3394, "status": "publish"
             }) as writer, \
             patch.object(p, "normalized_base", return_value="https://xfit.cz"), \
             patch.object(p, "verify_public", return_value=True) as public:
            p.snapshot()
            out = StringIO()
            with contextlib.redirect_stdout(out):
                p.apply()
            writer.assert_called_once_with(
                "https://xfit.cz", "posts/3394", payload={"content": new})
            public.assert_called_once()
            self.assertEqual(reads.call_count, 3)
            self.assertIn('"state": "PUBLIC_VERIFIED"', out.getvalue())
            self.assertIn('"seo_title_tags": 1', out.getvalue())

    def test_ambiguous_post_is_never_retried_and_no_success_is_claimed(self):
        old, _ = fixture()
        with tempfile.TemporaryDirectory() as d, \
             patch.object(p, "BACKUP", Path(d)/"original.json"), \
             patch.object(p, "EXPECTED_SHA", p.sha(old)), \
             patch.object(p, "source", side_effect=[post(old), post(old), post(old)]), \
             patch.object(p, "wp_request", side_effect=PublishError("HTTP 455")) as writer, \
             patch.object(p, "normalized_base", return_value="https://xfit.cz"), \
             patch.object(p, "verify_public") as public:
            p.snapshot()
            with self.assertRaises(PublishError):
                p.apply()
            self.assertEqual(writer.call_count, 1)
            public.assert_not_called()

    def test_metadata_drift_blocks_before_any_content_post(self):
        old, _ = fixture()
        with tempfile.TemporaryDirectory() as d, \
             patch.object(p, "BACKUP", Path(d)/"original.json"), \
             patch.object(p, "EXPECTED_SHA", p.sha(old)), \
             patch.object(p, "source", side_effect=[
                 post(old), dict(post(old), featured_media=99)
             ]), \
             patch.object(p, "wp_request") as writer:
            p.snapshot()
            with self.assertRaises(PublishError):
                p.apply()
            writer.assert_not_called()

    def test_public_requires_single_head_title_and_early_content_handoff(self):
        page = ('<html><head><title>Jedna SEO hlavička</title>'
                '<link rel="canonical" href="' + p.URL + '">'
                '</head><body><h1>Pilates vs klasické cvičení</h1>'
                + p.HANDOFF + '</body></html>')
        with patch.object(p, "read_public", return_value=(page, "")):
            self.assertTrue(p.verify_public())
        with patch.object(p, "read_public", return_value=(
                page.replace("</head>", "<title>Druhá</title></head>"), "")):
            self.assertFalse(p.verify_public())
        with patch.object(p, "read_public", return_value=(
                page.replace(p.TARGET, "https://evil.example/"), "")):
            self.assertFalse(p.verify_public())


if __name__ == "__main__":
    unittest.main()
