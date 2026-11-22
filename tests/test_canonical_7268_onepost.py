"""Verify #7268 runner reuses tested guards and leaves #8713 state unchanged."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import xfit_canonical_7268_onepost as wrapper
from scripts import xfit_canonical_8713_onepost as engine
from scripts.wp_publish import PublishError

URL = "https://xfit.cz/jak-mohu-dosahnout-svalu-na-brise-bez-nutnosti-pouziti-vybaveni/"
SLUG = "jak-mohu-dosahnout-svalu-na-brise-bez-nutnosti-pouziti-vybaveni"
BAD = '<link rel="canonical" href="https://example.com/incorrect-abdominal-exercise" />'
GOOD = '<link rel="canonical" href="' + URL + '" />'
RAW = "<!doctype html><html><head>" + BAD + "</head><body>" + (
    "<p>Praktické cviky bez vybavení s pozorností k přiměřenému úsilí.</p>" * 26
) + "</body></html>"
OLD = "<html><head>" + GOOD + "</head><body>" + RAW + "</body></html>"
AFTER = OLD.replace(BAD, "")


def post(body=RAW, modified="2023-05-14T06:29:04"):
    return {"id": 7268, "slug": SLUG, "link": URL, "status": "publish",
            "title": {"raw": "Jak dosáhnout svalů na břiše bez vybavení"},
            "content": {"raw": body}, "modified_gmt": modified,
            "featured_media": 0}


def public_rest(src):
    return {"id": 7268, "slug": SLUG, "link": URL, "status": "publish",
            "modified_gmt": src["modified_gmt"]}


class Onepost7268Tests(unittest.TestCase):
    def test_bad_args_cannot_write(self):
        for args in ([], ["publish"], ["snapshot", "deploy"]):
            with self.subTest(args=args), patch.object(engine, "wp_request") as w:
                with self.assertRaises(PublishError):
                    wrapper.run(args)
                w.assert_not_called()

    def test_reuse_same_sourceguard_while_restoring_pinned_identity(self):
        with TemporaryDirectory() as temp, \
             patch.object(wrapper, "BACKUP", Path(temp) / "original.json"):
            before_id, before_path = engine.POST_ID, engine.BACKUP
            with patch.object(engine, "remote", return_value=post()), \
                 patch.object(engine, "public_rest", side_effect=public_rest), \
                 patch.object(engine, "get_public", return_value=OLD), \
                 patch.object(engine, "wp_request") as writer:
                wrapper.run(["snapshot"])
                writer.assert_not_called()
            self.assertEqual(engine.POST_ID, before_id)
            self.assertEqual(engine.BACKUP, before_path)
            record = json.loads(wrapper.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(record["source"]["id"], 7268)
            self.assertEqual(record["source"]["raw"], RAW)
            self.assertEqual(record["wordpress_post_attempts"], 0)

    def test_single_content_only_post_and_public_verification(self):
        changed = post(body=RAW.replace(BAD, ""), modified="2026-11-22T19:00:00")
        with TemporaryDirectory() as temp, \
             patch.object(wrapper, "BACKUP", Path(temp) / "original.json"):
            with patch.object(engine, "remote", return_value=post()), \
                 patch.object(engine, "public_rest", side_effect=public_rest), \
                 patch.object(engine, "get_public", return_value=OLD):
                wrapper.run(["snapshot"])
            with patch.object(engine, "remote", side_effect=[post(), changed]), \
                 patch.object(engine, "public_rest", side_effect=public_rest), \
                 patch.object(engine, "get_public", side_effect=[OLD, AFTER]), \
                 patch.object(engine, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(engine, "wp_request",
                    return_value={"id": 7268, "status": "publish"}) as writer:
                wrapper.run(["deploy"])
                writer.assert_called_once()
                self.assertEqual(writer.call_args.kwargs["payload"],
                                 {"content": RAW.replace(BAD, "")})
            self.assertEqual(engine.POST_ID, 8713)

    def test_changed_source_blocks_any_post(self):
        with TemporaryDirectory() as temp, \
             patch.object(wrapper, "BACKUP", Path(temp) / "original.json"):
            with patch.object(engine, "remote", return_value=post()), \
                 patch.object(engine, "public_rest", side_effect=public_rest), \
                 patch.object(engine, "get_public", return_value=OLD):
                wrapper.run(["snapshot"])
            with patch.object(engine, "remote", return_value=post(modified="2026-11-22T19:00:00")), \
                 patch.object(engine, "wp_request") as writer:
                with self.assertRaisesRegex(PublishError, "Source changed"):
                    wrapper.run(["deploy"])
                writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
