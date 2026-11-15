import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.wp_publish import PublishError
from scripts import xfit_coupon_recovery_11945 as recovery
from scripts.xfit_coupon_cleanup import stripped

COUPON = ('[su_button url="https://xfit.cz/spalovace" background="#ccc"]'
          'Slevový kód 5NM2022[/su_button]')
BODY = '<p>Praktické informace o tréninku. ' + ('Doplňující text. ' * 80) + '</p>' + COUPON * 3


def post(body=BODY, **overrides):
    data = {"id": recovery.POST_ID, "slug": recovery.SLUG,
            "status": "publish", "link": recovery.URL,
            "content": {"raw": body}}
    data.update(overrides)
    return data


class Coupon11945RecoveryTests(unittest.TestCase):
    def test_only_exact_post_with_three_coupons(self):
        state = recovery.inspect(post())
        self.assertEqual(state["count"], 3)
        self.assertNotIn("5NM2022", state["after"])
        for invalid in (post(id=11264), post(status="draft"),
                        post(link="http://xfit.cz/"), post(body=BODY.replace(COUPON, "", 1)),
                        post(body=BODY + "<p>5NM2022</p>")):
            with self.subTest(invalid=str(invalid.get("id"))):
                with self.assertRaises(PublishError):
                    recovery.inspect(invalid)

    def test_full_rollback_before_any_write(self):
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

    def test_single_content_only_post_and_public_proof(self):
        clean, _ = stripped(BODY)
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(recovery, "BACKUP", Path(temp) / "backup.json"), \
                 patch.object(recovery, "get_post", side_effect=[post(), post(), post(clean)]), \
                 patch.object(recovery, "wp_request", return_value={
                     "id": recovery.POST_ID, "status": "publish"
                 }) as writer, \
                 patch.object(recovery, "normalized_base", return_value="https://xfit.cz"), \
                 patch.object(recovery, "verify_public_coupon_absent", return_value=True):
                recovery.snapshot()
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    recovery.apply()
                self.assertIn("PUBLIC_VERIFIED", output.getvalue())
                writer.assert_called_once_with(
                    "https://xfit.cz", "posts/11945", payload={"content": clean})

    def test_ambiguous_http_error_reconciles_without_retry(self):
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

    def test_unchanged_body_remains_a_failure(self):
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
