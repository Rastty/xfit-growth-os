"""Onepost creatine disadvantages factual correction, no remote writes in tests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import xfit_creatine_disadvantages_onepost as revision
from scripts.wp_publish import PublishError


def original_body():
    return (
        "<h2>Kreatin a jeho nevýhody</h2>" +
        "<p>Stručně popisujeme původní článek a jeho výhody.</p>" * 32 +
        "<p>Kreatin může způsobit dehydrataci. Někteří autoři uvádějí "
        "zvýšený krevní tlak a krční křeče bez odborného doložení.</p>"
    )


def post(*, raw=None, title=None, excerpt="Původní odstavec o kreatinu.",
         modified="2023-11-07T12:00:00", slug=revision.SLUG,
         status="publish", post_id=11304, link=revision.URL):
    return {
        "id": post_id, "slug": slug, "status": status, "link": link,
        "title": {"raw": revision.OLD_TITLE if title is None else title},
        "excerpt": {"raw": excerpt},
        "content": {"raw": original_body() if raw is None else raw},
        "modified_gmt": modified,
    }


class CreatineDisadvantagesOnepostTests(unittest.TestCase):
    def setUp(self):
        # Production pin remains immutable. Synthetic fixtures must pin their
        # own exact raw source to exercise logic without remote access.
        self.sha_guard = patch.object(revision, "PINNED_SOURCE_SHA256",
                                      revision.sha(original_body()))
        self.len_guard = patch.object(revision, "PINNED_ORIGINAL_LENGTH",
                                      len(original_body()))
        self.sha_guard.start()
        self.len_guard.start()
        self.addCleanup(self.len_guard.stop)
        self.addCleanup(self.sha_guard.stop)

    def test_production_source_pin_is_exact_and_single_post(self):
        # This test uses literal pin independently of the fixture overrides.
        self.assertEqual(revision.PINNED_POST_ID, 11304)
        self.assertEqual(len(revision.PINNED_SOURCE_SHA256), 64)
        self.assertEqual(revision.PINNED_ORIGINAL_LENGTH, len(original_body()))

    def test_replacement_is_evidence_backed_not_product_pitch(self):
        content = revision.reviewed_document()
        self.assertTrue(content.startswith("<div "))
        self.assertGreater(len(content), 4000)
        self.assertIn("nemusíte kupovat nic", content.casefold())
        self.assertIn("studie nepodporují", content)
        self.assertIn("není nezbytný", content)
        self.assertIn("Operation Supplement Safety", content)
        self.assertIn("NIH Office of Dietary Supplements", content)
        self.assertNotIn("a_aid=", content)
        self.assertNotIn("<h1", content)
        self.assertEqual(revision.editorial_links(content),
                         list(revision.APPROVED_LINKS))

    def test_old_post_strict_identity_and_outdated_content(self):
        post_ok, mode = revision.classify([post()])
        self.assertEqual(mode, "update")
        self.assertEqual(post_ok["id"], 11304)
        new = revision.reviewed_document()
        new_doc, mode = revision.classify([post(raw=new,
                                                title=revision.NEW_TITLE,
                                                excerpt=revision.EXCERPT)],
                                          new_body=new)
        self.assertEqual(mode, "already_applied")
        self.assertEqual(new_doc["id"], 11304)

    def test_no_update_when_source_ambiguous_or_editor_changed(self):
        cases = (
            [], [post(), post(post_id=10904)], [post(status="draft")],
            [post(slug="another")], [post(link="https://elsewhere.example/a/")],
            [post(raw=original_body().replace("zvýšený krevní tlak", "nové tvrzení"))],
            [post(raw=original_body() + "<!DOCTYPE html><html></html>")],
            [post(raw=original_body() + "<script>alert(1)</script>")],
            [post(title="Another editor already changed this")],
            [post(raw="Text too short")],
        )
        for row in cases:
            with self.subTest(row=str(row)[:60]), self.assertRaises(PublishError):
                revision.classify(row)

    def test_live_already_applied_must_be_complete(self):
        html = revision.reviewed_document()
        with self.assertRaises(PublishError):
            revision.classify([post(title=revision.NEW_TITLE)], new_body=html)
        with self.assertRaises(PublishError):
            revision.classify([post(raw=html.replace("https://ods.od.nih.gov/",
                         "https://wrong.example/"), title=revision.NEW_TITLE,
                         excerpt=revision.EXCERPT)], new_body=html)

    def test_snapshot_preserves_whole_original_source_before_write(self):
        original = post()
        with tempfile.TemporaryDirectory() as td, \
             patch.object(revision, "BACKUP", Path(td)/"original.json"), \
             patch.object(revision, "source_get", return_value=[original]), \
             patch.object(revision, "verify_existing_public", return_value=True):
            revision.snapshot()
            saved = json.loads(revision.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(saved["prewrite"]["original_raw"], original_body())
            self.assertEqual(saved["prewrite"]["title"], revision.OLD_TITLE)
            self.assertEqual(saved["prewrite"]["excerpt"], original["excerpt"]["raw"])
            self.assertEqual(saved["remote_writes"], 0)
            with self.assertRaisesRegex(PublishError, "cannot be overwritten"):
                revision.snapshot()

    def test_full_release_uses_exactly_one_post_then_auth_and_public_checks(self):
        original = post()
        updated = post(raw=revision.reviewed_document(),
                       title=revision.NEW_TITLE, excerpt=revision.EXCERPT,
                       modified="2026-11-21T13:00:00")
        with tempfile.TemporaryDirectory() as td, \
             patch.object(revision, "BACKUP", Path(td)/"original.json"):
            with patch.object(revision, "source_get", return_value=[original]), \
                 patch.object(revision, "verify_existing_public", return_value=True):
                revision.snapshot()
            with patch.object(revision, "source_get",
                              side_effect=[[original],[updated]]), \
                 patch.object(revision, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(revision, "wp_request", return_value={"id": 11304}) as writer, \
                 patch.object(revision, "validate_public_release", return_value=True) as public:
                revision.apply()
            writer.assert_called_once()
            self.assertEqual(writer.call_args.kwargs["payload"], {
                "title": revision.NEW_TITLE, "content": revision.reviewed_document(),
                "excerpt": revision.EXCERPT,
            })
            public.assert_called_once()

    def test_uncertain_post_can_be_confirmed_only_by_get_readback(self):
        original = post()
        updated = post(raw=revision.reviewed_document(),
                       title=revision.NEW_TITLE, excerpt=revision.EXCERPT)
        with tempfile.TemporaryDirectory() as td, \
             patch.object(revision, "BACKUP", Path(td)/"original.json"):
            with patch.object(revision, "source_get", return_value=[original]), \
                 patch.object(revision, "verify_existing_public", return_value=True):
                revision.snapshot()
            with patch.object(revision, "source_get", side_effect=[[original],[updated]]), \
                 patch.object(revision, "wp_request", side_effect=PublishError("timeout")) as writer, \
                 patch.object(revision, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(revision, "validate_public_release", return_value=True):
                revision.apply()
            writer.assert_called_once()

    def test_source_drift_after_snapshot_never_writes(self):
        original = post()
        drift = post(raw=original_body()+"<p>New independent editor paragraph.</p>",
                     modified="2026-11-21T12:00:00")
        with tempfile.TemporaryDirectory() as td, \
             patch.object(revision, "BACKUP", Path(td)/"original.json"):
            with patch.object(revision, "source_get", return_value=[original]), \
                 patch.object(revision, "verify_existing_public", return_value=True):
                revision.snapshot()
            with patch.object(revision, "source_get", return_value=[drift]), \
                 patch.object(revision, "wp_request") as writer:
                with self.assertRaisesRegex(PublishError, "changed between"):
                    revision.apply()
            writer.assert_not_called()

    def test_uncertain_post_and_missing_public_verification_never_retries(self):
        original = post()
        with tempfile.TemporaryDirectory() as td, \
             patch.object(revision, "BACKUP", Path(td)/"original.json"):
            with patch.object(revision, "source_get", return_value=[original]), \
                 patch.object(revision, "verify_existing_public", return_value=True):
                revision.snapshot()
            with patch.object(revision, "source_get", side_effect=[[original],[original]]), \
                 patch.object(revision, "wp_request", side_effect=PublishError("timeout")) as writer, \
                 patch.object(revision, "normalized_base", return_value="https://xfit.cz"):
                with self.assertRaisesRegex(PublishError, "not proven"):
                    revision.apply()
            writer.assert_called_once()

    def test_public_old_source_gate(self):
        html = "<html><h1>"+revision.OLD_TITLE+"</h1>" + (
            "<p>Kreatin a jeho nevýhody, dehydrataci a krevní tlak.</p></html>"
        )
        self.assertTrue(revision.verify_existing_public(reader=lambda _:html))
        self.assertFalse(revision.verify_existing_public(reader=lambda _:html.replace(
            revision.OLD_TITLE, "Unrelated page")))

    def test_workflow_one_source_slug_and_immutable_artifact(self):
        wf = Path(".github/workflows/xfit-creatine-disadvantages-onepost.yml").read_text(encoding="utf-8")
        self.assertIn("xfit_creatine_disadvantages_onepost snapshot", wf)
        self.assertIn("xfit_creatine_disadvantages_onepost apply", wf)
        self.assertIn("actions/upload-artifact@v4", wf)
        self.assertIn("if-no-files-found: error", wf)
        self.assertNotIn("schedule:", wf)
        self.assertNotIn("content/ready/", wf)


if __name__ == "__main__":
    unittest.main()
