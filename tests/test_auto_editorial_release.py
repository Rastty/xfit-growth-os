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

    def _source_bound_ai_post(self):
        """Mimic only the approved additive release layout of the AI editor."""
        from scripts.xfit_ai_editorial import config_targets

        target = next(
            t for t in config_targets()
            if t["kind"] == "enhance" and t["slug"] == self.entry["slug"]
        )
        paragraph = (
            "Nejprve najděte čistou hmotnost balení a na etiketě údaj "
            "o obsahu bílkovin. "
        ) * 15
        section = (
            '<section data-xfit-ai-edit="' + target["marker"] + '">'
            '<h2>Praktické porovnání podobných balení</h2>'
            '<p>' + paragraph + '</p>'
            '<ul><li>Přečtěte si etiketu a ověřte hmotnost výrobku.</li></ul>'
            '<p>Další metodika je v <a href="' + target["allowed_links"][0]
            + '">průvodci proteinem</a>.</p>'
            '</section>'
        )
        desired = self.entry["doc"]["content"]
        self.assertTrue(desired.startswith(MARKER + "\n"))
        return {
            "id": target["post_id"],
            "slug": self.entry["slug"],
            "status": "publish",
            "content": {"raw": MARKER + "\n" + section + "\n" +
                        desired[len(MARKER) + 1:]},
            "link": "https://xfit.cz/" + self.entry["slug"] + "/",
        }, target["marker"]

    def test_approved_ai_addition_is_idempotent_with_three_public_proofs(self):
        edited, ai_marker = self._source_bound_ai_post()
        reads = []
        result = publish_one(
            self.prepared, lookup=lambda _: edited,
            writer=lambda *args, **kwargs: self.fail("No WP writes allowed"),
            public_check=lambda url, marker: reads.append(("pinned", marker)),
            ai_public_check=lambda url, marker, *, kind: reads.append((kind, marker)),
            body_public_check=lambda url, title, content: reads.append(("body", content)),
        )
        self.assertEqual(result["status"], "ALL_PINNED_ARTICLES_PUBLIC_VERIFIED")
        self.assertEqual(result["new_posts"], 0)
        self.assertEqual(result["verified_ai_enhancements"], 1)
        self.assertEqual(reads[0], ("pinned", self.entry["marker"]))
        self.assertEqual(reads[1], ("enhance", ai_marker))
        self.assertEqual(reads[2], ("body", edited["content"]["raw"]))

    def test_modified_pinned_tail_must_not_be_reconciled(self):
        edited, marker = self._source_bound_ai_post()
        edited["content"]["raw"] = edited["content"]["raw"].replace(
            "899 Kč", "999 Kč"
        )
        with self.assertRaisesRegex(PublishError, "differs from pinned queue"):
            publish_one(
                self.prepared, lookup=lambda _: edited,
                writer=lambda *args, **kwargs: self.fail("No WP writes allowed"),
                public_check=lambda *args: self.fail("Do not approve drift"),
            )

    def test_unapproved_ai_sections_remain_blocked(self):
        post, marker = self._source_bound_ai_post()
        cases = [
            post["content"]["raw"].replace(marker, "xfit-ai-unknown-edit-v1"),
            post["content"]["raw"].replace(
                "https://xfit.cz/xfit-os-protein-guide/",
                "https://untrusted.example/advertisement/"
            ),
            post["content"]["raw"].replace(
                "<h2>Praktické", "<script>evil()</script><h2>Praktické"
            ),
            post["content"]["raw"].replace(
                "</section>\n", "</section><p>extra copy</p>\n", 1
            ),
        ]
        for raw in cases:
            with self.subTest(raw=raw[:90]):
                altered = dict(post, content={"raw": raw})
                with self.assertRaisesRegex(PublishError, "differs from pinned queue"):
                    publish_one(
                        self.prepared, lookup=lambda _: altered,
                        writer=lambda *args, **kwargs: self.fail("No WP writes allowed"),
                    )
        wrong_id = dict(post, id=999999)
        with self.assertRaisesRegex(PublishError, "differs from pinned queue"):
            publish_one(self.prepared, lookup=lambda _: wrong_id,
                        writer=lambda *args, **kwargs: self.fail("No WP writes allowed"))

    def test_missing_public_ai_proof_blocks_reconciliation_without_write(self):
        edited, marker = self._source_bound_ai_post()

        def fail_ai(*args, **kwargs):
            raise PublishError("AI section not visible publicly")

        with self.assertRaisesRegex(PublishError, "not visible publicly"):
            publish_one(
                self.prepared, lookup=lambda _: edited,
                writer=lambda *args, **kwargs: self.fail("No WP writes allowed"),
                public_check=lambda *args: True,
                ai_public_check=fail_ai,
                body_public_check=lambda *args: self.fail("Must not accept unverified AI"),
            )

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
