"""Source-bound direct publish: no stale overwrite, zero WP POST on mismatch."""
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.wp_publish import (
    MARKER, PublishError, assert_prewrite_source, publish, validate_document,
)


def old_document():
    return validate_document({
        "slug": "xfit-os-kreatin-nebo-protein",
        "title": "Kreatin, nebo protein: rozhodování podle cíle",
        "excerpt": "Rozhodnutí bez zbytečného nákupu.",
        "wp_post_id": 25504,
        "content": (
            "<h2>Nejprve zjistěte, zda doplněk potřebujete</h2>"
            "<p>Pravidelný trénink, jídlo a spánek jsou prvním krokem."
            " <a href='https://xfit.cz/xfit-os-protein-guide/'>Přečíst průvodce.</a></p>"
            "<p>Pokud pokryjete bílkoviny běžnou stravou, nový prášek není nutný.</p>"
            "<p>Kreatin je jiná látka, která souvisí s opakovaným intenzivním výkonem.</p>"
        ),
    })


def live_post(old=None):
    old = old or old_document()
    return {
        "id": 25504, "slug": old["slug"], "status": "publish",
        "title": {"raw": old["title"]},
        "content": {"raw": old["content"]},
        "link": "https://xfit.cz/xfit-os-kreatin-nebo-protein/",
    }


class DirectPublishDriftTests(unittest.TestCase):
    def test_unmodified_previous_source_allows_a_guarded_post_and_readback(self):
        previous = old_document()
        new_doc = dict(previous, content=previous["content"] +
                       "<p>Porovnejte cenu až po vyjasnění skutečné potřeby.</p>")
        saved = {"id": 25504}
        read = live_post(new_doc)
        with patch("scripts.xfit_editorial_gate.check_document", return_value={"passed": True}), \
             patch("scripts.wp_publish.normalized_base", return_value="https://xfit.cz"), \
             patch("scripts.wp_publish.wp_request",
                   side_effect=[live_post(previous), saved, read]) as request, \
             patch("scripts.wp_publish.verify_public") as public:
            result = publish(new_doc, live=True, expected_previous=previous)
        self.assertEqual(result["state"], "live_verified")
        self.assertEqual(request.call_count, 3)
        self.assertEqual(request.call_args_list[1].kwargs["payload"]["status"], "publish")
        public.assert_called_once()

    def test_remote_editorial_change_aborts_before_any_post(self):
        previous = old_document()
        changed = live_post()
        changed["content"]["raw"] = changed["content"]["raw"].replace(
            "prvním krokem", "důležitou součástí rozhodování")
        with patch("scripts.xfit_editorial_gate.check_document", return_value={"passed": True}), \
             patch("scripts.wp_publish.normalized_base", return_value="https://xfit.cz"), \
             patch("scripts.wp_publish.wp_request", return_value=changed) as request:
            with self.assertRaisesRegex(PublishError, "changed outside previous Git"):
                publish(previous, live=True, expected_previous=previous)
        self.assertEqual(request.call_count, 1)
        self.assertNotIn("payload", request.call_args.kwargs)

    def test_affiliate_or_internal_destination_change_is_not_invisible(self):
        previous = old_document()
        changed = live_post()
        changed["content"]["raw"] = changed["content"]["raw"].replace(
            "https://xfit.cz/xfit-os-protein-guide/",
            "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/")
        with self.assertRaisesRegex(PublishError, "changed outside previous Git"):
            assert_prewrite_source(changed, previous)

    def test_title_change_is_guarded_even_with_same_article_text(self):
        previous = old_document()
        changed = live_post()
        changed["title"]["raw"] = "Jak bezpečně vybírat doplňky podle cíle"
        with self.assertRaisesRegex(PublishError, "changed outside previous Git"):
            assert_prewrite_source(changed, previous)

    def test_no_edit_context_raw_body_fails_closed(self):
        previous = old_document()
        changed = live_post()
        changed["content"] = {"rendered": previous["content"]}
        with self.assertRaisesRegex(PublishError, "Missing owned raw"):
            assert_prewrite_source(changed, previous)

    def test_new_ready_file_cannot_overwrite_existing_owned_page(self):
        with self.assertRaisesRegex(PublishError, "New-only"):
            assert_prewrite_source(live_post(), None, new_only=True)

    def test_existing_source_missing_wp_post_cannot_make_duplicate(self):
        with self.assertRaisesRegex(PublishError, "WP post is missing"):
            assert_prewrite_source(None, old_document())

    def test_brand_new_slug_can_create_only_when_absent(self):
        self.assertIsNone(assert_prewrite_source(None, None, new_only=True))

    def test_manual_draft_cannot_unpublish_live_guide(self):
        previous = old_document()
        with patch("scripts.xfit_editorial_gate.check_document", return_value={"passed": True}), \
             patch("scripts.wp_publish.normalized_base", return_value="https://xfit.cz"), \
             patch("scripts.wp_publish.wp_request",
                   return_value=live_post(previous)) as request:
            with self.assertRaisesRegex(PublishError, "downgrade"):
                publish(previous, live=False, expected_previous=previous)
        self.assertEqual(request.call_count, 1)

    def test_workflow_pins_previous_git_commit_and_new_file_mode(self):
        source = Path(".github/workflows/xfit-publish.yml").read_text(encoding="utf-8")
        self.assertIn('git show "HEAD^:${file}"', source)
        self.assertIn('--previous-file "$previous"', source)
        self.assertIn("--new-only", source)
        self.assertNotIn('python scripts/wp_publish.py --file "$file" --publish\n', source)


if __name__ == "__main__":
    unittest.main()
