"""Fail-closed contract for replacing an unsafe homepage-promoted booster list."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.wp_publish import PublishError
from scripts import xfit_testosterone_legacy_revision as r


OLD_TITLE = "Přípravky na zvýšení hladiny testosteronu – srovnání pro rok 2025"
OLD_BODY = ("<h2>Stimulátory testosteronu</h2>"
            "<p>Prime Male, Testo Fuel, ProMan Plus a Primulus "
            "jsou nejlepší produkty se skóre 95 % bez nežádoucích účinků.</p>" * 15)
MODIFIED = "2025-10-12T09:11:22"
POST_ID = 928


def post(body=OLD_BODY, title=OLD_TITLE, **kwargs):
    result = {"id": POST_ID, "slug": r.SLUG, "status": "publish",
              "link": r.URL, "modified_gmt": MODIFIED,
              "content": {"raw": body}, "title": {"raw": title},
              "featured_media": 321}
    result.update(kwargs)
    return result


class OneLegacyPostOnly(unittest.TestCase):
    def test_safe_article_is_substantive_and_uncommercial(self):
        body = r.reviewed_body()
        self.assertTrue(r.revised(body))
        self.assertIn("nekoupit nic", r.visible(body))
        self.assertIn("endocrine.org", body)
        self.assertIn("ods.od.nih.gov", body)
        self.assertNotIn("<script", body)
        for product in r.OLD_PRODUCT_MARKERS:
            self.assertNotIn(product, r.visible(body))
        self.assertNotIn("rel=\"sponsored\"", body)

    def test_old_pinned_url_title_and_products_must_match(self):
        self.assertEqual(r._legacy(post())[1], OLD_TITLE)
        mutations = [
            post(id=0), post(id="928"), post(slug="other"),
            post(link="https://xfit.cz/other/"), post(status="draft"),
            post(modified_gmt="unknown"), post(featured_media=None),
            post(title={"raw": "Moderní trénink"}),
            post(body=OLD_BODY.replace("Primulus", "MissingBrand")),
            post(body="<p>short</p>"),
        ]
        for item in mutations:
            with self.subTest(item=item.get("id")):
                with self.assertRaises(PublishError):
                    r._legacy(item)

    def test_discovery_rejects_missing_and_multiple_posts(self):
        with patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
             patch.object(r, "wp_request", side_effect=[[post(), post()], []]):
            with self.assertRaises(PublishError):
                r.discover()
            with self.assertRaises(PublishError):
                r.discover()

    def test_snapshot_is_full_and_does_not_post(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(r, "BACKUP", Path(directory) / "backup.json"), \
                 patch.object(r, "discover", return_value=post()), \
                 patch.object(r, "wp_request") as writer:
                r.snapshot()
                record = json.loads(r.BACKUP.read_text(encoding="utf-8"))
                self.assertEqual(record["post_id"], POST_ID)
                self.assertEqual(record["original_raw"], OLD_BODY)
                self.assertEqual(record["original_title"], OLD_TITLE)
                self.assertEqual(record["featured_media"], 321)
                self.assertEqual(record["remote_writes"], 0)
                writer.assert_not_called()
                with self.assertRaises(PublishError):
                    r.snapshot()

    def test_deploy_attempts_one_post_and_checks_public_body(self):
        body = r.reviewed_body()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(r, "BACKUP", Path(directory) / "backup.json"), \
                 patch.object(r, "discover", return_value=post()), \
                 patch.object(r, "by_id", side_effect=[post(), post(body, r.TITLE)]), \
                 patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(r, "wp_request", return_value={"id": POST_ID}) as writer, \
                 patch.object(r, "verify_public", return_value=True) as public:
                r.snapshot()
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    r.deploy()
                self.assertIn('"state": "PUBLIC_VERIFIED"', output.getvalue())
                writer.assert_called_once_with("https://xfit.cz", f"posts/{POST_ID}",
                    payload={"content": body, "title": r.TITLE})
                public.assert_called_once_with(r.URL, r.TITLE, body)

    def test_source_drift_aborts_before_post(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(r, "BACKUP", Path(directory) / "backup.json"), \
                 patch.object(r, "discover", return_value=post()), \
                 patch.object(r, "by_id", return_value=post(modified_gmt="2026-11-17T19:15:00")), \
                 patch.object(r, "wp_request") as writer:
                r.snapshot()
                with self.assertRaises(PublishError):
                    r.deploy()
                writer.assert_not_called()

    def test_ambiguous_post_is_not_repeated(self):
        body = r.reviewed_body()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(r, "BACKUP", Path(directory) / "backup.json"), \
                 patch.object(r, "discover", return_value=post()), \
                 patch.object(r, "by_id", side_effect=[post(), post(body, r.TITLE)]), \
                 patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(r, "wp_request", side_effect=PublishError("timeout")) as writer, \
                 patch.object(r, "verify_public", return_value=True):
                r.snapshot()
                r.deploy()
                self.assertEqual(writer.call_count, 1)

    def test_stale_api_body_is_never_accepted_as_live(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(r, "BACKUP", Path(directory) / "backup.json"), \
                 patch.object(r, "discover", return_value=post()), \
                 patch.object(r, "by_id", side_effect=[post(), post()]), \
                 patch.object(r, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(r, "wp_request", return_value={"id": POST_ID}) as writer, \
                 patch.object(r, "verify_public") as public:
                r.snapshot()
                with self.assertRaises(PublishError):
                    r.deploy()
                self.assertEqual(writer.call_count, 1)
                public.assert_not_called()


if __name__ == "__main__":
    unittest.main()
