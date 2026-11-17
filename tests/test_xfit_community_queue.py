"""The acquisition pilot may find discussions but must never auto-post."""

import copy
from datetime import date
import json
from pathlib import Path
import unittest

from scripts.xfit_community_queue import (
    compile_queue, safe_reply_url, safe_thread_url,
)


TODAY = date(2026, 11, 17)
SOURCE = Path(__file__).resolve().parents[1] / "config/xfit-community-queue.json"


def leads():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


class CommunityQueueTests(unittest.TestCase):
    def test_real_candidates_expire_and_dont_post(self):
        result = compile_queue(leads(), today=TODAY)
        self.assertEqual(result["mode"], "READ_ONLY_NO_AUTO_POST")
        self.assertEqual(result["external_comments_posted"], 0)
        self.assertEqual(result["eligible_for_automatic_posting"], 0)
        self.assertEqual([x["status"] for x in result["candidates"]],
                         ["UNVERIFIED_THREAD", "EXPIRED", "EXPIRED"])
        self.assertEqual(result["candidates"][0]["next_action"],
                         "RECHECK_LIVE_THREAD")
        self.assertTrue(all(x["commissions"] == "UNKNOWN" for x in result["candidates"]))

    def test_exact_czech_subreddit_and_no_tracking_links(self):
        self.assertTrue(safe_thread_url(leads()["candidates"][1]["url"]))
        for url in (
            "https://reddit.com/r/czech/comments/1wy1491/protein/?utm_source=xfit",
            "https://www.reddit.com.evil.com/r/czech/comments/1wy1491/protein/",
            "http://www.reddit.com/r/czech/comments/1wy1491/protein/",
            "https://www.reddit.com/r/slovakia/comments/1wy1491/protein/",
            "https://www.reddit.com/r/czech/comments/1wy1491/protein%2Fextra/",
            "https://www.reddit.com/r/czech/comments/1wy1491/protein/#comment",
        ):
            with self.subTest(url=url):
                self.assertFalse(safe_thread_url(url))

    def test_reply_receipt_must_match_exact_thread(self):
        source = leads()
        candidate = source["candidates"][0]
        receipt = candidate["url"] + "abc123/"
        self.assertTrue(safe_reply_url(receipt, candidate["url"]))
        self.assertFalse(safe_reply_url(receipt + "?campaign=ads", candidate["url"]))
        candidate["state"] = "answered"
        candidate["reply_url"] = receipt
        result = compile_queue(source, today=TODAY)
        self.assertEqual(result["candidates"][0]["status"], "CLAIMED_ANSWER_UNVERIFIED")
        self.assertEqual(result["external_comments_posted"], 0)

    def test_answer_requires_receipt(self):
        source = leads()
        source["candidates"][0]["state"] = "answered"
        with self.assertRaises(ValueError):
            compile_queue(source, today=TODAY)

    def test_duplicate_thread_even_with_different_slug(self):
        source = leads()
        duplicate = copy.deepcopy(source["candidates"][0])
        duplicate["id"] = "reddit_same_thread_other_slug"
        duplicate["url"] = duplicate["url"].replace("/protein/", "/other/")
        source["candidates"].append(duplicate)
        with self.assertRaises(ValueError):
            compile_queue(source, today=TODAY)

    def test_unsafe_or_inconsistent_evidence_fails_closed(self):
        for field, value in (("topic", "health_diagnosis"),
                             ("observed_on", "2026-11-18"),
                             ("last_activity_on", "2026-11-18"),
                             ("affiliate_link_in_reply", True),
                             ("live_thread_verified", "true"),
                             ("rules_reviewed_on", "2026-11-18")):
            with self.subTest(field=field):
                source = leads()
                source["candidates"][0][field] = value
                with self.assertRaises(ValueError):
                    compile_queue(source, today=TODAY)

    def test_rule_check_and_expiry_after_last_activity(self):
        source = {"candidates": [leads()["candidates"][0]]}
        lead = source["candidates"][0]
        lead["live_thread_verified"] = True
        result = compile_queue(source, today=TODAY)
        self.assertEqual(result["candidates"][0]["status"], "RULES_NOT_CURRENT")
        lead["rules_reviewed_on"] = "2026-11-17"
        result = compile_queue(source, today=TODAY)
        self.assertEqual(result["candidates"][0]["status"], "HUMAN_REVIEW_ONLY")
        result = compile_queue(source, today=date(2026, 12, 5))
        self.assertEqual(result["candidates"][0]["status"], "EXPIRED")


if __name__ == "__main__":
    unittest.main()
