"""Evidence-backed existing creatine beginner page: source lease, no duplicate, no retry."""
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import xfit_creatine_beginners_onepost as b
from scripts.wp_publish import PublishError


def original_body():
    return (
        "<p>Starší úvod o kreatinu pro začátečníky, cvičení a sportu.</p>" * 35 +
        "<p>Začátečníci mohou po tréninku zvážit doplněk.</p>" +
        "<p>Některé starší články uvádí 20-30g kreatinu, "
        "po dobu delší než 8 týdnů a ihned po tréninku.</p>"
    )


def post(raw=None, title=b.OLD_TITLE, slug=b.SLUG, id=14567,
         modified="2023-05-15T12:00:00", status="publish"):
    return {
        "id": id, "slug": slug, "status": status, "link": b.URL,
        "title": {"raw": title}, "content": {"raw": original_body() if raw is None else raw},
        "excerpt": {"raw": "Původní shrnutí kreatinu."}, "modified_gmt": modified,
    }


class BeginnerCreatineEvidenceTests(unittest.TestCase):
    def test_replacement_is_useful_and_cannot_carry_unknown_links(self):
        content, excerpt = b.approved_document()
        self.assertGreater(len(content), 6000)
        self.assertLess(len(excerpt), 300)
        self.assertEqual(b.editorial_links(content), b.EXPECTED_LINKS)
        self.assertNotIn("a_aid=", content)
        self.assertNotIn("<h1", content)
        self.assertIn("není podmínkou", content)
        self.assertIn("Výběr bez nákupu", content)
        self.assertIn("3–5 g", content)

    def test_identity_exact_source_cardinality_and_slug(self):
        p, raw, title, excerpt = b.identity([post()])
        self.assertEqual(p["id"], 14567)
        self.assertEqual(title, b.OLD_TITLE)
        self.assertEqual(raw, original_body())
        for bad in ([], [post(), post(id=14568)],
                    [post(slug="other")], [post(status="draft")],
                    [post(id=0)], [post(raw="too short")]):
            with self.subTest(bad=str(bad)[:50]), self.assertRaises(PublishError):
                b.identity(bad)

    def test_diagnosis_is_get_only_and_redacted(self):
        raw = original_body()
        out = StringIO()
        with contextlib.redirect_stdout(out):
            row = b.diagnosis(rows=[post()])
        self.assertEqual(row["raw_sha256"], b.sha(raw))
        self.assertTrue(row["title_exact_reviewed_old"])
        self.assertEqual(row["wordpress_writes"], 0)
        self.assertFalse(row["release_approved"])
        self.assertNotIn("Starší úvod", out.getvalue())
        self.assertNotIn("Původní shrnutí", out.getvalue())

    def test_no_publication_when_source_not_pinned(self):
        new, excerpt = b.approved_document()
        with self.assertRaisesRegex(PublishError, "not yet pinned"):
            b.checked_existing([post()], new, excerpt)

    def test_only_exact_pinned_post_eligible_and_concurrent_drift_blocks(self):
        new, excerpt = b.approved_document()
        old = original_body()
        with patch.object(b, "PINNED_POST_ID", 14567), \
             patch.object(b, "PINNED_SOURCE_LENGTH", len(old)), \
             patch.object(b, "PINNED_SOURCE_SHA256", b.sha(old)):
            self.assertEqual(b.checked_existing([post()], new, excerpt)[1], "update")
            for changed in [post(raw=old+"<p>Editor updated text.</p>"),
                            post(title="Different title"), post(id=14568)]:
                with self.assertRaises(PublishError):
                    b.checked_existing([changed], new, excerpt)

    def test_snapshot_and_apply_once_full_source_backup_before_post(self):
        old = original_body()
        updated, ex = b.approved_document()
        original = post()
        final = post(raw=updated, title=b.NEW_TITLE)
        final["excerpt"]["raw"] = ex
        final["modified_gmt"] = "2026-11-21T10:30:00"
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(b, "PINNED_POST_ID", 14567), \
             patch.object(b, "PINNED_SOURCE_LENGTH", len(old)), \
             patch.object(b, "PINNED_SOURCE_SHA256", b.sha(old)), \
             patch.object(b, "BACKUP", Path(tmp)/"backup.json"):
            with patch.object(b, "source_get", return_value=[original]):
                b.snapshot()
            saved = json.loads(b.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(saved["before"]["raw"], old)
            self.assertEqual(saved["before"]["title"], b.OLD_TITLE)
            self.assertEqual(saved["mode"], "update")
            with patch.object(b, "source_get", side_effect=[[original], [final]]), \
                 patch.object(b, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(b, "wp_request", return_value={"id":14567}) as writer, \
                 patch.object(b, "verify_public", return_value=True) as verifier:
                b.apply()
            writer.assert_called_once()
            verifier.assert_called_once_with(b.URL, b.NEW_TITLE, updated)
            self.assertEqual(writer.call_args.kwargs["payload"]["title"], b.NEW_TITLE)

    def test_uncertain_post_never_retried_and_drift_prior_write_refused(self):
        old = original_body()
        approved, ex = b.approved_document()
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(b, "PINNED_POST_ID", 14567), \
             patch.object(b, "PINNED_SOURCE_LENGTH", len(old)), \
             patch.object(b, "PINNED_SOURCE_SHA256", b.sha(old)), \
             patch.object(b, "BACKUP", Path(tmp)/"backup.json"):
            with patch.object(b, "source_get", return_value=[post()]):
                b.snapshot()
            with patch.object(b, "source_get",
                              side_effect=[[post()],[post()]]), \
                 patch.object(b, "wp_request", side_effect=PublishError("timeout")) as writer, \
                 patch.object(b, "normalized_base", return_value="https://xfit.cz"):
                with self.assertRaisesRegex(PublishError, "Write not proved"):
                    b.apply()
            writer.assert_called_once()
            with patch.object(b, "source_get", return_value=[post(modified="2026-11-20T10:00:00")]), \
                 patch.object(b, "wp_request") as writer:
                with self.assertRaisesRegex(PublishError, "Another editor"):
                    b.apply()
            writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
