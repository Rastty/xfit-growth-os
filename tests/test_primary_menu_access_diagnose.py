"""No-write redacted diagnosis for blocked sitewide navigation."""
import unittest
from scripts import xfit_primary_menu_access_diagnose as diagnosis
from scripts.wp_publish import PublishError


def four_items():
    return [
        {"id": n, "title": {"raw": title}, "parent": 0,
         "menu_order": n, "menus": 12, "url": "https://xfit.cz/category/" + str(n) + "/",
         "status": "publish"}
        for n, title in enumerate(("Výživa", "Kulturistika & fitness", "Sporty", "Anatomie"), 1)
    ]


class MenuAccessEvidenceTests(unittest.TestCase):
    def test_http_denial_is_categorized_without_leaking_error(self):
        def fetch(*args):
            raise PublishError("WordPress REST API returned HTTP 403")
        row = diagnosis.probe(fetch=fetch, base_reader=lambda: "https://xfit.cz")
        self.assertEqual(row["state"], "MENU_COLLECTION_NOT_READABLE")
        self.assertEqual(row["menu_collection_failure"], "HTTP_403")
        self.assertEqual(row["wordpress_writes"], 0)
        self.assertNotIn("private", str(row).lower())

    def test_exact_one_header_menu_evidence(self):
        def fetch(base, path):
            if path.startswith("menus?"):
                return [{"id": 12, "locations": ["header-menu"]}]
            return four_items()
        row = diagnosis.probe(fetch=fetch, base_reader=lambda: "https://xfit.cz")
        self.assertEqual(row["state"], "EXACT_ONE_HEADER_MENU_FOUND")
        self.assertEqual(row["best_public_label_match_count"], 4)
        self.assertEqual(row["exact_header_menu_candidates"], 1)
        self.assertEqual(row["menu_items_created"], 0)

    def test_nonheader_menu_cannot_be_treated_as_target(self):
        row = diagnosis.probe(
            fetch=lambda *args: [{"id": 8, "locations": ["footer-menu"]}],
            base_reader=lambda: "https://xfit.cz",
        )
        self.assertEqual(row["state"], "NO_SAFE_UNIQUE_HEADER_MENU")
        self.assertEqual(row["header_or_primary_menu_locations"], 0)


if __name__ == "__main__":
    unittest.main()
