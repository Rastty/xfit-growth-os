"""Exact WP #9371: source-locked evidence revision and unique public canonical."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import xfit_bcaa_9371_evidence_release as r
from scripts.wp_publish import PublishError

BAD='<link rel="canonical" href="https://www.example.com/bcaa/" />'
SELF='<link rel="canonical" href="'+r.URL+'" />'
TEXT=("<p>BCAA mohou pomáhat regeneraci. Jak správně používat BCAA "
      "pro regeneraci a svalový růst; popisujeme běžnou stravu.</p>")
OLD=("".join(
    '<!DOCTYPE html><html><head>'+ (BAD if n==0 else "")
    +'</head><body><h2>Regenerace a růst BCAA</h2>'
    +TEXT*30+'</body></html>'
    for n in range(3)
))
TITLE="Jak správně používat BCAA pro lepší regeneraci a svalový růst"
PUBLIC_OLD='<html><head>'+SELF+'</head><body>'+OLD+'</body></html>'
NEW_PUBLIC='<html><head>'+SELF+'</head><body><article>'+r.SOURCE.read_text(encoding="utf-8")+'</article></body></html>'


def post(body=OLD, **updates):
    sample={
        "id":r.POST_ID,"slug":r.SLUG,"status":"publish","link":r.URL,
        "content":{"raw":body},"title":{"raw":TITLE},
        "modified_gmt":"2023-10-21T05:44:55","featured_media":0,
    }
    sample.update(updates)
    return sample


class BCAA9371Tests(unittest.TestCase):
    def test_new_content_is_evidence_led_noncommercial_and_independent(self):
        content=r.reviewed()
        self.assertTrue(r.new_body(content))
        self.assertIn("nekoupit nic",r.plain(content))
        self.assertIn("bcaa, eaa nebo protein",r.plain(content))
        self.assertIn("svalovou bolestí",r.plain(content))
        self.assertEqual(content.count("<h2>"),7)
        self.assertEqual(r.canonical_links(content),[])
        self.assertNotIn("5NM2022",content)
        self.assertNotIn("<!DOCTYPE",content)
        for link in r.SOURCES+r.GUIDES:
            self.assertEqual(content.count('href="'+link+'"'),1)

    def test_only_exact_old_nested_three_docs_and_bogus_canonical(self):
        self.assertTrue(r.legacy(OLD))
        self.assertFalse(r.legacy(OLD.replace(BAD,"")))
        self.assertFalse(r.legacy(OLD.replace(BAD,SELF)))
        self.assertFalse(r.legacy(OLD.replace(BAD,BAD+BAD)))
        self.assertFalse(r.legacy(OLD.replace("<!DOCTYPE html>","",1)))
        self.assertFalse(r.legacy(OLD.replace("BCAA","doplněk")))

    def test_public_duplicate_source_and_unique_correct_destination(self):
        self.assertTrue(r.old_public(PUBLIC_OLD))
        self.assertFalse(r.new_public(PUBLIC_OLD))
        self.assertTrue(r.new_public(NEW_PUBLIC))
        self.assertFalse(r.old_public(NEW_PUBLIC))
        self.assertFalse(r.new_public(NEW_PUBLIC+BAD))

    def test_wrong_identity_and_partial_missing_metadata_refused(self):
        for sample in (
            post(id=1),post(id="9371"),post(status="draft"),
            post(slug="other"),post(link="https://xfit.cz/elsewhere/"),
            post(content={"raw":"short"}),post(title={"raw":"Neznámé"}),
            post(modified_gmt="not known"),post(featured_media=None)
        ):
            with self.subTest(sample=sample.get("slug")):
                with self.assertRaises(PublishError):
                    r.identity(sample)
        self.assertEqual(r.classify(post())["mode"],"update")
        self.assertEqual(
            r.classify(post(body=r.reviewed()))["mode"],"already_applied"
        )

    def test_immutable_full_original_backup_and_single_content_only_post(self):
        before=post()
        after=post(body=r.reviewed(),modified_gmt="2026-11-22T11:31:02")
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"snapshot.json"
        ):
            with patch.object(r,"remote",return_value=before),patch.object(
                r,"public_page",return_value=PUBLIC_OLD
            ),patch.object(r,"wp_request") as writer:
                r.snapshot()
                writer.assert_not_called()
            saved=json.loads(r.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(saved["original_raw"],OLD)
            self.assertEqual(saved["original_title"],TITLE)
            self.assertEqual(saved["original_media"],0)
            self.assertEqual(saved["remote_writes"],0)
            with patch.object(r,"remote",side_effect=[before,after]),patch.object(
                r,"public_page",side_effect=[PUBLIC_OLD,NEW_PUBLIC]
            ),patch.object(r,"normalized_base",return_value="https://xfit.cz"),patch.object(
                r,"wp_request",return_value={"id":9371,"status":"publish"}
            ) as writer,patch.object(r,"verify_public") as proof:
                r.deploy()
                writer.assert_called_once()
                self.assertEqual(writer.call_args.kwargs["payload"],
                                 {"content":r.reviewed()})
                proof.assert_called_once_with(r.URL,TITLE,r.reviewed())

    def test_no_post_when_other_editor_changes_original(self):
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"snapshot.json"
        ):
            with patch.object(r,"remote",return_value=post()),patch.object(
                r,"public_page",return_value=PUBLIC_OLD
            ):
                r.snapshot()
            drift=post(body=OLD+"<p>Other editor note.</p>",
                       modified_gmt="2026-11-22T11:32:00")
            with patch.object(r,"remote",return_value=drift),patch.object(
                r,"wp_request"
            ) as writer:
                with self.assertRaisesRegex(PublishError,"Concurrent"):
                    r.deploy()
                writer.assert_not_called()

    def test_bad_prewrite_public_canonical_blocks_post(self):
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"snapshot.json"
        ):
            with patch.object(r,"remote",return_value=post()),patch.object(
                r,"public_page",return_value=PUBLIC_OLD
            ):
                r.snapshot()
            with patch.object(r,"remote",return_value=post()),patch.object(
                r,"public_page",return_value=NEW_PUBLIC
            ),patch.object(r,"wp_request") as writer:
                with self.assertRaisesRegex(PublishError,"Prewrite public canonical"):
                    r.deploy()
                writer.assert_not_called()

    def test_write_timeout_not_retried_or_claimed_success(self):
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"snapshot.json"
        ):
            with patch.object(r,"remote",return_value=post()),patch.object(
                r,"public_page",return_value=PUBLIC_OLD
            ):
                r.snapshot()
            with patch.object(r,"remote",side_effect=[post(),post()]),patch.object(
                r,"public_page",return_value=PUBLIC_OLD
            ),patch.object(r,"normalized_base",return_value="https://xfit.cz"),patch.object(
                r,"wp_request",side_effect=PublishError("POST transport timeout")
            ) as writer:
                with self.assertRaisesRegex(PublishError,"mismatch"):
                    r.deploy()
                writer.assert_called_once()

    def test_already_applied_is_idempotent_zero_write(self):
        done=post(body=r.reviewed())
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"snapshot.json"
        ):
            with patch.object(r,"remote",return_value=done):
                r.snapshot()
            with patch.object(r,"remote",return_value=done),patch.object(
                r,"public_page",return_value=NEW_PUBLIC
            ),patch.object(r,"verify_public") as public,patch.object(
                r,"wp_request"
            ) as writer:
                r.deploy()
                writer.assert_not_called()
                public.assert_called_once_with(r.URL,TITLE,r.reviewed())


if __name__=="__main__":
    unittest.main()
