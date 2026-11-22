"""Fail-closed contract for evidence-led replacement of one unsafe Black Mamba page."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import xfit_black_mamba_safety_release as r
from scripts.wp_publish import PublishError

OLD_TITLE = "Black mamba – co to je"
OLD_HTML = (
    '<p>Black mamba může rychle zhubnout i bez cvičení.</p>'
    '<p>Směs Sida Cordifolia obsahuje efedrin v dávce bezpečné pro tělo, '
    'při správném použití nezpůsobují vedlejší účinky. '
    'Podle staré reklamy zrychluje metabolismus o 22 %.</p>'
    '<p><a href="https://us-supplements.to/black-mamba/">Koupit Black Mamba</a></p>'
    + "<p>Dřívější nezávisle neověřené marketingové doporučení.</p>" * 20
)


def post(body=OLD_HTML, **changes):
    old = {
        "id": 9187, "slug": r.SLUG, "status": "publish", "link": r.URL,
        "title": {"raw": OLD_TITLE}, "content": {"raw": body},
        "modified_gmt": "2022-12-12T12:15:00", "featured_media": 0,
    }
    old.update(changes)
    return old


class BlackMambaReleaseTests(unittest.TestCase):
    def test_reviewed_safety_source_is_substantive_noncommercial_and_cited(self):
        source = r.reviewed_body()
        self.assertTrue(r.revised(source))
        self.assertIn("nekoupit", r.visible(source))
        self.assertIn("těhotenství a kojení", r.visible(source))
        self.assertIn("bez nezávislého", r.visible(
            "<p>bez nezávislého</p>"))
        self.assertNotIn("us-supplements.to", source)
        self.assertNotIn("5nm2022", source.casefold())
        self.assertNotIn("<script", source.casefold())
        for url in r.EVIDENCE_URLS + r.INTERNAL_URLS:
            self.assertEqual(source.count(url), 1)
        self.assertEqual(source.count("<h2>"), 6)

    def test_legacy_signature_and_unverified_merchant_are_required(self):
        self.assertEqual(r.source_state(post())[0], "needs_revision")
        candidates = [
            post(id=5), post(id="9187"), post(slug="other"),
            post(status="draft"), post(link="https://xfit.cz/other/"),
            post(title={"raw": "Nebezpečný článek"}),
            post(modified_gmt="unknown"),
            post(featured_media="bad"),
            post(body="<p>Text</p>"),
            post(body=OLD_HTML.replace("22 %", "31 %")),
            post(body=OLD_HTML.replace("us-supplements.to", "valid.example")),
        ]
        for candidate in candidates:
            with self.subTest(candidate=candidate.get("slug")):
                with self.assertRaises(PublishError):
                    r.source_state(candidate)

    def test_discover_only_exact_published_slug(self):
        with patch.object(r, "wp_request",side_effect=[
            [],[post(),post()], [post(slug="other")],
        ]),patch.object(r, "normalized_base",return_value="https://xfit.cz"):
            for _ in range(3):
                with self.assertRaises(PublishError):
                    r.discover()

    def test_snapshot_is_immutable_full_original_metadata_no_post(self):
        with TemporaryDirectory() as d, patch.object(
            r, "BACKUP", Path(d)/"rollback.json"
        ),patch.object(r,"discover",return_value=post()),patch.object(
            r,"wp_request"
        ) as writer:
            r.snapshot()
            record=json.loads(r.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(record["post_id"],9187)
            self.assertEqual(record["original_raw"],OLD_HTML)
            self.assertEqual(record["original_title"],OLD_TITLE)
            self.assertEqual(record["featured_media"],0)
            self.assertEqual(record["remote_writes"],0)
            self.assertEqual(record["mode"],"needs_revision")
            writer.assert_not_called()
            with self.assertRaisesRegex(PublishError,"already exists"):
                r.snapshot()

    def test_one_content_only_post_followed_by_authenticated_and_public_proof(self):
        old=post()
        new=post(body=r.reviewed_body(),
                 modified_gmt="2026-11-22T10:33:01")
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"rollback.json"
        ):
            with patch.object(r,"discover",return_value=old):
                r.snapshot()
            with patch.object(r,"remote",side_effect=[old,new]),patch.object(
                r,"normalized_base",return_value="https://xfit.cz"
            ),patch.object(r,"wp_request",return_value={
                "id":9187,"status":"publish"
            }) as writer,patch.object(r,"verify_public") as public:
                r.deploy()
                writer.assert_called_once()
                self.assertEqual(writer.call_args.kwargs["payload"],
                                 {"content":r.reviewed_body()})
                public.assert_called_once_with(r.URL,OLD_TITLE,r.reviewed_body())

    def test_concurrent_editor_prevents_any_wp_write(self):
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"rollback.json"
        ):
            with patch.object(r,"discover",return_value=post()):
                r.snapshot()
            with patch.object(r,"remote",return_value=post(
                modified_gmt="2026-11-22T10:33:01"
            )),patch.object(r,"wp_request") as writer:
                with self.assertRaisesRegex(PublishError,"Concurrent edit"):
                    r.deploy()
                writer.assert_not_called()

    def test_uncertain_post_never_retried_or_reported_success(self):
        old=post()
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"rollback.json"
        ):
            with patch.object(r,"discover",return_value=old):
                r.snapshot()
            with patch.object(r,"remote",side_effect=[old,old]),patch.object(
                r,"normalized_base",return_value="https://xfit.cz"
            ),patch.object(r,"wp_request",side_effect=PublishError(
                "write timeout"
            )) as writer,patch.object(r,"verify_public") as public:
                with self.assertRaisesRegex(PublishError,"auth readback did not match"):
                    r.deploy()
                writer.assert_called_once()
                public.assert_not_called()

    def test_already_correct_page_remains_noop(self):
        old=post(body=r.reviewed_body())
        with TemporaryDirectory() as d,patch.object(
            r,"BACKUP",Path(d)/"rollback.json"
        ):
            with patch.object(r,"discover",return_value=old):
                r.snapshot()
            with patch.object(r,"remote",return_value=old),patch.object(
                r,"wp_request"
            ) as writer,patch.object(r,"verify_public") as public:
                r.deploy()
                writer.assert_not_called()
                public.assert_called_once_with(r.URL,OLD_TITLE,r.reviewed_body())


if __name__=="__main__":
    unittest.main()
