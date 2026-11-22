"""Exact WP #8531: food-first mass-gainer buyer guide and canonical rescue."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import xfit_gainer_8531_evidence_release as r
from scripts.wp_publish import PublishError

BAD='<link rel="canonical" href="https://www.example.com/gainer/" />'
SELF='<link rel="canonical" href="'+r.URL+'" />'
TEXT=("<p>Gainer se nabízí jako cesta k růstu svalové hmoty. "
      "Před rozhodnutím je potřeba porovnávat bílkoviny a energii.</p>")
OLD=(
    '<!DOCTYPE html><html><head>'+BAD+'</head><body>'
    '<h2>Gainer a svalová hmota</h2>'+TEXT*32+
    '</body></html>'
)
TITLE="Jaké jsou klíčové faktory při výběru nejlepšího gainery pro fitness a růst svalové hmoty?"
PUBLIC_OLD='<html><head>'+SELF+'</head><body>'+OLD+'</body></html>'
NEW_PUBLIC='<html><head>'+SELF+'</head><body><article>'+
    r.SOURCE.read_text(encoding="utf-8")+'</article></body></html>'


def post(body=OLD, **change):
    value={
        "id":r.POST_ID,"slug":r.SLUG,"status":"publish","link":r.URL,
        "title":{"raw":TITLE},"content":{"raw":body},
        "modified_gmt":"2023-10-13T17:01:57","featured_media":0,
    }
    value.update(change)
    return value


class Gainer8531Tests(unittest.TestCase):
    def test_reviewed_source_has_no_buy_and_hypothetical_correct_math(self):
        raw=r.reviewed()
        self.assertTrue(r.new_body(raw))
        self.assertEqual(raw.count("<h2>"),7)
        self.assertIn("nekoupit nic",r.plain(raw))
        self.assertIn("93,75 Kč",raw)
        self.assertIn("37,50 Kč",raw)
        self.assertEqual(750/20,37.5)
        self.assertEqual(37.5/400*1000,93.75)
        self.assertIn("modelový příklad",r.plain(raw))
        self.assertIn("gainer, domácí svačina",r.plain(raw))
        self.assertEqual(r.canonical_links(raw),[])
        for link in r.SOURCES+r.GUIDES:
            self.assertEqual(raw.count('href="'+link+'"'),1)
        self.assertNotIn("5NM2022",raw)
        self.assertNotIn("example.com",raw)
        self.assertNotIn("namaximum.cz",raw)

    def test_source_only_exact_old_bogus_one_document(self):
        self.assertTrue(r.legacy(OLD))
        self.assertFalse(r.legacy(OLD.replace(BAD,"")))
        self.assertFalse(r.legacy(OLD.replace(BAD,SELF)))
        self.assertFalse(r.legacy(OLD.replace(BAD,BAD+BAD)))
        self.assertFalse(r.legacy(OLD.replace("<!DOCTYPE html>","")))
        self.assertFalse(r.legacy(OLD.replace("Gainer","Doplněk").replace(
            "gainer","doplněk")))

    def test_public_before_and_after_canonicity(self):
        self.assertTrue(r.old_public(PUBLIC_OLD))
        self.assertTrue(r.new_public(NEW_PUBLIC))
        self.assertFalse(r.old_public(NEW_PUBLIC))
        self.assertFalse(r.new_public(PUBLIC_OLD))
        self.assertFalse(r.new_public(NEW_PUBLIC+BAD))

    def test_wrong_source_identity_rejected(self):
        for value in (
            post(id=1),post(id="8531"),post(slug="other"),
            post(status="draft"),post(link="https://xfit.cz/other/"),
            post(content={"raw":"tiny"}),
            post(title={"raw":"Fotbal a běhání"}),
            post(modified_gmt=""),post(featured_media=None)
        ):
            with self.subTest(field=value.get("slug")):
                with self.assertRaises(PublishError):
                    r.identity(value)
        self.assertEqual(r.classify(post())["mode"],"update")
        self.assertEqual(
            r.classify(post(body=r.reviewed()))["mode"],"already_applied")

    def test_full_immutable_backup_then_exactly_one_wp_content_post(self):
        original=post()
        changed=post(body=r.reviewed(),
                     modified_gmt="2026-11-22T12:15:00")
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"backup.json"
        ):
            with patch.object(r,"remote",return_value=original),patch.object(
                r,"public_page",return_value=PUBLIC_OLD
            ),patch.object(r,"wp_request") as writer:
                r.snapshot()
                writer.assert_not_called()
            saved=json.loads(r.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(saved["original_raw"],OLD)
            self.assertEqual(saved["original_title"],TITLE)
            self.assertEqual(saved["remote_writes"],0)
            self.assertEqual(saved["post_id"],8531)
            with patch.object(r,"remote",side_effect=[original,changed]),patch.object(
                r,"public_page",side_effect=[PUBLIC_OLD,NEW_PUBLIC]
            ),patch.object(r,"normalized_base",return_value="https://xfit.cz"),patch.object(
                r,"wp_request",return_value={"id":8531,"status":"publish"}
            ) as writer,patch.object(r,"verify_public") as proof:
                r.deploy()
                writer.assert_called_once()
                self.assertEqual(writer.call_args.kwargs["payload"],
                                 {"content":r.reviewed()})
                proof.assert_called_once_with(r.URL,TITLE,r.reviewed())

    def test_concurrent_editor_or_changed_public_blocks_post(self):
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"backup.json"
        ):
            with patch.object(r,"remote",return_value=post()),patch.object(
                r,"public_page",return_value=PUBLIC_OLD
            ):
                r.snapshot()
            updated=post(body=OLD+"<p>Editor now owns this source.</p>",
                         modified_gmt="2026-11-22T12:15:00")
            with patch.object(r,"remote",return_value=updated),patch.object(
                r,"wp_request"
            ) as writer:
                with self.assertRaisesRegex(PublishError,"Concurrent"):
                    r.deploy()
                writer.assert_not_called()
            with patch.object(r,"remote",return_value=post()),patch.object(
                r,"public_page",return_value=NEW_PUBLIC
            ),patch.object(r,"wp_request") as writer:
                with self.assertRaisesRegex(PublishError,"Prewrite public canonical"):
                    r.deploy()
                writer.assert_not_called()

    def test_transport_timeout_never_retried(self):
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"backup.json"
        ):
            with patch.object(r,"remote",return_value=post()),patch.object(
                r,"public_page",return_value=PUBLIC_OLD
            ):
                r.snapshot()
            with patch.object(r,"remote",side_effect=[post(),post()]),patch.object(
                r,"public_page",return_value=PUBLIC_OLD
            ),patch.object(r,"normalized_base",return_value="https://xfit.cz"),patch.object(
                r,"wp_request",side_effect=PublishError("POST timeout")
            ) as writer:
                with self.assertRaisesRegex(PublishError,"mismatch"):
                    r.deploy()
                writer.assert_called_once()

    def test_already_published_rewrite_is_zero_write(self):
        new=post(body=r.reviewed())
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"backup.json"
        ):
            with patch.object(r,"remote",return_value=new):
                r.snapshot()
            with patch.object(r,"remote",return_value=new),patch.object(
                r,"public_page",return_value=NEW_PUBLIC
            ),patch.object(r,"verify_public") as proof,patch.object(
                r,"wp_request"
            ) as writer:
                r.deploy()
                writer.assert_not_called()
                proof.assert_called_once_with(r.URL,TITLE,r.reviewed())


if __name__=="__main__":
    unittest.main()
