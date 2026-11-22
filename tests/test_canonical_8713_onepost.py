"""Safety regressions for exact WP 8713 source-CAS canonical release."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import xfit_canonical_8713_onepost as c
from scripts.wp_publish import PublishError

SLUG = "overeny-puvodni-clanek"
URL = "https://xfit.cz/" + SLUG + "/"
BAD = '<link rel="canonical" href="https://www.example.com/obsolete-8713" />'
GOOD = '<link rel="canonical" href="' + URL + '" />'
ORIGINAL = ("<!doctype html><html><head>" + BAD + "</head><body>"
            + "<p>Starší text z původního článku s technicky chybným odkazem.</p>" * 28
            + "</body></html>")
PUBLIC_OLD = "<html><head>" + GOOD + "</head><body>" + ORIGINAL + "</body></html>"
PUBLIC_NEW = PUBLIC_OLD.replace(BAD, "")


def post(raw=ORIGINAL, **changes):
    obj = {"id": 8713, "slug": SLUG, "status": "publish",
           "link": URL, "title": {"raw": "Původní fitness průvodce"},
           "content": {"raw": raw}, "modified_gmt": "2023-10-21T07:44:55",
           "featured_media": 0}
    obj.update(changes)
    return obj


def mock_rest(src):
    return {"id": src["id"], "slug": src["slug"], "link": src["link"],
            "status": "publish", "modified_gmt": src["modified_gmt"]}


class Canonical8713Tests(unittest.TestCase):
    def test_exact_one_tag_removed_without_other_mutation(self):
        result = c.remove_one_bogus_canonical(ORIGINAL)
        self.assertEqual(result, ORIGINAL.replace(BAD, ""))
        self.assertTrue(c.before_ok(PUBLIC_OLD, URL))
        self.assertTrue(c.after_ok(PUBLIC_NEW, URL))
        self.assertFalse(c.after_ok(PUBLIC_OLD, URL))
        self.assertFalse(c.before_ok(PUBLIC_NEW, URL))
        self.assertFalse(c.after_ok(PUBLIC_NEW + BAD, URL))

    def test_source_pinning_guards_url_id_metadata(self):
        a = c.source(post())
        self.assertEqual(a["raw"], ORIGINAL)
        self.assertEqual(a["id"], 8713)
        for bad in (post(id=9008), post(id="8713"), post(status="draft"),
                    post(link="https://example.com/"+SLUG+"/"),
                    post(link="https://www.xfit.cz/"+SLUG+"/"),
                    post(slug="different"), post(featured_media=None),
                    post(modified_gmt=""), post(content={"raw":None}),
                    post(title={"raw":""})):
            with self.subTest(data=bad):
                with self.assertRaises(PublishError):
                    c.source(bad)

    def test_multiple_or_different_canonical_never_writes(self):
        for raw in (ORIGINAL.replace(BAD, ""), ORIGINAL.replace(BAD, BAD+BAD),
                    ORIGINAL.replace("https://www.example.com", "https://xfit.cz"),
                    ORIGINAL.replace(BAD, GOOD),
                    ORIGINAL.replace(BAD, '<link rel="canonical" href="http://example.com/test" />')):
            with self.subTest(raw=raw[:100]):
                with self.assertRaises(PublishError):
                    c.remove_one_bogus_canonical(raw)

    def test_backup_precedes_exact_one_post_and_public_proof(self):
        auth = post()
        edited = post(raw=ORIGINAL.replace(BAD, ""),
                      modified_gmt="2026-11-22T18:00:00")
        with TemporaryDirectory() as tmp, patch.object(
                c, "BACKUP", Path(tmp) / "original.json"):
            with patch.object(c, "remote", return_value=auth), \
                 patch.object(c, "public_rest", side_effect=lambda src: mock_rest(src)), \
                 patch.object(c, "get_public", return_value=PUBLIC_OLD), \
                 patch.object(c, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(c, "wp_request") as writer:
                c.snapshot()
                writer.assert_not_called()
            record = json.loads(c.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(record["source"]["raw"], ORIGINAL)
            self.assertEqual(record["source"]["featured_media"], 0)
            self.assertEqual(record["wordpress_post_attempts"], 0)
            with patch.object(c, "remote", side_effect=[auth, edited]), \
                 patch.object(c, "public_rest", side_effect=lambda src: mock_rest(src)), \
                 patch.object(c, "get_public", side_effect=[PUBLIC_OLD, PUBLIC_NEW]), \
                 patch.object(c, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(c, "wp_request",
                              return_value={"id":8713,"status":"publish"}) as writer:
                c.deploy()
                writer.assert_called_once()
                self.assertEqual(writer.call_args.kwargs["payload"],
                                 {"content": ORIGINAL.replace(BAD, "")})

    def test_source_drift_blocks_any_post(self):
        with TemporaryDirectory() as tmp, patch.object(
                c, "BACKUP", Path(tmp) / "original.json"):
            with patch.object(c, "remote", return_value=post()), \
                 patch.object(c, "public_rest", side_effect=lambda src: mock_rest(src)), \
                 patch.object(c, "get_public", return_value=PUBLIC_OLD):
                c.snapshot()
            with patch.object(c, "remote", return_value=post(
                    modified_gmt="2026-11-22T18:00:01")), \
                 patch.object(c, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(c, "wp_request") as writer:
                with self.assertRaisesRegex(PublishError, "Source changed"):
                    c.deploy()
                writer.assert_not_called()

    def test_stale_public_state_blocks_any_post(self):
        with TemporaryDirectory() as tmp, patch.object(
                c, "BACKUP", Path(tmp) / "original.json"):
            with patch.object(c, "remote", return_value=post()), \
                 patch.object(c, "public_rest", side_effect=lambda src: mock_rest(src)), \
                 patch.object(c, "get_public", return_value=PUBLIC_OLD):
                c.snapshot()
            with patch.object(c, "remote", return_value=post()), \
                 patch.object(c, "public_rest", side_effect=lambda src: mock_rest(src)), \
                 patch.object(c, "get_public", return_value=PUBLIC_NEW), \
                 patch.object(c, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(c, "wp_request") as writer:
                with self.assertRaisesRegex(PublishError, "Fresh page"):
                    c.deploy()
                writer.assert_not_called()

    def test_uncertain_post_is_never_retried(self):
        with TemporaryDirectory() as tmp, patch.object(
                c, "BACKUP", Path(tmp) / "original.json"):
            with patch.object(c, "remote", return_value=post()), \
                 patch.object(c, "public_rest", side_effect=lambda src: mock_rest(src)), \
                 patch.object(c, "get_public", return_value=PUBLIC_OLD):
                c.snapshot()
            with patch.object(c, "remote", side_effect=[post(), post()]), \
                 patch.object(c, "public_rest", side_effect=lambda src: mock_rest(src)), \
                 patch.object(c, "get_public", return_value=PUBLIC_OLD), \
                 patch.object(c, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(c, "wp_request", side_effect=PublishError("timeout")) as writer, \
                 patch.object(c.time, "sleep"):
                with self.assertRaisesRegex(PublishError, "UNKNOWN_NO_RETRY"):
                    c.deploy()
                writer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
