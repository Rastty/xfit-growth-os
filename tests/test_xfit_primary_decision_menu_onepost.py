"""Sitewide decision menu: no duplicate, no rearrangement, no blind retry."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import xfit_primary_decision_menu_onepost as nav
from scripts.wp_publish import PublishError


def original_items():
    return [
        {"id": k, "title": {"raw": name}, "url": "https://xfit.cz/category/" + str(k) + "/",
         "menus": 12, "parent": 0, "menu_order": k, "status": "publish"}
        for k, name in zip((1,2,3,4), ("Výživa", "Kulturistika & fitness", "Sporty", "Anatomie"))
    ]


def menu():
    return [{"id": 12, "slug": "main", "name": "Site header",
             "locations": ["header-menu"]}]


def fake_guide():
    return [{"id": 25458, "slug": "xfit-os-doplnky-pro-zacatecniky",
             "link": nav.DEST, "status": "publish"}]


class DecisionNavigationTests(unittest.TestCase):
    def setUp(self):
        self.mock_base = patch.object(nav, "normalized_base",
                                      return_value="https://xfit.cz")
        self.mock_base.start()
        self.addCleanup(self.mock_base.stop)

    def test_choose_exact_primary_menu_by_location_and_four_current_titles(self):
        with patch.object(nav, "fetch_menu_items", return_value=original_items()):
            ident, items = nav.choose_header_menu(fetch=lambda *args: menu())
        self.assertEqual(ident, 12)
        self.assertEqual({i["title"] for i in items}, nav.KNOWN_HEADER)

    def test_wrong_nav_structure_or_ambiguous_menu_blocks_without_post(self):
        wrong = original_items()[:2]
        for menus, items in ((menu(), wrong), (menu() * 2, original_items()),
                             ([{"id": 12, "locations": ["footer-menu"]}], original_items())):
            with self.subTest(menus=menus), \
                 patch.object(nav, "fetch_menu_items", return_value=items):
                with self.assertRaises(PublishError):
                    nav.choose_header_menu(fetch=lambda *args, m=menus: m)

    def test_existing_dest_duplicate_or_invented_title_blocked(self):
        items = original_items()
        items.append({"id": 9, "title": {"raw": "Old hidden link"},
                      "url": nav.DEST, "menus": 12, "parent": 0,
                      "menu_order": 9, "status": "publish"})
        with patch.object(nav, "fetch_menu_items", return_value=items):
            with self.assertRaisesRegex(PublishError, "under a different label"):
                nav.choose_header_menu(fetch=lambda *args: menu())

    def test_header_link_is_not_satisfied_by_body_card_or_sidebar(self):
        only_article = '<html><body><article><a href="' + nav.DEST + '">Vybrat doplněk</a></article></body></html>'
        self.assertFalse(nav.public_header_verified(reader=lambda _: only_article))
        header = ('<html><header><nav><a href="' + nav.DEST + '">'
                  'Vybrat doplněk</a></nav></header></html>')
        self.assertTrue(nav.public_header_verified(reader=lambda _: header))
        self.assertFalse(nav.public_header_verified(reader=lambda _:
                         header.replace('Vybrat doplněk', 'Unrelated menu')))

    def test_snapshot_preserves_all_prewrite_items_and_one_destination(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(nav, "BACKUP", Path(tmp)/"backup.json"), \
             patch.object(nav, "assert_public_guide"), \
             patch.object(nav, "choose_header_menu",
                          return_value=(12, nav.menu_projection(original_items()))):
            nav.snapshot()
            saved = json.loads(nav.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(saved["menu_id"], 12)
            self.assertEqual(len(saved["items"]), 4)
            self.assertEqual(saved["mode"], "create")
            self.assertEqual(saved["remote_writes"], 0)
            with self.assertRaisesRegex(PublishError, "no overwrite"):
                nav.snapshot()

    def test_single_post_preserves_existing_items_and_public_header(self):
        original = nav.menu_projection(original_items())
        updated = original_items() + [{
            "id": 5, "title": {"raw": nav.TITLE}, "url": nav.DEST,
            "menus": 12, "parent": 0, "menu_order": 5, "status": "publish",
        }]
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(nav, "BACKUP", Path(tmp)/"backup.json"):
            nav.BACKUP.write_text(json.dumps({
                "schema": 1, "menu_id": 12, "items": original,
                "mode": "create", "remote_writes": 0,
            }), encoding="utf-8")
            with patch.object(nav, "choose_header_menu", return_value=(12, original)), \
                 patch.object(nav, "fetch_menu_items", return_value=updated), \
                 patch.object(nav, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(nav, "wp_request", return_value={"id":5}) as write, \
                 patch.object(nav, "public_header_verified", return_value=True):
                nav.apply()
            write.assert_called_once()
            self.assertEqual(write.call_args.kwargs["payload"]["menus"], 12)
            self.assertEqual(write.call_args.kwargs["payload"]["url"], nav.DEST)
            self.assertEqual(write.call_args.kwargs["payload"]["title"], nav.TITLE)

    def test_unknown_post_must_not_retry_and_race_refused_before_post(self):
        original = nav.menu_projection(original_items())
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(nav, "BACKUP", Path(tmp)/"backup.json"):
            nav.BACKUP.write_text(json.dumps({
                "schema": 1, "menu_id": 12, "items": original,
                "mode": "create", "remote_writes": 0,
            }), encoding="utf-8")
            drift = original + [dict(original[0], id=7)]
            with patch.object(nav, "choose_header_menu", return_value=(12, drift)), \
                 patch.object(nav, "wp_request") as writer:
                with self.assertRaisesRegex(PublishError, "drift"):
                    nav.apply()
                writer.assert_not_called()
            with patch.object(nav, "choose_header_menu", return_value=(12, original)), \
                 patch.object(nav, "fetch_menu_items", return_value=original_items()), \
                 patch.object(nav, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(nav, "wp_request", side_effect=PublishError("timeout")) as writer:
                with self.assertRaises(PublishError):
                    nav.apply()
                writer.assert_called_once()

    def test_existing_menu_item_is_noop(self):
        before = original_items() + [{
            "id": 5, "title": {"raw": nav.TITLE}, "url": nav.DEST,
            "menus": 12, "parent": 0, "menu_order": 5, "status": "publish",
        }]
        projected = nav.menu_projection(before)
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(nav, "BACKUP", Path(tmp)/"backup.json"):
            nav.BACKUP.write_text(json.dumps({
                "schema": 1, "menu_id": 12, "items": projected,
                "mode": "already_linked", "remote_writes": 0,
            }), encoding="utf-8")
            with patch.object(nav, "choose_header_menu",
                              return_value=(12, projected)), \
                 patch.object(nav, "public_header_verified", return_value=True), \
                 patch.object(nav, "wp_request") as writer:
                nav.apply()
                writer.assert_not_called()

    def test_workflow_requires_backup_and_no_schedule(self):
        text = Path(".github/workflows/xfit-decision-primary-menu-onepost.yml").read_text()
        self.assertIn("xfit_primary_decision_menu_onepost snapshot", text)
        self.assertIn("xfit_primary_decision_menu_onepost apply", text)
        self.assertIn("if-no-files-found: error", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("workflow_dispatch:", text)


if __name__ == "__main__":
    unittest.main()
