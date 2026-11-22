"""Only numeric reviewed post IDs can become durable coupon attempt state."""
import json
import unittest
from unittest.mock import patch

from scripts import xfit_coupon_attempt_ledger as ledger
from scripts.wp_publish import PublishError


def response(ids, *, updated="2026-11-22T10:00:00Z", title=ledger.TITLE,
             state="open", extra_body=""):
    body = (
        "Machine-owned XFIT coupon attempt ledger.\n\n"
        + ledger.MARKER + "\n\x60\x60\x60json\n"
        + json.dumps({
            "schema":1,
            "purpose":"xfit_coupon_one_attempt_only",
            "attempted_ids":ids,
        }, separators=(",", ":")) + "\n\x60\x60\x60\n" + extra_body
    )
    return {"number":ledger.ISSUE, "title":title, "state":state,
            "body":body, "updated_at":updated}


class CouponAttemptLedgerTests(unittest.TestCase):
    def test_existing_issue_identity_and_sorted_ids(self):
        record = ledger.decode(response([10830,10860,10995]))
        self.assertEqual(record.ids, (10830,10860,10995))
        self.assertEqual(record.updated_at, "2026-11-22T10:00:00Z")
        self.assertEqual(record.fingerprint, ledger.fingerprint(record.ids))
        self.assertNotIn("Bearer", record.body)

    def test_tampering_with_owner_issue_fails_closed(self):
        bad = [
            response([1], title="Different issue"),
            response([1], state="closed"),
            {**response([1]), "number":42},
            response([1,1]),
            response([2,1]),
            response([0]),
            response([True]),
            response(["10830"]),
            response([1], extra_body=ledger.MARKER),
            {**response([1]), "body":"missing ledger"},
        ]
        for item in bad:
            with self.subTest(case=item):
                with self.assertRaises(PublishError):
                    ledger.decode(item)

    def test_reserve_adds_ids_once_with_readback_before_wp(self):
        initial = response([10830,10860])
        newer = response([10830,10860,10870,10880],updated="2026-11-22T10:01:00Z")
        calls=[]
        def network(method="GET", body=None):
            calls.append((method,body))
            if method=="PATCH":
                self.assertIn('"attempted_ids":[10830,10860,10870,10880]',body)
                return newer
            return initial if len(calls)==1 else newer
        old=ledger.decode(initial)
        with patch.object(ledger,"_request",side_effect=network):
            result=ledger.reserve(old,[10880,10870])
        self.assertEqual(result.ids,(10830,10860,10870,10880))
        self.assertEqual([i[0] for i in calls],["GET","PATCH","GET"])

    def test_attempted_post_is_never_reserved_again(self):
        old=ledger.decode(response([10830,10860]))
        with patch.object(ledger,"_request",return_value=response([10830,10860])) as get:
            with self.assertRaisesRegex(PublishError,"changed since"):
                ledger.reserve(old,[10830])
            get.assert_called_once()

    def test_concurrent_issue_update_aborts_before_patch(self):
        old=ledger.decode(response([10830,10860]))
        changed=response([10830,10860,10900],updated="2026-11-22T10:05:00Z")
        with patch.object(ledger,"_request",return_value=changed) as read:
            with self.assertRaisesRegex(PublishError,"changed since"):
                ledger.reserve(old,[10870])
            read.assert_called_once()

    def test_unknown_or_failed_patch_is_not_retried(self):
        old=ledger.decode(response([10830]))
        commands=[]
        def network(method="GET",body=None):
            commands.append(method)
            if method=="PATCH":
                raise PublishError("PATCH timed out")
            return response([10830])
        with patch.object(ledger,"_request",side_effect=network):
            with self.assertRaisesRegex(PublishError,"timed out"):
                ledger.reserve(old,[10870])
        self.assertEqual(commands,["GET","PATCH"])

    def test_missing_token_fails_without_request(self):
        with patch.dict(ledger.os.environ, {"XFIT_GITHUB_ISSUES_TOKEN":""}):
            with patch.object(ledger,"urlopen") as send:
                with self.assertRaisesRegex(PublishError,"Missing scoped"):
                    ledger._request()
                send.assert_not_called()

    def test_unknown_write_rejected_if_verification_lacks_id(self):
        old=ledger.decode(response([10830]))
        actual=response([10830],updated="2026-11-22T10:02:00Z")
        count=0
        def response_sequence(method="GET", body=None):
            nonlocal count
            count+=1
            if count==1:return response([10830])
            if count==2:return actual
            return actual
        with patch.object(ledger,"_request",side_effect=response_sequence):
            with self.assertRaisesRegex(PublishError,"not verified"):
                ledger.reserve(old,[10870])

    def test_batch_limit_enforced_before_api_call(self):
        old=ledger.decode(response([10830]))
        with patch.object(ledger,"_request") as network:
            with self.assertRaisesRegex(PublishError,"eight"):
                ledger.reserve(old,list(range(1,10)))
            network.assert_not_called()


if __name__=="__main__":
    unittest.main()
