"""Guard exact one-URL evidence rescue, immutable rollback and no retries."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import xfit_creatine_safety_2212_revision as r
from scripts.wp_publish import PublishError


OLD_TITLE = "Bezpečnostní aspekty kreatinu monohydrátu a jak minimalizovat rizika"
OLD_RAW = (
    '<h2>Bezpečnostní aspekty kreatinu monohydrátu</h2>'
    '<p>Bezpečnostní aspekty kreatinu monohydrátu a jak minimalizovat rizika. '
    'Staré slevové kódy 5NM2022, 5NM2022 a 5NM2022 jsou zde '
    'uvedené bez ověření, a článek se mnohokrát opakuje.</p>' * 33
)


def post(raw=OLD_RAW, modified="2023-04-15T08:30:00", **kwargs):
    result = {
        "id": r.POST_ID, "slug": r.SLUG, "status": "publish",
        "link": r.URL,
        "title": {"raw": OLD_TITLE},
        "modified_gmt": modified, "featured_media": 789,
        "content": {"raw": raw},
    }
    result.update(kwargs)
    return result


class CreatineSafetyReviewTests(unittest.TestCase):
    def test_substantive_source_and_noncommercial_evidence(self):
        body = r.reviewed_body()
        self.assertTrue(r.revised(body))
        self.assertIn("nekupovat", r.visible(body))
        self.assertNotIn("5nm2022", body.casefold())
        self.assertNotIn("[su_button", body)
        self.assertEqual(body.count("<h2>"), 7)
        for url in r.REQUIRED_EVIDENCE_URLS + r.OWNED_HANDOFFS:
            self.assertEqual(body.count(url), 1)
        self.assertNotIn("href=\"https://www.namaximum.cz", body)
        self.assertNotIn("href=\"https://namaximum.cz", body)

    def test_identity_and_concurrent_drift_fail_closed(self):
        self.assertEqual(r.source_state(post())[0], "needs_revision")
        changed = [
            post(id=2), post(slug="incorrect"), post(status="draft"),
            post(link="https://xfit.cz/other/"),
            post(modified=""), post(featured_media=None),
            post(title={"raw": "Protein a cena"}),
            post(raw="<p>Short</p>"),
            post(raw=OLD_RAW.replace("5NM2022", "NEW2026")),
            post(raw=OLD_RAW.replace("Bezpečnostní aspekty", "Jiné téma")),
        ]
        for case in changed:
            with self.subTest(case=case.get("slug")):
                with self.assertRaises(PublishError):
                    r.source_state(case)

    def test_backup_full_original_before_single_content_post(self):
        before = post()
        after_html = r.reviewed_body()
        after = post(raw=after_html, modified="2026-11-22T11:11:11")
        with TemporaryDirectory() as temp, patch.object(
                r, "BACKUP", Path(temp) / "rollback.json"):
            with patch.object(r, "remote", return_value=before):
                r.snapshot()
            backup = json.loads(r.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(backup["original_raw"], OLD_RAW)
            self.assertEqual(backup["original_title"], OLD_TITLE)
            self.assertEqual(backup["remote_writes"], 0)
            self.assertEqual(backup["post_id"], 2212)
            self.assertEqual(backup["featured_media"], 789)
            self.assertEqual(backup["mode"], "needs_revision")
            with patch.object(r, "remote", side_effect=[before, after]), \
                 patch.object(r, "normalized_base",
                              return_value="https://xfit.cz"), \
                 patch.object(r, "wp_request",
                              return_value={"id": 2212, "status": "publish"}) as wp, \
                 patch.object(r, "verify_public") as public:
                r.deploy()
                wp.assert_called_once()
                self.assertEqual(wp.call_args.kwargs["payload"],
                                 {"content": after_html})
                public.assert_called_once_with(r.URL, OLD_TITLE, after_html)

    def test_race_guard_does_not_try_wp_write(self):
        with TemporaryDirectory() as temp, patch.object(
                r, "BACKUP", Path(temp) / "rollback.json"):
            with patch.object(r, "remote", return_value=post()):
                r.snapshot()
            with patch.object(r, "remote",
                              return_value=post(modified="2026-11-22T11:11:11")), \
                 patch.object(r, "wp_request") as writer:
                with self.assertRaisesRegex(PublishError, "Concurrent"):
                    r.deploy()
                writer.assert_not_called()

    def test_idempotent_existing_repair_is_noop(self):
        already = post(raw=r.reviewed_body())
        with TemporaryDirectory() as temp, patch.object(
                r, "BACKUP", Path(temp) / "rollback.json"):
            with patch.object(r, "remote", return_value=already):
                r.snapshot()
            with patch.object(r, "remote", return_value=already), \
                 patch.object(r, "wp_request") as writer, \
                 patch.object(r, "verify_public") as public:
                r.deploy()
                writer.assert_not_called()
                public.assert_called_once()

    def test_failed_single_post_no_retry_or_false_success(self):
        before = post()
        with TemporaryDirectory() as temp, patch.object(
                r, "BACKUP", Path(temp) / "rollback.json"):
            with patch.object(r, "remote", return_value=before):
                r.snapshot()
            with patch.object(r, "remote", side_effect=[before, before]), \
                 patch.object(r, "normalized_base",
                              return_value="https://xfit.cz"), \
                 patch.object(r, "wp_request",
                              side_effect=PublishError("write timeout")) as writer, \
                 patch.object(r, "verify_public") as public:
                with self.assertRaisesRegex(PublishError,
                                            "content or identity differs"):
                    r.deploy()
                writer.assert_called_once()
                public.assert_not_called()


if __name__ == "__main__":
    unittest.main()
