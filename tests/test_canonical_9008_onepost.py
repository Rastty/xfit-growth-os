"""Source-locked SEO canonical onepost: no invented slug, zero blind retries."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import xfit_canonical_9008_onepost as c
from scripts.wp_publish import PublishError

BAD='<link rel="canonical" href="https://www.example.com/creatine-timing" />'
GOOD='<link rel="canonical" href="'+c.URL+'" />'
OLD=("<!DOCTYPE html><html><head>"+BAD+"</head><body>"
     +"<h2>Jak užívat kreatin v rámci fitness</h2>"
     +"<p>Původní vysvětlení načasování kreatinu bez zaručených výsledků.</p>"*28
     +"</body></html>")
TITLE="Jaký je nejlepší čas pro užívání kreatinu v rámci fitness tréninku?"
PUBLIC_BEFORE="<html><head>"+GOOD+"</head><body>"+OLD+"</body></html>"
PUBLIC_AFTER="<html><head>"+GOOD+"</head><body>"+OLD.replace(BAD,"")+"</body></html>"


def post(body=OLD, **change):
    result={
        "id":c.POST_ID,"slug":c.SLUG,"status":"publish","link":c.URL,
        "title":{"raw":TITLE}, "content":{"raw":body},
        "modified_gmt":"2023-10-21T07:44:55",
        "featured_media":0,
    }
    result.update(change)
    return result


class Canonical9008Tests(unittest.TestCase):
    def test_only_exact_bogus_example_link_token_removed(self):
        result=c.remove_one_bogus_canonical(OLD)
        self.assertEqual(result, OLD.replace(BAD,""))
        self.assertEqual(c.canonicals(OLD), ["https://www.example.com/creatine-timing"])
        self.assertEqual(c.canonicals(result), [])
        self.assertTrue(c.approved_before(PUBLIC_BEFORE))
        self.assertTrue(c.approved_after(PUBLIC_AFTER))
        self.assertEqual(c.public_state(PUBLIC_BEFORE)["canonical_total"],2)

    def test_refuses_other_canonical_or_multiple_tags(self):
        bodies=[
            OLD.replace("www.example.com", "xfit.cz"),
            OLD.replace(BAD,GOOD),
            OLD.replace(BAD,""),
            OLD.replace(BAD,BAD+BAD),
            OLD.replace(BAD,BAD.replace('canonical','alternate')),
            "<p>Short</p>"+BAD,
            OLD.replace("https://www.example.com/creatine-timing",
                        "http://www.example.com/creatine-timing"),
        ]
        for body in bodies:
            with self.subTest(body=body[:100]):
                with self.assertRaises(PublishError):
                    c.remove_one_bogus_canonical(body)

    def test_public_two_head_canonicals_do_not_pass(self):
        self.assertFalse(c.approved_before(PUBLIC_AFTER))
        self.assertFalse(c.approved_after(PUBLIC_BEFORE))
        self.assertFalse(c.approved_after(PUBLIC_AFTER+BAD))
        self.assertFalse(c.approved_before(PUBLIC_BEFORE+BAD))

    def test_pinned_source_identification(self):
        self.assertEqual(c.pinned(post())[0],OLD)
        mutations=[
            post(id=123),post(id="9008"),post(slug="wrong"),
            post(status="draft"),post(link="https://xfit.cz/other/"),
            post(title={"raw":"Neověřený článek"}),
            post(modified_gmt=""),post(featured_media=None),
            post(content={"raw":None}),
        ]
        for val in mutations:
            with self.subTest(post_id=val.get("id")):
                with self.assertRaises(PublishError):
                    c.pinned(val)

    def test_full_backup_and_single_content_only_write(self):
        before=post()
        changed=post(body=OLD.replace(BAD,""),
                     modified_gmt="2026-11-22T12:00:01")
        with TemporaryDirectory() as d, patch.object(
            c,"BACKUP",Path(d)/"full-original.json"
        ):
            with patch.object(c,"remote",return_value=before), \
                 patch.object(c,"public_page",return_value=PUBLIC_BEFORE), \
                 patch.object(c,"wp_request") as writer:
                c.snapshot()
                writer.assert_not_called()
            archived=json.loads(c.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(archived["original_raw"],OLD)
            self.assertEqual(archived["original_title"],TITLE)
            self.assertEqual(archived["featured_media"],0)
            self.assertEqual(archived["remote_writes"],0)
            self.assertEqual(archived["reviewed_public_canonicals"]["bogus_count"],1)
            with patch.object(c,"remote",side_effect=[before,changed]), \
                 patch.object(c,"public_page",
                     side_effect=[PUBLIC_BEFORE,PUBLIC_AFTER]), \
                 patch.object(c,"normalized_base",return_value="https://xfit.cz"), \
                 patch.object(c,"wp_request",
                     return_value={"id":9008,"status":"publish"}) as writer:
                c.deploy()
                writer.assert_called_once()
                self.assertEqual(writer.call_args.kwargs["payload"],
                                 {"content":OLD.replace(BAD,"")})

    def test_concurrent_source_edit_cannot_write(self):
        with TemporaryDirectory() as d,patch.object(
            c,"BACKUP",Path(d)/"full-original.json"
        ):
            with patch.object(c,"remote",return_value=post()), \
                 patch.object(c,"public_page",return_value=PUBLIC_BEFORE):
                c.snapshot()
            with patch.object(c,"remote",return_value=post(
                modified_gmt="2026-11-22T12:00:01"
            )), patch.object(c,"wp_request") as writer:
                with self.assertRaisesRegex(PublishError,"Concurrent"):
                    c.deploy()
                writer.assert_not_called()

    def test_public_changed_since_snapshot_blocks_wp_post(self):
        with TemporaryDirectory() as d,patch.object(
            c,"BACKUP",Path(d)/"full-original.json"
        ):
            with patch.object(c,"remote",return_value=post()), \
                 patch.object(c,"public_page",return_value=PUBLIC_BEFORE):
                c.snapshot()
            with patch.object(c,"remote",return_value=post()), \
                 patch.object(c,"public_page",return_value=PUBLIC_AFTER), \
                 patch.object(c,"wp_request") as writer:
                with self.assertRaisesRegex(PublishError,"prewrite public canonical"):
                    c.deploy()
                writer.assert_not_called()

    def test_single_timeout_never_retried_or_falsely_verified(self):
        with TemporaryDirectory() as d,patch.object(
            c,"BACKUP",Path(d)/"full-original.json"
        ):
            with patch.object(c,"remote",return_value=post()), \
                 patch.object(c,"public_page",return_value=PUBLIC_BEFORE):
                c.snapshot()
            with patch.object(c,"remote",side_effect=[post(),post()]), \
                 patch.object(c,"public_page",return_value=PUBLIC_BEFORE), \
                 patch.object(c,"normalized_base",return_value="https://xfit.cz"), \
                 patch.object(c,"wp_request",side_effect=PublishError(
                     "WEDOS POST timeout"
                 )) as writer:
                with self.assertRaisesRegex(PublishError,"never retry"):
                    c.deploy()
                writer.assert_called_once()


if __name__=="__main__":
    unittest.main()
