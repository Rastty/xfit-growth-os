import unittest
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from scripts.wp_publish import PublishError
from scripts import xfit_coupon_cleanup as c
from scripts.xfit_coupon_cleanup import stripped,sha,QUARANTINE_IDS
class CouponCleanupTests(unittest.TestCase):
    def test_failed_post_is_quarantined_until_isolated_recovery(self):
        self.assertIn(11595,QUARANTINE_IDS)
        self.assertIn(11945,QUARANTINE_IDS)
        self.assertIn(11264,QUARANTINE_IDS)
        self.assertIn(10995,QUARANTINE_IDS)

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
        with tempfile.TemporaryDirectory() as temp, patch.object(
                c,"BACKUP",Path(temp)/"rollback.json"), \
                patch.object(c,"get_post",side_effect=[response(before),response(after)]), \
                patch.object(c,"wp_request",return_value={"id":911,"status":"publish"}) as post, \
                patch.object(c,"normalized_base",return_value="https://xfit.cz"), \
                patch.object(c,"public_readback",return_value={"verified_post_ids":[],
                    "not_verified":[{"id":911,"state":"EXPIRED_COUPON_VISIBLE"}]}), \
                patch.object(c.time,"sleep"),patch("sys.stdout",new_callable=io.StringIO) as output:
            c.BACKUP.write_text(json.dumps({"wave":"coupon01","entries":[entry],
                                           "remote_writes":0}))
            with self.assertRaises(PublishError):
                c.apply()
            self.assertEqual(post.call_count,1)
            self.assertIn("coupon_wave_public_unverified",output.getvalue())
