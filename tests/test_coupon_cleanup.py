import unittest
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from scripts.wp_publish import PublishError
from scripts import xfit_coupon_cleanup as c
from scripts.xfit_coupon_cleanup import stripped,sha,QUARANTINE_IDS
from scripts.xfit_coupon_attempt_ledger import Ledger, fingerprint
class CouponCleanupTests(unittest.TestCase):
    def test_failed_post_is_quarantined_until_isolated_recovery(self):
        self.assertIn(11595,QUARANTINE_IDS)
        self.assertIn(11945,QUARANTINE_IDS)
        self.assertIn(11264,QUARANTINE_IDS)
        self.assertIn(10995,QUARANTINE_IDS)
        # One unchanged post in run 45008217157 must never block new batches.
        self.assertIn(10860,QUARANTINE_IDS)
        self.assertIn(10830,QUARANTINE_IDS)
        self.assertEqual(c.MAX_COUNT, 8)

    def test_accelerated_cadence_keeps_eight_post_prewrite_release(self):
        workflow = Path(".github/workflows/xfit-coupon-cleanup-wave01.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("cron: '17 2,5,8,11,14,17,20,23 * * *'", workflow)
        self.assertEqual(workflow.count("    - cron:"), 1)
        self.assertEqual(c.MAX_COUNT, 8)
        self.assertIn("xfit-wp-heavy-reads", workflow)
        self.assertIn("xfit_coupon_cleanup snapshot", workflow)
        self.assertIn("xfit_coupon_cleanup apply", workflow)
        self.assertIn("if-no-files-found: error", workflow)
        self.assertIn("issues: write",workflow)
        self.assertIn("XFIT_GITHUB_ISSUES_TOKEN:",workflow)

        self.assertLess(workflow.index("xfit_coupon_cleanup snapshot"),
                        workflow.index("actions/upload-artifact@v4"))
        self.assertLess(workflow.index("actions/upload-artifact@v4"),
                        workflow.index("xfit_coupon_cleanup apply"))
        self.assertIn("QUARANTINE_IDS", Path("scripts/xfit_coupon_cleanup.py").read_text(
            encoding="utf-8"
        ))

    def test_pagination_passes_previously_attempted_coupon_sources(self):
        old_ids = tuple(range(1,101))
        ledger=Ledger("2026-11-22T11:00:00Z","body",old_ids,fingerprint(old_ids))
        def source(i):
            slug=f"coupon-{i}"
            return {"id":i,"slug":slug,"link":f"https://xfit.cz/{slug}/",
                    "status":"publish","content":{"raw":
                        "<p>Prokazatelně původní článek o výživě. </p>"*35 +
                        "[su_button]5NM2022[/su_button]"}}
        with tempfile.TemporaryDirectory() as root, \
             patch.object(c,"BACKUP",Path(root)/"backup.json"), \
             patch.object(c,"ledger_load",return_value=ledger), \
             patch.object(c,"retry_read",
                          side_effect=[[source(i) for i in range(1,101)],
                                       [source(i) for i in range(101,109)]]) as get, \
             patch.object(c,"wp_request") as writer:
            c.snapshot()
            saved=json.loads(c.BACKUP.read_text(encoding="utf-8"))
            self.assertEqual([x["id"] for x in saved["entries"]],
                             list(range(101,109)))
            self.assertEqual(saved["ledger_issue"],363)
            self.assertEqual(saved["ledger_fingerprint"],ledger.fingerprint)
            self.assertEqual(saved["search_pages_examined"],2)
            self.assertEqual(get.call_count,2)
            self.assertIn("page=2",get.call_args_list[-1].args[0])
            writer.assert_not_called()

    def test_unverified_ledger_reservation_prevents_all_wp_posts(self):
        slug="neprepisovat"
        old=("<p>Obsah článku o cvičení a výživě. </p>"*40+
             "[su_button]5NM2022[/su_button]")
        after,count=c.stripped(old)
        entry={"id":811,"slug":slug,"link":f"https://xfit.cz/{slug}/",
               "original_raw":old,"before_sha256":c.sha(old),
               "after_sha256":c.sha(after),"shortcodes_removed":count}
        ledger=Ledger("2026-11-22T11:00:00Z","body",(),fingerprint(()))
        post={"id":811,"slug":slug,"link":entry["link"],"status":"publish",
              "content":{"raw":old}}
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(c,"BACKUP",Path(temp)/"rollback.json"), \
             patch.object(c,"ledger_load",return_value=ledger), \
             patch.object(c,"ledger_reserve",
                          side_effect=PublishError("GitHub readback failed")) as reserve, \
             patch.object(c,"get_post",return_value=post), \
             patch.object(c,"wp_request") as writer:
            c.BACKUP.write_text(json.dumps({
                "wave":"coupon01","entries":[entry],"remote_writes":0,
                "ledger_issue":363,"ledger_updated_at":ledger.updated_at,
                "ledger_fingerprint":ledger.fingerprint,
            }),encoding="utf-8")
            with self.assertRaisesRegex(PublishError,"GitHub readback failed"):
                c.apply()
            reserve.assert_called_once()
            writer.assert_not_called()

    def test_only_explicit_2022_promo_shortcode_removed(self):
        s=(('Užitečný odstavec. '*40)+
          '[su_button url="https://xfit.cz/damske-obleceni" background="#2def4c"]'
          'FITNESS OBLEČENÍ V AKCI - slevový kód: 5NM2022[/su_button]'
          '<h2>Důležité informace</h2><p>Čtenářská hodnota</p>')
        out,count=stripped(s)
        self.assertEqual(count,1)
        self.assertNotIn("5NM2022",out)
        self.assertIn("<h2>Důležité informace</h2>",out)
    def test_other_coupon_untouched(self):
        original='<p>Aktuální slevový kupon</p>[su_button]KOD2026[/su_button]'
        updated,count=stripped(original)
        self.assertEqual(count,0)
        self.assertEqual(updated,original)
    def test_historical_mention_not_removed(self):
        original='<p>Před lety jsme psali o 5NM2022, který už neplatí.</p>'
        self.assertEqual(stripped(original),(original,0))
    def test_hash_is_deterministic(self):
        self.assertEqual(sha("abc"),sha("abc"))
        self.assertNotEqual(sha("abc"),sha("abd"))

    def test_public_attestation_requires_exact_post_url_and_zero_visible_mentions(self):
        entry={"id":811,"slug":"konkretni-clanek",
               "link":"https://xfit.cz/konkretni-clanek/"}
        calls=[]
        def reader(post_id,slug):
            calls.append((post_id,slug))
            return {"id":post_id,"url":"https://xfit.cz/"+slug+"/",
                    "state":"PUBLIC_NO_COUPON_OBSERVED","visible_mentions":0}
        proof=c.public_readback([entry],reader=reader,sleeper=lambda _:None)
        self.assertEqual(proof["verified_post_ids"],[811])
        self.assertEqual(proof["not_verified"],[])
        self.assertEqual(calls,[(811,"konkretni-clanek")])

    def test_public_attestation_retries_stale_cache_without_rewriting_wp(self):
        entry={"id":812,"slug":"druhy-clanek",
               "link":"https://xfit.cz/druhy-clanek/"}
        responses=iter(["EXPIRED_COUPON_VISIBLE","UNVERIFIED_FETCH",
                        "PUBLIC_NO_COUPON_OBSERVED"])
        waits=[]
        def reader(post_id,slug):
            state=next(responses)
            return {"id":post_id,"url":c.expected_url(slug),"state":state,
                    "visible_mentions":0 if state=="PUBLIC_NO_COUPON_OBSERVED" else 1}
        proof=c.public_readback([entry],reader=reader,sleeper=waits.append)
        self.assertEqual(proof["verified_post_ids"],[812])
        self.assertEqual(waits,[4,4])

    def test_false_clean_or_wrong_identity_never_becomes_public_proof(self):
        entry={"id":813,"slug":"treti-clanek",
               "link":"https://xfit.cz/treti-clanek/"}
        for response in (
            {"id":999,"url":c.expected_url(entry["slug"]),
             "state":"PUBLIC_NO_COUPON_OBSERVED","visible_mentions":0},
            {"id":813,"url":"https://evil.test/treti-clanek/",
             "state":"PUBLIC_NO_COUPON_OBSERVED","visible_mentions":0},
            {"id":813,"url":c.expected_url(entry["slug"]),
             "state":"PUBLIC_NO_COUPON_OBSERVED","visible_mentions":3},
            {"id":813,"url":c.expected_url(entry["slug"]),
             "state":"UNVERIFIED_IDENTITY","visible_mentions":0},
        ):
            with self.subTest(state=response):
                proof=c.public_readback([entry],reader=lambda *_:response,sleeper=lambda _:None)
                self.assertFalse(proof["verified_post_ids"])
                self.assertEqual(len(proof["not_verified"]),1)

    def test_reject_noncanonical_source_before_public_probe(self):
        entry={"id":811,"slug":"konkretni-clanek",
               "link":"https://xfit.cz/other/"}
        with patch.object(c,"probe") as reader:
            with self.assertRaises(PublishError):
                c.public_readback([entry],reader=reader)
            reader.assert_not_called()
        bad={"id":811,"slug":"konkretni-clanek","status":"publish",
             "link":"https://xfit.cz/other/","content":{"raw":"text"}}
        with self.assertRaises(PublishError):
            c.validate(bad)

    def test_authenticated_success_with_unproven_public_page_is_failure_no_retry(self):
        slug="clanek-s-kuponem"
        before=("<p>Redakční text věnovaný sportu a výživě. </p>"*22
                +"[su_button]Nabídka 5NM2022[/su_button]")
        after,count=c.stripped(before)
        self.assertEqual(count,1)
        url=c.expected_url(slug)
        entry={"id":911,"slug":slug,"link":url,"original_raw":before,
               "before_sha256":c.sha(before),"after_sha256":c.sha(after),
               "shortcodes_removed":1}
        def response(body):
            return {"id":911,"slug":slug,"status":"publish","link":url,
                    "content":{"raw":body}}
        ledger=Ledger("2026-11-22T11:00:00Z","body",(),fingerprint(()))
        reserved=Ledger("2026-11-22T11:01:00Z","newbody",(911,),fingerprint((911,)))
        with tempfile.TemporaryDirectory() as temp, patch.object(
                c,"BACKUP",Path(temp)/"rollback.json"), \
                patch.object(c,"ledger_load",return_value=ledger), \
                patch.object(c,"ledger_reserve",return_value=reserved) as reserve, \
                patch.object(c,"get_post",side_effect=[response(before),response(after)]), \
                patch.object(c,"wp_request",return_value={"id":911,"status":"publish"}) as post, \
                patch.object(c,"normalized_base",return_value="https://xfit.cz"), \
                patch.object(c,"public_readback",return_value={"verified_post_ids":[],
                    "not_verified":[{"id":911,"state":"EXPIRED_COUPON_VISIBLE"}]}), \
                patch.object(c.time,"sleep"),patch("sys.stdout",new_callable=io.StringIO) as output:
            c.BACKUP.write_text(json.dumps({"wave":"coupon01","entries":[entry],
                                           "remote_writes":0,"ledger_issue":363,
                                           "ledger_updated_at":ledger.updated_at,
                                           "ledger_fingerprint":ledger.fingerprint}))
            with self.assertRaises(PublishError):
                c.apply()
            self.assertEqual(post.call_count,1)
            reserve.assert_called_once()
            self.assertEqual(reserve.call_args.args[1],[911])
            self.assertIn("COUPON_ATTEMPTS_RESERVED_BEFORE_WP",output.getvalue())
            self.assertIn("coupon_wave_public_unverified",output.getvalue())
