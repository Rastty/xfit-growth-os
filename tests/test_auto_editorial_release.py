"""Offline regression contracts for the trusted, pinned editorial release queue."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.xfit_auto_release import (
    MARKER, PublishError, blob_sha, prepare_queue, publish_one,
)

ROOT = Path(__file__).resolve().parents[1]
ARTICLE = "content/auto-ready/xfit-os-cena-proteinu-podle-etikety.json"
QUEUE = "content/auto-ready/queue-v1.json"


class AutonomousEditorialReleaseTests(unittest.TestCase):
    def setUp(self):
        self.prepared = prepare_queue(root=ROOT)
        self.assertEqual(len(self.prepared), 1)
        self.entry = self.prepared[0]

    def test_real_article_is_editorially_valid_and_exactly_pinned(self):
        self.assertGreaterEqual(self.entry["word_count"], 450)
        self.assertEqual(
            blob_sha((ROOT / ARTICLE).read_bytes()), self.entry["git_blob_sha"]
        )
        self.assertNotIn("namaximum.cz", self.entry["doc"]["content"])

    def test_one_new_post_is_live_and_exact_public_marker_is_checked(self):
        writes, reads = [], []

        def write(doc, live):
            writes.append((doc["slug"], live))
            return {"state": "live_verified", "slug": doc["slug"],
                    "post_id": 81234, "url": "https://xfit.cz/" + doc["slug"] + "/"}

        def check(url, marker):
            reads.append((url, marker))
            return True

        result = publish_one(self.prepared, lookup=lambda s: None,
                             writer=write, public_check=check)
        self.assertEqual(result["status"], "PUBLIC_VERIFIED_NEW_POST")
        self.assertEqual(result["new_posts"], 1)
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][1], True)
        self.assertEqual(reads[0][1], self.entry["marker"])

    def test_idempotent_replay_never_writes(self):
        post = {"id": 81234, "slug": self.entry["slug"],
                "status": "publish",
                "content": {"raw": self.entry["doc"]["content"]},
                "link": "https://xfit.cz/" + self.entry["slug"] + "/"}
        result = publish_one(self.prepared, lookup=lambda s: post,
                             writer=lambda *a, **k: self.fail("unexpected write"),
                             public_check=lambda *a: True)
        self.assertEqual(result["new_posts"], 0)
        self.assertEqual(result["status"], "ALL_PINNED_ARTICLES_PUBLIC_VERIFIED")

    def test_nonowned_or_modified_post_is_never_overwritten(self):
        post = {"id": 81234, "slug": self.entry["slug"], "status": "publish",
                "content": {"raw": MARKER + "\n" + "<p>Different existing editor content.</p>"},
                "link": "https://xfit.cz/" + self.entry["slug"] + "/"}
        with self.assertRaisesRegex(PublishError, "differs from pinned queue"):
            publish_one(self.prepared, lookup=lambda s: post,
                        writer=lambda *a, **k: self.fail("unexpected write"),
                        public_check=lambda *a: True)

    def test_failed_public_proof_is_not_reported_as_live(self):
        def no_public(*args):
            raise PublishError("Public cache stale")
        with self.assertRaisesRegex(PublishError, "cache stale"):
            publish_one(self.prepared, lookup=lambda s: None,
                        writer=lambda doc, live: {
                            "state": "live_verified", "slug": doc["slug"],
                            "post_id": 81234,
                            "url": "https://xfit.cz/" + doc["slug"] + "/"},
                        public_check=no_public)

    def test_tampered_article_is_rejected_before_wp(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dst = root / "content/auto-ready"
            dst.mkdir(parents=True)
            shutil.copy2(ROOT / QUEUE, dst / "queue-v1.json")
            data = json.loads((ROOT / ARTICLE).read_text(encoding="utf-8"))
            data["title"] += " tampered"
            (root / ARTICLE).write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(PublishError, "Git blob SHA mismatch"):
                prepare_queue(root=root)

    def test_invalid_nonobject_source_is_blocked_before_wordpress(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dst = root / "content/auto-ready"
            dst.mkdir(parents=True)
            payload = b'["not", "an", "article"]\n'
            (root / ARTICLE).write_bytes(payload)
            queue = json.loads((ROOT / QUEUE).read_text(encoding="utf-8"))
            queue["articles"][0]["git_blob_sha"] = blob_sha(payload)
            (root / QUEUE).write_text(json.dumps(queue), encoding="utf-8")
            with self.assertRaisesRegex(PublishError, "must be an object"):
                prepare_queue(root=root)

    def test_commercial_or_untrusted_reference_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dst = root / "content/auto-ready"
            dst.mkdir(parents=True)
            data = json.loads((ROOT / ARTICLE).read_text(encoding="utf-8"))
            data["content"] = data["content"].replace(
                "https://xfit.cz/xfit-os-protein-guide/",
                "https://evil.example.com/unsafe-product/")
            payload = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
            (root / ARTICLE).write_bytes(payload)
            queue = json.loads((ROOT / QUEUE).read_text(encoding="utf-8"))
            queue["articles"][0]["git_blob_sha"] = blob_sha(payload)
            (root / QUEUE).write_text(json.dumps(queue), encoding="utf-8")
            with self.assertRaisesRegex(PublishError, "Non-approved external"):
                prepare_queue(root=root)

    def test_legacy_pin_and_extra_fields_disallowed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dst = root / "content/auto-ready"
            dst.mkdir(parents=True)
            data = json.loads((ROOT / ARTICLE).read_text(encoding="utf-8"))
            data["wp_post_id"] = 1
            payload = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
            (root / ARTICLE).write_bytes(payload)
            queue = json.loads((ROOT / QUEUE).read_text(encoding="utf-8"))
            queue["articles"][0]["git_blob_sha"] = blob_sha(payload)
            (root / QUEUE).write_text(json.dumps(queue), encoding="utf-8")
            with self.assertRaisesRegex(PublishError, "legacy WP IDs"):
                prepare_queue(root=root)

    def test_medical_advice_disallowed_in_unattended_lane(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dst = root / "content/auto-ready"
            dst.mkdir(parents=True)
            data = json.loads((ROOT / ARTICLE).read_text(encoding="utf-8"))
            data["content"] += "<p>Rady o dávkování by vyžadovaly kontrolu.</p>"
            payload = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
            (root / ARTICLE).write_bytes(payload)
            queue = json.loads((ROOT / QUEUE).read_text(encoding="utf-8"))
            queue["articles"][0]["git_blob_sha"] = blob_sha(payload)
            (root / QUEUE).write_text(json.dumps(queue), encoding="utf-8")
            with self.assertRaisesRegex(PublishError, "Sensitive medical"):
                prepare_queue(root=root)


if __name__ == "__main__":
    unittest.main()
