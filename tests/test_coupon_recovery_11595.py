import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.wp_publish import PublishError
from scripts import xfit_coupon_recovery as recovery
from scripts.xfit_coupon_cleanup import stripped, sha


SHORTCODE = ('[su_button url="https://xfit.cz/pohyb" background="#eee"]'
             'Fitness oblečení v akci – starý slevový kód 5NM2022[/su_button]')
SOURCE = ('<p>Praktické rady pro výběr a použití oblečení při pohybu. '
          'Nejsou to přísliby slevy ani lékařské rady.</p>' * 12
          + SHORTCODE * 3 +
          '<h2>Jaké materiály vybírat?</h2><p>Ověřte etiketu výrobku.</p>')


def post(content=SOURCE, post_id=11595, slug="jak-vybrat-sportovni-obleceni"):
    return {
        "id": post_id, "status": "publish", "slug": slug,
        "link": "https://xfit.cz/" + slug + "/",
        "content": {"raw": content},
    }


class RecoveryTests(unittest.TestCase):
    def test_preflight_is_pinned_to_known_single_post_and_exact_three_blocks(self):
        x = recovery.classify(post())
        self.assertEqual(x["post_id"], 11595)
        self.assertEqual(x["shortcodes_to_remove"], 3)
        self.assertEqual(x["before_sha256"], sha(SOURCE))
        cleaned, count = stripped(SOURCE)
        self.assertEqual(x["after_sha256"], sha(cleaned))
        self.assertEqual(count, 3)
        self.assertIn("Jaké materiály vybírat?", cleaned)
        self.assertNotIn("5NM2022", cleaned)
        for invalid in (post(post_id=11888), post(post_id=999),
                        {**post(), "status": "draft"},
                        {**post(), "link": "https://bad.example/other"},
                        {**post(), "slug": "other"},
                        post(content=SOURCE.replace(SHORTCODE, "", 1))):
            with self.subTest(invalid=str(invalid.get("id"))):
                with self.assertRaises(PublishError):
                    recovery.classify(invalid)

    def test_snapshot_is_read_only_and_contains_exact_prewrite_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "snapshot.json"
            with patch.object(recovery, "BACKUP", dest), \
                 patch.object(recovery, "get_post", return_value=post()), \
                 patch.object(recovery, "wp_request") as writer:
                recovery.snapshot()
                file = json.loads(dest.read_text(encoding="utf-8"))
                self.assertEqual(file["entry"]["post_id"], 11595)
                self.assertEqual(file["entry"]["original_raw"], SOURCE)
                self.assertEqual(file["remote_writes"], 0)
                writer.assert_not_called()
                with self.assertRaises(PublishError):
                    recovery.snapshot()

    def test_one_post_one_write_with_verified_public_receipt(self):
        updated, _ = stripped(SOURCE)
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "snapshot.json"
            with patch.object(recovery, "BACKUP", dest), \
                 patch.object(recovery, "get_post", side_effect=[
                     post(), post(), post(content=updated)
                 ]), \
                 patch.object(recovery, "wp_request", return_value={
                     "id":11595,"status":"publish"
                 }) as writer, \
                 patch.object(recovery, "normalized_base",
                              return_value="https://xfit.cz"), \
                 patch.object(recovery, "verify_public_coupon_absent",
                              return_value=True) as public:
                recovery.snapshot()
                output=io.StringIO()
                with contextlib.redirect_stdout(output):
                    recovery.apply()
                writer.assert_called_once_with(
                    "https://xfit.cz","posts/11595",payload={"content":updated})
                public.assert_called_once_with(
                    "https://xfit.cz/jak-vybrat-sportovni-obleceni/")
                self.assertIn('"state": "PUBLIC_VERIFIED"',output.getvalue())
                self.assertIn('"posts_changed": 1',output.getvalue())
                self.assertNotIn("5NM2022",output.getvalue())

    def test_failed_post_may_have_committed_and_is_never_repeated(self):
        updated,_=stripped(SOURCE)
        with tempfile.TemporaryDirectory() as directory:
            dest=Path(directory)/"snapshot.json"
            with patch.object(recovery,"BACKUP",dest), \
                 patch.object(recovery,"get_post",side_effect=[
                     post(),post(),post(content=updated)]), \
                 patch.object(recovery,"wp_request",side_effect=PublishError(
                     "connection closed after remote write")) as writer, \
                 patch.object(recovery,"normalized_base",
                              return_value="https://xfit.cz"), \
                 patch.object(recovery,"verify_public_coupon_absent",
                              return_value=True):
                recovery.snapshot()
                recovery.apply()
                self.assertEqual(writer.call_count,1)

    def test_uncertain_failure_or_source_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            dest=Path(directory)/"snapshot.json"
            with patch.object(recovery,"BACKUP",dest), \
                 patch.object(recovery,"get_post",return_value=post()):
                recovery.snapshot()
            with patch.object(recovery,"BACKUP",dest), \
                 patch.object(recovery,"get_post",return_value=post(
                     content=SOURCE+"<p>Somebody edited this</p>")), \
                 patch.object(recovery,"wp_request") as writer:
                with self.assertRaises(PublishError):
                    recovery.apply()
                writer.assert_not_called()
            with patch.object(recovery,"BACKUP",dest), \
                 patch.object(recovery,"get_post",side_effect=[post(),post()]), \
                 patch.object(recovery,"wp_request",
                              side_effect=PublishError("HTTP 503")) as writer, \
                 patch.object(recovery,"normalized_base",
                              return_value="https://xfit.cz"), \
                 patch.object(recovery,"verify_public_coupon_absent") as public:
                with self.assertRaises(PublishError):
                    recovery.apply()
                self.assertEqual(writer.call_count,1)
                public.assert_not_called()

    def test_already_clean_has_zero_post_attempts(self):
        updated,_=stripped(SOURCE)
        with tempfile.TemporaryDirectory() as directory:
            dest=Path(directory)/"snapshot.json"
            with patch.object(recovery,"BACKUP",dest), \
                 patch.object(recovery,"get_post",return_value=post(updated)), \
                 patch.object(recovery,"wp_request") as writer:
                recovery.snapshot()
                recovery.apply()
                writer.assert_not_called()

    def test_public_result_rejects_coupon_in_html(self):
        self.assertFalse(recovery.verify_public_coupon_absent(
            "https://xfit.cz/example/",
            public_reader=lambda url:'<button>5NM2022</button>'))
        self.assertTrue(recovery.verify_public_coupon_absent(
            "https://xfit.cz/example/",
            public_reader=lambda url:'<h1>New evergreen guide</h1>'))


if __name__ == "__main__":
    unittest.main()
