"""Exactly one recoverable 2022 coupon article; no blind write retries."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.xfit_coupon_cleanup import sha, stripped
from scripts.wp_publish import PublishError
from scripts import xfit_coupon_recovery_11888 as c


BUTTON = ('[su_button url="https://xfit.cz/produkt"]'
          '5NM2022 starý kupon, není platný[/su_button]')
RAW = ("<h1>Jak vybrat kreatin</h1><p>Aktualizujte informaci podle "
       "aktuálního výrobce. Nevydáváme neověřené slevy.</p>" * 8 +
       BUTTON * 3 +
       "<h2>Další informace</h2><p>Etiketa a potřeba jsou důležitější.</p>")
CLEAN, COUNT = stripped(RAW)


def post(body=RAW, *, post_id=c.POST_ID, status="publish", slug=c.SLUG,
         url=c.URL):
    return {
        "id": post_id, "status": status, "slug": slug, "link": url,
        "content": {"raw": body},
    }


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.assertEqual(COUNT, 3)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patches = [
            patch.object(c, "BACKUP", Path(self.temp.name) / "one.json"),
            patch.object(c, "BEFORE_SHA", sha(RAW)),
            patch.object(c, "AFTER_SHA", sha(CLEAN)),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_only_matching_historical_body_and_three_blocks_allowed(self):
        st = c.state(post())
        self.assertEqual(st["mode"], "update")
        self.assertEqual(st["after"], CLEAN)
        self.assertEqual(st["before"], RAW)
        self.assertEqual(c.state(post(CLEAN))["mode"], "clean")
        for altered in [
            post(RAW+"<p>New editorial change</p>"),
            post(RAW.replace(BUTTON,"",1)),
            post(status="draft"),
            post(post_id=11889),
            post(slug="other"),
            post(url="https://other.example/"+c.SLUG+"/"),
            post(url=c.URL+"?utm_source=test"),
            post(body=""),
        ]:
            with self.subTest(altered_id=altered.get("id"),
                              altered_len=len((altered.get("content") or {}).get("raw",""))):
                with self.assertRaises(PublishError):
                    c.state(altered)

    def test_snapshot_is_read_only_and_not_overwritten(self):
        with patch.object(c, "get_post", return_value=post()), \
             patch.object(c, "wp_request") as writer:
            c.snapshot()
            saved=json.loads(c.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual(saved["post_id"], 11888)
            self.assertEqual(saved["source"].split()[0], "original")
            self.assertEqual(saved["original_raw"], RAW)
            self.assertEqual(saved["before_sha"], sha(RAW))
            self.assertEqual(saved["after_sha"], sha(CLEAN))
            self.assertEqual(saved["remote_writes"], 0)
            writer.assert_not_called()
            with self.assertRaises(PublishError):
                c.snapshot()

    def test_one_and_only_one_actual_post_with_public_verification(self):
        with patch.object(c, "get_post", side_effect=[
            post(), post(), post(CLEAN)
        ]), patch.object(c, "wp_request", return_value={
            "id": c.POST_ID, "status": "publish"
        }) as writer, patch.object(c, "normalized_base",
                                   return_value="https://xfit.cz"), \
            patch.object(c, "public_clean", return_value=True) as public:
            c.snapshot()
            c.apply()
            writer.assert_called_once_with(
                "https://xfit.cz", "posts/11888", payload={"content": CLEAN})
            public.assert_called_once_with()
            self.assertEqual(json.loads(c.BACKUP.read_text())["remote_writes"],0)

    def test_post_timeout_that_committed_is_reconciled_not_repeated(self):
        with patch.object(c, "get_post", side_effect=[
            post(), post(), post(CLEAN)
        ]), patch.object(c, "wp_request",
                         side_effect=PublishError("timeout")) as writer, \
            patch.object(c, "normalized_base",
                         return_value="https://xfit.cz"), \
            patch.object(c, "public_clean", return_value=True):
            c.snapshot()
            c.apply()
            self.assertEqual(writer.call_count,1)

    def test_source_drift_aborts_before_post(self):
        with patch.object(c, "get_post", side_effect=[
            post(), post(RAW+"<p>Live change</p>")
        ]), patch.object(c, "wp_request") as writer:
            c.snapshot()
            with self.assertRaises(PublishError):
                c.apply()
            writer.assert_not_called()

    def test_uncertain_write_not_retried(self):
        with patch.object(c, "get_post", side_effect=[
            post(), post(), post()
        ]), patch.object(c, "wp_request",
                         side_effect=PublishError("HTTP 503")) as writer:
            c.snapshot()
            with self.assertRaises(PublishError):
                c.apply()
            writer.assert_called_once()

    def test_already_clean_never_post(self):
        with patch.object(c, "get_post", return_value=post(CLEAN)), \
             patch.object(c, "public_clean", return_value=True), \
             patch.object(c, "wp_request") as writer:
            c.snapshot()
            c.apply()
            writer.assert_not_called()

    def test_public_page_must_really_omit_expired_code(self):
        good = "<html><h1>Který kreatin vybrat?</h1>" + (
            "<p>Kreatin, srovnání a etiketa.</p>" * 25) + "</html>"
        self.assertTrue(c.public_clean(reader=lambda _:good))
        self.assertFalse(c.public_clean(reader=lambda _:
            good.replace("</html>","<p>5NM2022</p></html>")))
        self.assertFalse(c.public_clean(reader=lambda _:
            "<html><h1>Not this blog</h1>" + "xxx"*300 + "</html>"))


if __name__ == "__main__":
    unittest.main()
