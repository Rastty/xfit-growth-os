"""Fail-closed original WP #6331 safety rescue. No medical purchase advice."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import xfit_pregnancy_fatburner_6331_release as r
from scripts.wp_publish import PublishError

TITLE="Spalovače tuků v těhotenství a při kojení: Co je bezpečné a účinné?"
OLD=(
 "<h2>Spalovače tuků v těhotenství a při kojení</h2>"
 + "<p>Spalovače tuku v těhotenství a při kojení bez prověřených zdrojů "
   "se starým slevovým kódem 5NM2022.</p>"*35
)
HEAD='<link rel="canonical" href="'+r.URL+'" />'
PUBLIC_OLD='<html><head>'+HEAD+'</head><body>'+OLD+'</body></html>'
PUBLIC_NEW=('<html><head>'+HEAD+'</head><body><article>'
            +r.SOURCE.read_text(encoding="utf-8")+'</article></body></html>')


def post(body=OLD,**updates):
    result={"id":r.POST_ID,"slug":r.SLUG,"status":"publish","link":r.URL,
            "title":{"raw":TITLE},"content":{"raw":body},
            "modified_gmt":"2023-05-09T07:10:00","featured_media":7}
    result.update(updates)
    return result


class Pregnancy6331Tests(unittest.TestCase):
    def test_no_buy_source_is_substantial_sourced_and_noncommercial(self):
        source=r.reviewed()
        self.assertTrue(r.revised(source))
        self.assertEqual(source.count("<h2>"),6)
        self.assertIn("nekupujte žádný spalovač",r.visible(source))
        self.assertIn("při kojení",r.visible(source))
        self.assertIn("nekoupit nic",r.visible(source))
        self.assertNotIn("5NM2022",source)
        self.assertNotIn("namaximum.cz",source)
        self.assertEqual(r.canonical_links(source),[])
        for link in r.SOURCE_LINKS:
            self.assertEqual(source.count('href="'+link+'"'),1)

    def test_only_exact_original_wp_identity_accepted(self):
        self.assertEqual(r.classify(post())["mode"],"update")
        self.assertEqual(
            r.classify(post(body=r.reviewed()))["mode"],"already_applied")
        for value in (
            post(id=3),post(id="6331"),post(slug="different"),
            post(status="draft"),post(link="https://xfit.cz/other/"),
            post(title={"raw":"Fitmarket"}),
            post(modified_gmt=""),post(featured_media=None),
            post(content={"raw":"<p>Tiny</p>"})
        ):
            with self.subTest(value=value.get("slug")):
                with self.assertRaises(PublishError):
                    r.identity(value)

    def test_old_source_must_contain_real_pregnancy_and_promo_evidence(self):
        for bad in (
            OLD.replace("5NM2022","SLEVA"),
            OLD.replace("kojení","sportu"),
            OLD.replace("těhotenství","fitness"),
            OLD.replace("Spalovače","Výrobky").replace("Spalovače","Výrobky"),
        ):
            with self.subTest(bad=bad[:60]):
                with self.assertRaises(PublishError):
                    r.classify(post(body=bad))

    def test_self_canonical_public_identity_and_no_buy(self):
        self.assertTrue(r.public_before(PUBLIC_OLD))
        self.assertTrue(r.public_after(PUBLIC_NEW))
        self.assertFalse(r.public_after(PUBLIC_OLD))
        self.assertFalse(r.public_before(PUBLIC_OLD.replace(HEAD,"")))

    def test_full_immutable_original_snapshot_precedes_only_one_post(self):
        old=post()
        revised=post(body=r.reviewed(),modified_gmt="2026-11-22T12:10:00")
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"immutable.json"
        ):
            with patch.object(r,"remote",return_value=old),patch.object(
                r,"public_page",return_value=PUBLIC_OLD
            ),patch.object(r,"wp_request") as writer:
                r.snapshot()
                writer.assert_not_called()
            record=json.loads(r.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(record["original_raw"],OLD)
            self.assertEqual(record["original_title"],TITLE)
            self.assertEqual(record["original_media"],7)
            self.assertEqual(record["remote_writes"],0)
            with patch.object(r,"remote",side_effect=[old,revised]),patch.object(
                r,"public_page",side_effect=[PUBLIC_OLD,PUBLIC_NEW]
            ),patch.object(r,"normalized_base",return_value="https://xfit.cz"),patch.object(
                r,"wp_request",return_value={"id":6331,"status":"publish"}
            ) as writer,patch.object(r,"verify_public") as public:
                r.deploy()
                writer.assert_called_once()
                self.assertEqual(writer.call_args.kwargs["payload"],
                                 {"content":r.reviewed()})
                public.assert_called_once_with(r.URL,TITLE,r.reviewed())

    def test_concurrent_editor_prevents_any_wp_write(self):
        old=post()
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"immutable.json"
        ):
            with patch.object(r,"remote",return_value=old),patch.object(
                r,"public_page",return_value=PUBLIC_OLD
            ):
                r.snapshot()
            other=post(body=OLD+"<p>Other editor addition.</p>",
                       modified_gmt="2026-11-22T12:10:00")
            with patch.object(r,"remote",return_value=other),patch.object(
                r,"wp_request"
            ) as writer:
                with self.assertRaisesRegex(PublishError,"Concurrent"):
                    r.deploy()
                writer.assert_not_called()

    def test_public_changed_since_backup_blocks_write(self):
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"immutable.json"
        ):
            with patch.object(r,"remote",return_value=post()),patch.object(
                r,"public_page",return_value=PUBLIC_OLD
            ):
                r.snapshot()
            with patch.object(r,"remote",return_value=post()),patch.object(
                r,"public_page",return_value='<html><body>Uncertain source</body></html>'
            ),patch.object(r,"wp_request") as writer:
                with self.assertRaisesRegex(PublishError,"changed before write"):
                    r.deploy()
                writer.assert_not_called()

    def test_uncertain_post_does_not_retry_or_claim_success(self):
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"immutable.json"
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

    def test_already_applied_no_post(self):
        done=post(body=r.reviewed())
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"immutable.json"
        ):
            with patch.object(r,"remote",return_value=done):
                r.snapshot()
            with patch.object(r,"remote",return_value=done),patch.object(
                r,"public_page",return_value=PUBLIC_NEW
            ),patch.object(r,"verify_public") as public,patch.object(
                r,"wp_request"
            ) as writer:
                r.deploy()
                writer.assert_not_called()
                public.assert_called_once_with(r.URL,TITLE,r.reviewed())


if __name__=="__main__":
    unittest.main()
