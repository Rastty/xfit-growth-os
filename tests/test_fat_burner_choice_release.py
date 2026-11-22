"""Existing fat-burner buying page: source-locked, evidence-led onepost rescue."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import xfit_fat_burner_choice_release as r
from scripts.wp_publish import PublishError

OLD_TITLE="Jak vybrat ten správný spalovač tuků pro vaše fitness cíle?"
OLD_HTML=(
    '<h2>Jak vybrat ten správný spalovač tuků pro vaše fitness cíle?</h2>'
    '<p>Spalovače tuků mohou být užitečné při snižování tělesného tuku.</p>'
    '<h2>Jak vybrat ten správný spalovač tuků pro vaše fitness cíle?</h2>'
    '<p>Nejlepší spalovače tuků obsahují yohimbe kůru a kofein. '
    'Doporučujeme Lipo 6 Black Ultra Concentrate.</p>'
    + "<p>Staré doporučení včetně kódu 5NM2022 nemělo nezávislou metodiku.</p>"*18
)

def post(body=OLD_HTML, **change):
    data={"id":7445,"slug":r.SLUG,"status":"publish","link":r.URL,
          "title":{"raw":OLD_TITLE},"content":{"raw":body},
          "modified_gmt":"2023-05-01T14:00:00","featured_media":17}
    data.update(change)
    return data


class FatBurnerOnepostTests(unittest.TestCase):
    def test_reviewed_source_is_unique_safe_and_noncommercial(self):
        html=r.reviewed_body()
        self.assertTrue(r.revised(html))
        self.assertIn("nekoupit nic",r.visible(html))
        self.assertIn("yohimbe",r.visible(html))
        self.assertIn("těhotenství a kojení",r.visible(html))
        self.assertNotIn("5NM2022",html)
        self.assertNotIn("href=\"https://www.namaximum.cz",html)
        self.assertNotIn("Lipo 6 Black",html)
        self.assertEqual(html.count("<h2>"),6)
        for link in r.EVIDENCE_URLS+r.INTERNAL_URLS:
            self.assertEqual(html.count(link),1)

    def test_legacy_source_and_title_must_match(self):
        self.assertEqual(r.source_state(post())[0],"needs_revision")
        for changed in (
            post(id="7445"),post(slug="other"),post(status="draft"),
            post(link="https://xfit.cz/other/"),
            post(title={"raw":"Fitness"}),
            post(modified_gmt="bad"),post(featured_media=None),
            post(body="<p>Too short</p>"),
            post(body=OLD_HTML.replace("Lipo 6 Black Ultra Concentrate",
                                       "Nehodnocený produkt")),
            post(body=OLD_HTML.replace("yohimbe kůru","bezpečnou variantu")),
            post(body=OLD_HTML.replace("Jak vybrat ten správný","Jak vybrat jiný")),
        ):
            with self.subTest(changed=changed.get("slug")):
                with self.assertRaises(PublishError):
                    r.source_state(changed)
        with self.assertRaises(PublishError):
            r.source_identity(post(id=7446),expected_id=7445)

    def test_freeze_discovery_rejects_zero_or_multiple(self):
        with patch.object(r,"wp_request",side_effect=[
            [],[post(),post()]
        ]),patch.object(r,"normalized_base",return_value="https://xfit.cz"):
            with self.assertRaises(PublishError):r.discover()
            with self.assertRaises(PublishError):r.discover()

    def test_full_original_snapshot_before_one_content_only_post(self):
        old=post()
        newer=post(body=r.reviewed_body(),
                   modified_gmt="2026-11-22T11:31:01")
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"rollback.json"
        ):
            with patch.object(r,"discover",return_value=old):
                r.snapshot()
            record=json.loads(r.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(record["original_raw"],OLD_HTML)
            self.assertEqual(record["original_title"],OLD_TITLE)
            self.assertEqual(record["post_id"],7445)
            self.assertEqual(record["featured_media"],17)
            self.assertEqual(record["remote_writes"],0)
            with patch.object(r,"remote",side_effect=[old,newer]),patch.object(
                r,"normalized_base",return_value="https://xfit.cz"
            ),patch.object(r,"wp_request",return_value={"id":7445,
                           "status":"publish"}) as writer,patch.object(
                r,"verify_public"
            ) as proof:
                r.deploy()
                writer.assert_called_once()
                self.assertEqual(writer.call_args.kwargs["payload"],
                                 {"content":r.reviewed_body()})
                proof.assert_called_once_with(r.URL,OLD_TITLE,r.reviewed_body())

    def test_concurrent_editor_blocks_write(self):
        old=post()
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"rollback.json"
        ):
            with patch.object(r,"discover",return_value=old):r.snapshot()
            with patch.object(r,"remote",return_value=post(
                modified_gmt="2026-11-22T11:31:01"
            )),patch.object(r,"wp_request") as writer:
                with self.assertRaisesRegex(PublishError,"Concurrent edit"):
                    r.deploy()
                writer.assert_not_called()

    def test_uncertain_single_post_no_retry(self):
        old=post()
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"rollback.json"
        ):
            with patch.object(r,"discover",return_value=old):r.snapshot()
            with patch.object(r,"remote",side_effect=[old,old]),patch.object(
                r,"normalized_base",return_value="https://xfit.cz"
            ),patch.object(r,"wp_request",side_effect=PublishError(
                "POST timeout"
            )) as writer,patch.object(r,"verify_public") as proof:
                with self.assertRaisesRegex(PublishError,
                                             "auth readback did not match"):
                    r.deploy()
                writer.assert_called_once()
                proof.assert_not_called()

    def test_already_revised_source_no_wp_post(self):
        ready=post(body=r.reviewed_body())
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"rollback.json"
        ):
            with patch.object(r,"discover",return_value=ready):r.snapshot()
            with patch.object(r,"remote",return_value=ready),patch.object(
                r,"wp_request"
            ) as writer,patch.object(r,"verify_public") as proof:
                r.deploy()
                writer.assert_not_called()
                proof.assert_called_once()


if __name__=="__main__":
    unittest.main()
