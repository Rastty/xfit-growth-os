import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.wp_publish import PublishError
from scripts import xfit_coupon_recovery_11264 as recovery
from scripts.xfit_coupon_cleanup import stripped

COUPON = ('[su_button url="https://xfit.cz/fit" background="#ccc"]'
          'Slevový kód 5NM2022[/su_button]')
BODY = '<p>Praktické informace o tréninku a kreatinu. ' + ('Zdroje a zkušenosti. ' * 80) + '</p>' + COUPON * 3


def post(body=BODY, **overrides):
    data = {"id": recovery.POST_ID, "slug": recovery.SLUG,
            "status": "publish", "link": recovery.URL,
            "content": {"raw": body}}
    data.update(overrides)
    return data


class OnePostRecoveryTests(unittest.TestCase):
    def test_exact_identity_and_three_buttons_only(self):
        state = recovery.inspect(post())
        self.assertEqual(state["count"], 3)
        self.assertNotIn("5NM2022", state["after"])
        for invalid in (post(id=11595), post(status="draft"),
                        post(link="https://bad.example/"),
                        post(body=BODY.replace(COUPON, "", 1)),
                        post(body=BODY + "<p>5NM2022</p>")):
            with self.subTest(invalid=str(invalid.get("id"))):
                with self.assertRaises(PublishError):
                    recovery.inspect(invalid)

    def test_snapshot_contains_full_rollback_without_remote_write(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "backup.json"
            with patch.object(recovery, "BACKUP", target), \
                 patch.object(recovery, "get_post", return_value=post()), \
                 patch.object(recovery, "wp_request") as writer:
                recovery.snapshot()
                manifest = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual(manifest["original_raw"], BODY)
                self.assertEqual(manifest["remote_writes"], 0)
                writer.assert_not_called()
                with self.assertRaises(PublishError):
                    recovery.snapshot()

    def test_one_post_one_write_and_public_proof(self):
        clean, _ = stripped(BODY)
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "backup.json"
            with patch.object(recovery, "BACKUP", target), \
                 patch.object(recovery, "get_post", side_effect=[post(), post(), post(clean)]), \
                 patch.object(recovery, "wp_request", return_value={
                     "id": recovery.POST_ID, "status": "publish"
                 }) as writer, \
                 patch.object(recovery, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(recovery, "verify_public_coupon_absent", return_value=True) as public:
                recovery.snapshot()
                with contextlib.redirect_stdout(io.StringIO()) as stream:
                    recovery.apply()
                self.assertIn("PUBLIC_VERIFIED", stream.getvalue())
                writer.assert_called_once_with("https://xfit.cz", "posts/11264",
                                               payload={"content": clean})
                public.assert_called_once_with(recovery.URL)

    def test_failed_post_might_have_committed_but_is_not_retried(self):
        clean, _ = stripped(BODY)
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(recovery, "BACKUP", Path(temp) / "backup.json"), \
                 patch.object(recovery, "get_post", side_effect=[post(), post(), post(clean)]), \
                 patch.object(recovery, "wp_request", side_effect=PublishError("HTTP 502")) as writer, \
                 patch.object(recovery, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(recovery, "verify_public_coupon_absent", return_value=True):
                recovery.snapshot()
                recovery.apply()
                self.assertEqual(writer.call_count, 1)

    def test_unchanged_post_fails_without_false_success(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(recovery, "BACKUP", Path(temp) / "backup.json"), \
                 patch.object(recovery, "get_post", side_effect=[post(), post(), post()]), \
                 patch.object(recovery, "wp_request", return_value={
                     "id": recovery.POST_ID, "status": "publish"
                 }) as writer, \
                 patch.object(recovery, "normalized_base", return_value="https://xfit.cz"):
                recovery.snapshot()
                with self.assertRaises(PublishError):
                    recovery.apply()
                self.assertEqual(writer.call_count, 1)


if __name__ == "__main__":
    unittest.main()
