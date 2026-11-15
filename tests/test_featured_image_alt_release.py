import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import xfit_featured_image_alt_release as release
from scripts.wp_publish import PublishError


def snapshot_data():
    data = []
    for spec in release.IMAGES:
        data.append({
            "media": {"id": spec["id"], "slug": spec["slug"], "status": "inherit",
                      "alt_text": "", "source_url": spec["url"]},
            "posts": [{"id": post_id, "slug": slug,
                       "url": "https://xfit.cz/" + slug + "/",
                       "featured_media": spec["id"]}
                      for post_id, slug in spec["posts"]],
        })
    return data


class FeaturedImageAltReleaseTests(unittest.TestCase):
    def test_exact_five_posts_and_three_distinct_media(self):
        specs = release.IMAGES
        self.assertEqual([s["id"] for s in specs], [2003, 1767, 1786])
        self.assertEqual(sum(len(s["posts"]) for s in specs), 5)
        self.assertEqual(len(set(x["id"] for x in specs)), 3)
        self.assertTrue(all("fitness" not in s["alt"].lower() for s in specs))

    def test_public_parser_correct_image_and_alt(self):
        s = release.IMAGES[0]
        p = snapshot_data()[0]["posts"][0]
        html = '<img class="entry-thumb" alt="falešný popis" src="/x.jpg">' + (
            f'<div><img class="entry-thumb td-modal-image" src="{s["url"]}" '
            f'alt="{s["alt"]}"></div>')
        self.assertTrue(release.public_alt_verified(s, p, reader=lambda _: html))
        self.assertFalse(release.public_alt_verified(s, p, reader=lambda _: html.replace(s["alt"], "")))

    def test_empty_featured_alt_is_not_a_pass(self):
        s = release.IMAGES[2]
        p = snapshot_data()[2]["posts"][1]
        page = f'<img class="entry-thumb" src="{s["url"]}" alt="">'
        self.assertFalse(release.public_alt_verified(s, p, reader=lambda _: page))

    def test_other_image_not_a_pass(self):
        s = release.IMAGES[1]
        p = snapshot_data()[1]["posts"][0]
        page = f'<img class="entry-thumb" src="https://example.com/photo.jpg" alt="{s["alt"]}">'
        self.assertFalse(release.public_alt_verified(s, p, reader=lambda _: page))

    def test_media_rejects_wrong_source_or_foreign_alt(self):
        s = release.IMAGES[0]
        raw = snapshot_data()[0]["media"]
        for field, value in (("source_url", "https://xfit.cz/wrong.jpg"),
                             ("alt_text", "A different editor's text"),
                             ("id", 99999)):
            remote = {**raw, field: value}
            with patch.object(release, "normalized_base", return_value="https://xfit.cz"), \
                    patch.object(release, "wp_request", return_value=remote):
                with self.assertRaises(PublishError):
                    release.media_state(s)

    def test_post_rejects_wrong_featured_attachment(self):
        s = release.IMAGES[0]
        p = snapshot_data()[0]["posts"][0]
        remote = {**p, "status": "publish", "featured_media": 999}
        with patch.object(release, "normalized_base", return_value="https://xfit.cz"), \
                patch.object(release, "wp_request", return_value=remote):
            with self.assertRaises(PublishError):
                release.post_states(s)

    def test_snapshot_writes_manifest_without_wp_write(self):
        originals = snapshot_data()
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "rollback.json"
            with patch.object(release, "BACKUP", dest), \
                    patch.object(release, "media_state", side_effect=[d["media"] for d in originals] * 2), \
                    patch.object(release, "post_states", side_effect=[d["posts"] for d in originals] * 2):
                release.snapshot()
                self.assertEqual(json.loads(dest.read_text())["originals"], originals)
                with self.assertRaises(PublishError):
                    release.snapshot()

    def test_apply_writes_only_alt_and_checks_public_pages(self):
        originals = snapshot_data()
        current = copy.deepcopy(originals)
        writes = []

        def media(s):
            for entry in current:
                if entry["media"]["id"] == s["id"]:
                    return copy.deepcopy(entry["media"])
            raise AssertionError

        def posts(s):
            return next(copy.deepcopy(d["posts"]) for d in current if d["media"]["id"] == s["id"])

        def wp_req(base, path, payload=None):
            self.assertEqual(base, "https://xfit.cz")
            self.assertIsNotNone(payload)
            media_id = int(path.split("/")[1])
            self.assertEqual(payload, {"alt_text": next(s["alt"] for s in release.IMAGES if s["id"] == media_id)})
            entry = next(d for d in current if d["media"]["id"] == media_id)
            entry["media"]["alt_text"] = payload["alt_text"]
            writes.append((media_id, payload))
            return {"id": media_id}

        with patch.object(release, "manifest", return_value=originals), \
                patch.object(release, "media_state", side_effect=media), \
                patch.object(release, "post_states", side_effect=posts), \
                patch.object(release, "normalized_base", return_value="https://xfit.cz"), \
                patch.object(release, "wp_request", side_effect=wp_req), \
                patch.object(release, "public_alt_verified", return_value=True) as public:
            release.apply()
        self.assertEqual([w[0] for w in writes], [2003, 1767, 1786])
        self.assertEqual(public.call_count, 5)

    def test_concurrent_change_aborts_before_writes(self):
        originals = snapshot_data()
        changed = copy.deepcopy(originals)
        changed[2]["media"]["status"] = "trash"
        with patch.object(release, "manifest", return_value=originals), \
                patch.object(release, "media_state", side_effect=[d["media"] for d in changed]), \
                patch.object(release, "post_states", side_effect=[d["posts"] for d in originals]), \
                patch.object(release, "wp_request") as wp:
            with self.assertRaises(PublishError):
                release.apply()
            wp.assert_not_called()

    def test_uncertain_post_does_not_retry(self):
        originals = snapshot_data()
        current = copy.deepcopy(originals)

        def media(s):
            return next(copy.deepcopy(d["media"]) for d in current if d["media"]["id"] == s["id"])

        with patch.object(release, "manifest", return_value=originals), \
                patch.object(release, "media_state", side_effect=media), \
                patch.object(release, "post_states", side_effect=[d["posts"] for d in originals]), \
                patch.object(release, "normalized_base", return_value="https://xfit.cz"), \
                patch.object(release, "wp_request", side_effect=PublishError("timeout")) as wp:
            with self.assertRaises(PublishError):
                release.apply()
            self.assertEqual(wp.call_count, 1)


if __name__ == "__main__":
    unittest.main()
