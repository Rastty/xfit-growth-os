import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import xfit_beginner_protein_cost_release as release
from scripts.wp_publish import MARKER, PublishError


def post_record():
    source = json.loads(release.SOURCE.read_text(encoding="utf-8"))
    return {
        "id": release.POST_ID, "slug": release.SLUG, "status": "publish",
        "link": release.URL, "title": {"raw": source["title"]},
        "excerpt": {"raw": source["excerpt"]},
        "content": {"raw": MARKER + "\n" + source["content"]},
        "modified_gmt": "2026-11-15T00:00:00", "featured_media": 0,
    }


class BeginnerProteinCostReleaseTests(unittest.TestCase):
    def test_reviewed_proposal_exact_source_bound(self):
        p = release.review()
        self.assertEqual(p["wp_post_id"], 25458)
        self.assertEqual(p["status"], "editorial_proposal_not_deployed")
        self.assertEqual(p["operation"], "replace_exact_once")
        self.assertIn("900 Kč", p["original"])
        self.assertNotIn("900 Kč", p["replacement"])
        self.assertIn("včetně dopravy a povinných poplatků", p["replacement"])

    def test_live_article_one_exact_block_changed(self):
        record = post_record()
        p = release.review()
        out = release.inspect(record, p)
        self.assertEqual(out["state"], "ready")
        self.assertNotIn(p["original"], out["after"])
        self.assertEqual(out["after"].count(p["replacement"]), 1)
        self.assertEqual(out["after"].replace(p["replacement"], p["original"], 1), out["before"])
        record["content"]["raw"] = out["after"]
        self.assertEqual(release.inspect(record, p)["state"], "already_applied")

    def test_does_not_overwrite_foreign_editor_changes(self):
        record = post_record()
        record["content"]["raw"] = record["content"]["raw"].replace("Ukázkový výpočet", "Jiná kalkulace")
        with self.assertRaises(PublishError):
            release.inspect(record, release.review())

    def test_rejects_changed_identity_and_status(self):
        for field, value in (("id", 44), ("slug", "other"), ("status", "draft"),
                             ("link", "https://example.com/fake/")):
            record = post_record()
            record[field] = value
            with self.assertRaises(PublishError):
                release.inspect(record, release.review())

    def test_public_verifier_requires_real_method_and_no_old_fake_price(self):
        p = release.review()
        good = "<article>" + p["replacement"] + "</article>"
        self.assertTrue(release.public_verified(reader=lambda _: good))
        self.assertFalse(release.public_verified(reader=lambda _: p["original"]))
        self.assertFalse(release.public_verified(reader=lambda _: good + p["original"]))

    def test_snapshot_and_realistic_one_post_release(self):
        current = post_record()
        writes = []

        def remote(base, path, payload=None):
            self.assertEqual(base, "https://xfit.cz")
            self.assertIn("posts/25458", path)
            if payload is None:
                return copy.deepcopy(current)
            writes.append(payload)
            self.assertEqual(set(payload), {"content"})
            current["content"]["raw"] = payload["content"]
            return {"id": 25458, "status": "publish"}

        with tempfile.TemporaryDirectory() as folder:
            backup = Path(folder) / "rollback.json"
            with patch.object(release, "BACKUP", backup), \
                    patch.object(release, "normalized_base", return_value="https://xfit.cz"), \
                    patch.object(release, "wp_request", side_effect=remote), \
                    patch.object(release, "public_verified", return_value=True) as public:
                release.snapshot()
                manifest = json.loads(backup.read_text(encoding="utf-8"))
                self.assertEqual(manifest["original_raw"], post_record()["content"]["raw"])
                self.assertEqual(manifest["remote_writes"], 0)
                release.apply()
                self.assertEqual(len(writes), 1)
                self.assertEqual(public.call_count, 1)
                self.assertIn("Jak porovnat cenu proteinu", current["content"]["raw"])

    def test_snapshot_never_overwrites_existing_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            backup = Path(folder) / "rollback.json"
            backup.write_text("previous evidence", encoding="utf-8")
            with patch.object(release, "BACKUP", backup), patch.object(release, "post", return_value=post_record()):
                with self.assertRaises(PublishError):
                    release.snapshot()
            self.assertEqual(backup.read_text(), "previous evidence")

    def test_timeout_after_committed_write_does_not_retry(self):
        current = post_record()
        calls = []

        def remote(base, path, payload=None):
            if payload is None:
                return copy.deepcopy(current)
            calls.append(payload)
            current["content"]["raw"] = payload["content"]
            raise PublishError("ambiguous timeout, committed remotely")

        with tempfile.TemporaryDirectory() as folder:
            with patch.object(release, "BACKUP", Path(folder) / "rollback.json"), \
                    patch.object(release, "normalized_base", return_value="https://xfit.cz"), \
                    patch.object(release, "wp_request", side_effect=remote), \
                    patch.object(release, "public_verified", return_value=True):
                release.snapshot()
                release.apply()
        self.assertEqual(len(calls), 1)

    def test_unchanged_after_one_post_is_failure_no_repeat(self):
        current = post_record()
        writes = []

        def remote(base, path, payload=None):
            if payload is None:
                return copy.deepcopy(current)
            writes.append(payload)
            return {"id": 25458, "status": "publish"}

        with tempfile.TemporaryDirectory() as folder:
            with patch.object(release, "BACKUP", Path(folder) / "rollback.json"), \
                    patch.object(release, "normalized_base", return_value="https://xfit.cz"), \
                    patch.object(release, "wp_request", side_effect=remote):
                release.snapshot()
                with self.assertRaises(PublishError):
                    release.apply()
        self.assertEqual(len(writes), 1)

    def test_concurrent_article_edit_aborts_before_post(self):
        current = post_record()
        writes = []

        def remote(base, path, payload=None):
            if payload is None:
                return copy.deepcopy(current)
            writes.append(payload)
            return {"id": 25458, "status": "publish"}

        with tempfile.TemporaryDirectory() as folder:
            with patch.object(release, "BACKUP", Path(folder) / "rollback.json"), \
                    patch.object(release, "normalized_base", return_value="https://xfit.cz"), \
                    patch.object(release, "wp_request", side_effect=remote):
                release.snapshot()
                current["modified_gmt"] = "2026-11-15T00:01:00"
                with self.assertRaises(PublishError):
                    release.apply()
        self.assertEqual(writes, [])


if __name__ == "__main__":
    unittest.main()
