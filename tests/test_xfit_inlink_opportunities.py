"""Safety and evidence quality for a source-title internal-link review queue."""

from datetime import date
import unittest

from scripts.xfit_archive_full import inventory
from scripts.xfit_inlink_opportunities import (
    COOLDOWN_DAYS, MAX_CANDIDATES, TARGETS, build_opportunities,
)


NOW = date(2026, 11, 17)


def post(post_id, slug, title, body="<p>Useful fitness article.</p>", *,
         modified="2026-10-20T12:00:00", url=None):
    return {
        "id": post_id, "slug": slug,
        "link": url if url is not None else f"https://xfit.cz/{slug}/",
        "title": {"rendered": title}, "content": {"rendered": body},
        "modified": modified,
    }


def group(result, target):
    return next(p for p in result["targets"] if p["target_slug"] == target)


class OpportunityTests(unittest.TestCase):
    def test_only_specific_title_intents_are_candidates(self):
        posts = [
            post(11, "kreatin-a-protein-v-treninku", "Kreatin a protein – co vybrat?"),
            post(12, "kolik-stoji-protein", "Cena proteinu za jednu dávku"),
            post(13, "protein-pro-zacatecniky", "Protein – velký přehled"),
            post(14, "fitness-snazsi", "Fitness začátky", "Protein a kreatin v textu"),
            post(15, "srovnani-proteinu", "Porovnání proteinů"),
        ]
        result = build_opportunities(posts, as_of=NOW)
        self.assertEqual([p["id"] for p in group(result, TARGETS[0])["source_candidates"]], [11])
        self.assertEqual([p["id"] for p in group(result, TARGETS[1])["source_candidates"]], [12, 15])
        self.assertEqual(group(result, TARGETS[1])["source_candidates"][1]["title_relevance_tier"], "possible")
        self.assertTrue(result["no_wordpress_writes"])
        self.assertEqual(result["status"], "HUMAN_REVIEW_ONLY")

    def test_existing_real_link_excludes_source_but_inactive_markup_does_not(self):
        target = TARGETS[0]
        posts = [
            post(11, "kreatin-protein-ano", "Kreatin a protein", f'<a href="/{target}/?ref=sensitive">poradce</a>'),
            post(12, "kreatin-protein-template", "Kreatin a protein", f'<template><a href="/{target}/">schované</a></template>'),
            post(13, "kreatin-protein-domena", "Kreatin a protein", f'<a href="https://xfit.cz.evil.example/{target}/">cizí</a>'),
        ]
        result = build_opportunities(posts, as_of=NOW)
        self.assertEqual([p["id"] for p in group(result, target)["source_candidates"]], [12, 13])
        self.assertNotIn("sensitive", str(result))
        self.assertNotIn("evil.example", str(result))

    def test_recent_unknown_and_future_modified_are_not_suggested(self):
        posts = [
            post(1, "cena-proteinu-stara", "Cena proteinu", modified="2026-11-03T08:00:00"),
            post(2, "cena-proteinu-nova", "Cena proteinu", modified="2026-11-04T08:00:00"),
            post(3, "cena-proteinu-chybi", "Cena proteinu", modified=""),
            post(4, "cena-proteinu-budoucnost", "Cena proteinu", modified="2027-01-04T00:00:00"),
        ]
        result = build_opportunities(posts, as_of=NOW)
        self.assertEqual([p["id"] for p in group(result, TARGETS[1])["source_candidates"]], [1])
        self.assertEqual(result["posts_skipped_recent_or_unknown_modified"], 3)
        self.assertEqual(result["cooldown_days"], COOLDOWN_DAYS)

    def test_untrusted_urls_and_existing_guide_sources_are_rejected(self):
        posts = [
            post(1, "kreatin-protein", "Kreatin protein", url="https://xfit.cz.evil.example/kreatin-protein/"),
            post(2, "kreatin-protein-2", "Kreatin protein", url="https://xfit.cz:443/kreatin-protein-2/"),
            post(3, "kreatin-protein-3", "Kreatin protein", url="https://xfit.cz/kreatin-protein-3/?s=1"),
            post(4, "xfit-os-protein-guide", "Kreatin protein"),
            post(5, "kreatin-protein-5", "Kreatin protein", url="https://xfit.cz/kreatin-protein-5/"),
        ]
        result = build_opportunities(posts, as_of=NOW)
        self.assertEqual([p["id"] for p in group(result, TARGETS[0])["source_candidates"]], [5])

    def test_bounded_deterministic_order_and_archive_deduplication(self):
        posts = [post(i, f"kreatin-protein-{i}", "Kreatin protein")
                 for i in range(100, 100 + MAX_CANDIDATES + 3)][::-1]
        result = build_opportunities(posts, as_of=NOW)
        row = group(result, TARGETS[0])
        self.assertEqual(row["matching_source_posts"], MAX_CANDIDATES + 3)
        self.assertEqual(len(row["source_candidates"]), MAX_CANDIDATES)
        self.assertTrue(row["sample_truncated"])
        self.assertEqual(row["source_candidates"][0]["id"], 100)
        self.assertNotIn("https://", str(result))
        archived = inventory([posts[0], posts[0]])
        self.assertEqual(archived["guide_inlink_editorial_queue"]["posts_examined"], 1)


if __name__ == "__main__":
    unittest.main()
