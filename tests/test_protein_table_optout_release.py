"""Safe onepost opt-out row insertion without rewriting already improved content."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.wp_publish import MARKER, PublishError
from scripts import xfit_protein_table_optout_release as release


def source_body():
    ready = json.loads(Path("content/ready/xfit-os-protein-guide.json")
                       .read_text(encoding="utf-8"))
    return MARKER + "\n" + ready["content"] + (
        "\n<section><h2>Další schválené vysvětlení</h2>"
        "<p>Veřejný článek může mít novější schválený obsah.</p></section>"
    )


def post(raw, modified="2026-11-10T16:00:00", status="publish"):
    return {"id": release.POST_ID, "slug": release.SLUG,
            "status": status, "link": release.PUBLIC_URL,
            "modified_gmt": modified, "content": {"raw": raw}}


class ProteinTableOptOutReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rev = release.revision()
        cls.old = source_body()
        cls.new = cls.old.replace(cls.rev["original"],
                                  cls.rev["replacement"], 1)

    def test_original_table_prefix_is_unique_and_no_buy_is_first(self):
        self.assertEqual(self.old.count(self.rev["original"]), 1)
        self.assertEqual(self.new.count(self.rev["replacement"]), 1)
        self.assertIn("<tr><td>Bílkoviny už pokryjete běžným jídlem", self.new)
        self.assertIn("<td>Žádný proteinový doplněk</td>", self.new)
        self.assertEqual(self.new.replace(self.rev["replacement"],
                                          self.rev["original"], 1), self.old)
        self.assertEqual(release.inspect(post(self.old), self.rev)["after"], self.new)

    def test_single_remote_write_after_immutable_backup(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(release, "BACKUP", Path(d) / "backup.json"), \
                 patch.object(release, "post", side_effect=[
                     post(self.old), post(self.old), post(self.new)]), \
                 patch.object(release, "normalized_base",
                              return_value="https://xfit.cz"), \
                 patch.object(release, "wp_request",
                              return_value={"id": release.POST_ID, "status": "publish"}) as writer, \
                 patch.object(release, "public_verified", return_value=True):
                release.snapshot()
                backup = json.loads(release.BACKUP.read_text(encoding="utf-8"))
                self.assertEqual(backup["original_raw"], self.old)
                self.assertEqual(backup["remote_writes"], 0)
                release.apply()
                writer.assert_called_once_with(
                    "https://xfit.cz", "posts/25451",
                    payload={"content": self.new})

    def test_changed_remote_content_after_backup_fails_without_write(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(release, "BACKUP", Path(d) / "backup.json"), \
                 patch.object(release, "post", side_effect=[
                     post(self.old), post(self.old,
                         modified="2026-11-10T16:00:01")]), \
                 patch.object(release, "wp_request") as writer:
                release.snapshot()
                with self.assertRaises(PublishError):
                    release.apply()
                writer.assert_not_called()

    def test_post_timeout_can_reconcile_but_never_repeat_the_post(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(release, "BACKUP", Path(d) / "backup.json"), \
                 patch.object(release, "post", side_effect=[
                     post(self.old), post(self.old), post(self.new)]), \
                 patch.object(release, "normalized_base",
                              return_value="https://xfit.cz"), \
                 patch.object(release, "wp_request",
                              side_effect=PublishError("timed out")) as writer, \
                 patch.object(release, "public_verified", return_value=True):
                release.snapshot()
                release.apply()
                self.assertEqual(writer.call_count, 1)

    def test_already_applied_remains_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(release, "BACKUP", Path(d) / "backup.json"), \
                 patch.object(release, "post", return_value=post(self.new)), \
                 patch.object(release, "wp_request") as writer, \
                 patch.object(release, "public_verified", return_value=True):
                release.snapshot()
                release.apply()
                writer.assert_not_called()

    def test_protects_post_identity_and_original_row(self):
        for bad in (
            post(self.old, status="draft"),
            {**post(self.old), "slug": "unrelated"},
            {**post(self.old), "link": "https://other.example/protein/"},
            post(self.old.replace(MARKER, "")),
            post(self.old.replace(self.rev["original"], "Outdated table")),
            post(self.old.replace(self.rev["original"],
                                  self.rev["original"] * 2)),
        ):
            with self.subTest(bad=bad.get("slug")):
                with self.assertRaises(PublishError):
                    release.inspect(bad, self.rev)

    def test_public_content_requires_the_actual_new_row(self):
        good = ("<table><tr><td>Bílkoviny už pokryjete běžným jídlem</td>"
                "<td>Žádný proteinový doplněk</td>"
                "<td>Než přejdete ke srovnání cen</td></tr>"
                "<tr><td>Univerzální protein za rozumnou cenu</td></tr></table>"
                "<h2>1. Kolik bílkovin vlastně potřebujete?</h2>")
        self.assertTrue(release.public_verified(reader=lambda _: good))
        self.assertFalse(release.public_verified(reader=lambda _:
            good.replace("Žádný proteinový doplněk", "WPC")))
        self.assertFalse(release.public_verified(reader=lambda _: good + good))
        self.assertFalse(release.public_verified(reader=lambda _:
            "<table><tr><td>Syrovátkový izolát</td></tr></table>"))


if __name__ == "__main__":
    unittest.main()
