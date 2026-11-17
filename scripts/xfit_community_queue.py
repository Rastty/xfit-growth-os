#!/usr/bin/env python3
"""Build a bounded, read-only Czech community-help queue.

The queue is deliberately *not* a posting bot. A search result alone never
authorizes a reply, advertising, account access, or a backlink. This module
only turns independently sourced public thread candidates into an auditable
manual-review plan, expiring them rather than silently recycling old leads.
"""

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


MAX_CANDIDATES = 30
FRESH_DAYS = 21
MAX_OBSERVATION_AGE_DAYS = 7
REDDIT_PATH = re.compile(r"/r/czech/comments/([a-z0-9]{5,10})/[\w-]+/\Z")
SAFE_SOURCES = {"reddit.com", "www.reddit.com"}
WEIGHTS = {"protein_cost": 4, "beginner_fitness": 3, "home_training": 2}
ALLOWED_STATES = {"discovered", "answered", "discarded"}


def strict_day(value):
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Invalid ISO calendar date")
    return date.fromisoformat(value)


def safe_thread_url(raw):
    if type(raw) is not str or len(raw) > 260:
        return False
    try:
        parsed = urlsplit(raw)
        decoded_path = unquote(parsed.path, errors="strict")
    except (ValueError, UnicodeDecodeError):
        return False
    return (parsed.scheme == "https" and parsed.hostname in SAFE_SOURCES
            and parsed.netloc == parsed.hostname and parsed.username is None
            and parsed.password is None and parsed.port is None
            and not parsed.query and not parsed.fragment
            and REDDIT_PATH.fullmatch(decoded_path) is not None)


def safe_reply_url(raw, thread):
    if not safe_thread_url(thread) or type(raw) is not str or len(raw) > 280:
        return False
    try:
        candidate = urlsplit(raw)
        base = urlsplit(thread)
        path = unquote(candidate.path, errors="strict")
        base_path = unquote(base.path, errors="strict")
    except (ValueError, UnicodeDecodeError):
        return False
    return (candidate.scheme == "https" and candidate.netloc == base.netloc
            and not candidate.query and not candidate.fragment
            and re.fullmatch(re.escape(base_path) + r"[a-z0-9]{5,10}/", path) is not None)


def compile_queue(data, *, today):
    """Fail closed on ungrounded or malformed leads; do not infer live replies."""
    if type(today) is not date or type(data) is not dict or set(data) != {"candidates"}:
        raise ValueError("Unexpected community input shape")
    candidates = data["candidates"]
    if type(candidates) is not list or len(candidates) > MAX_CANDIDATES:
        raise ValueError("Community candidate limit exceeded")
    seen_threads, seen_ids, queue = set(), set(), []
    for lead in candidates:
        expected = {"id", "url", "topic", "observed_on", "last_activity_on",
                    "state", "live_thread_verified", "rules_reviewed_on",
                    "reply_url", "affiliate_link_in_reply"}
        if type(lead) is not dict or set(lead) != expected:
            raise ValueError("Unexpected candidate keys")
        key, url, topic = lead["id"], lead["url"], lead["topic"]
        if (type(key) is not str or not re.fullmatch(r"[a-z0-9_-]{6,60}", key)
                or key in seen_ids or not safe_thread_url(url)
                or type(topic) is not str or topic not in WEIGHTS
                or type(lead["state"]) is not str or lead["state"] not in ALLOWED_STATES):
            raise ValueError("Duplicate, unsupported or unsafe community lead")
        thread_id = REDDIT_PATH.fullmatch(unquote(urlsplit(url).path))[1]
        if thread_id in seen_threads:
            raise ValueError("Duplicate source thread")
        observed = strict_day(lead["observed_on"])
        activity = strict_day(lead["last_activity_on"])
        reviewed = (strict_day(lead["rules_reviewed_on"])
                    if lead["rules_reviewed_on"] is not None else None)
        if not (activity <= observed <= today) or (reviewed is not None and
                not observed <= reviewed <= today):
            raise ValueError("Inconsistent evidence dates")
        if type(lead["live_thread_verified"]) is not bool:
            raise ValueError("Thread verification must be boolean")
        if type(lead["affiliate_link_in_reply"]) is not bool:
            raise ValueError("Reply disclosure flag must be boolean")
        reply = lead["reply_url"]
        if reply is not None and not safe_reply_url(reply, url):
            raise ValueError("Reply URL is not a verified exact thread URL")
        if lead["state"] == "answered" and reply is None:
            raise ValueError("Answered requires a public comment receipt")
        if lead["state"] != "answered" and reply is not None:
            raise ValueError("Unpublished candidate cannot have a reply receipt")
        if lead["affiliate_link_in_reply"]:
            raise ValueError("Affiliate promotion is out of scope for this pilot")

        age = (today - activity).days
        observation_age = (today - observed).days
        if lead["state"] == "answered":
            # A supplied receipt URL is not proof that Reddit still shows it.
            status, next_action = "CLAIMED_ANSWER_UNVERIFIED", "VERIFY_COMMENT_THEN_7_AND_30_DAY_EVIDENCE"
        elif lead["state"] == "discarded":
            status, next_action = "DISCARDED", "NONE"
        elif age > FRESH_DAYS:
            status, next_action = "EXPIRED", "DISCOVER_NEW_DISCUSSION"
        elif observation_age > MAX_OBSERVATION_AGE_DAYS:
            status, next_action = "STALE_OBSERVATION", "RECHECK_LIVE_THREAD"
        elif not lead["live_thread_verified"]:
            status, next_action = "UNVERIFIED_THREAD", "RECHECK_LIVE_THREAD"
        elif reviewed is None or (today - reviewed).days > MAX_OBSERVATION_AGE_DAYS:
            status, next_action = "RULES_NOT_CURRENT", "VERIFY_MODERATION_RULES"
        else:
            status, next_action = "HUMAN_REVIEW_ONLY", "DECIDE_IF_HELPFUL_NO_LINK_REPLY"
        seen_ids.add(key)
        seen_threads.add(thread_id)
        queue.append({"id": key, "url": url, "topic": topic,
                      "status": status, "next_action": next_action,
                      "last_activity_on": str(activity),
                      "days_since_activity": age,
                      "priority_score": max(0, WEIGHTS[topic] * 10 - age),
                      "ga4_reddit_sessions": "UNKNOWN",
                      "backlinks": "UNKNOWN", "commissions": "UNKNOWN"})
    queue.sort(key=lambda x: (x["status"] not in ("HUMAN_REVIEW_ONLY", "UNVERIFIED_THREAD", "RULES_NOT_CURRENT"),
                              -x["priority_score"], x["id"]))
    return {"date": str(today), "mode": "READ_ONLY_NO_AUTO_POST",
            "candidate_count": len(queue), "eligible_for_automatic_posting": 0,
            "candidates": queue, "website_modified": False,
            "external_comments_posted": 0}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default="config/xfit-community-queue.json")
    parser.add_argument("--today", default=str(date.today()))
    args = parser.parse_args(argv)
    result = compile_queue(json.loads(Path(args.candidates).read_text(encoding="utf-8")),
                           today=strict_day(args.today))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, TypeError, json.JSONDecodeError):
        print("XFIT_COMMUNITY_QUEUE_ERROR: invalid or unsafe evidence", file=sys.stderr)
        sys.exit(2)
