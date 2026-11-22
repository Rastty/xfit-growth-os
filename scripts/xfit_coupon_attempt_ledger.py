"""Fail-closed, repository-owned at-most-once attempt ledger for old coupon cleanups.

Before *any* WordPress POST, reserve the complete intended batch of exact
numeric post IDs in a dedicated public GitHub issue. This is conservative:
a reserved post whose WP write never happened is skipped by future bulk
waves and requires an isolated source-reviewed recovery. Never send raw WP
HTML, affiliate IDs, campaign links or credentials to this public issue.
"""
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from scripts.wp_publish import PublishError

ISSUE = 363
API = "https://api.github.com/repos/Rastty/xfit-growth-os/issues/363"
TITLE = "XFIT coupon cleanup — immutable at-most-once attempted-post ledger"
MARKER = "<!-- XFIT_COUPON_ATTEMPT_LEDGER_V1 -->"
BLOCK = re.compile(
    re.escape(MARKER) + r"\s*\x60\x60\x60json\s*(\{[^\x60]*\})\s*\x60\x60\x60",
    re.S,
)
MAX_ATTEMPTS = 4500
MAX_ONE_BATCH = 8
MAX_POST_ID = 2**31 - 1


@dataclass(frozen=True)
class Ledger:
    updated_at: str
    body: str
    ids: tuple[int, ...]
    fingerprint: str


def _valid_ids(ids, *, allow_empty):
    if not isinstance(ids, list) or (not ids and not allow_empty):
        raise PublishError("Coupon issue ledger has invalid ID list")
    if len(ids) > MAX_ATTEMPTS:
        raise PublishError("Coupon issue ledger exhausted safe ID capacity")
    if any(type(p) is not int or not 0 < p <= MAX_POST_ID for p in ids):
        raise PublishError("Coupon issue ledger contains invalid post ID")
    if len(set(ids)) != len(ids) or ids != sorted(ids):
        raise PublishError("Coupon issue ledger IDs must be sorted and unique")
    return tuple(ids)


def fingerprint(ids):
    return hashlib.sha256(json.dumps(
        list(ids), separators=(",", ":")
    ).encode("ascii")).hexdigest()


def _request(method="GET", body=None):
    token = os.environ.get("XFIT_GITHUB_ISSUES_TOKEN", "").strip()
    if not token:
        raise PublishError("Missing scoped GitHub issue token, fail closed")
    if method not in ("GET", "PATCH"):
        raise PublishError("Unsupported GitHub ledger operation")
    data = None if body is None else json.dumps({"body": body}).encode("utf-8")
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "XFITCouponAttemptLedger/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = Request(API, headers=headers, data=data, method=method)
    # No repeat on PATCH: server may have saved a successful update.
    tries = 3 if method == "GET" else 1
    for i in range(tries):
        try:
            with urlopen(req, timeout=20) as response:
                if response.status != 200:
                    raise PublishError("GitHub issue ledger returned non-200")
                payload = response.read(70_001)
                if len(payload) > 70_000:
                    raise PublishError("GitHub issue ledger exceeded byte bound")
                return json.loads(payload)
        except (HTTPError, URLError, OSError, ValueError, TimeoutError) as exc:
            if i < tries - 1:
                time.sleep(i + 1)
                continue
            # Never log HTTP error bodies, URLs with tokens, or response content.
            raise PublishError("GitHub coupon ledger request could not be verified") from exc
    raise PublishError("GitHub coupon ledger unavailable")


def decode(response):
    if (not isinstance(response, dict) or response.get("number") != ISSUE
            or response.get("state") != "open" or response.get("title") != TITLE):
        raise PublishError("Wrong public GitHub coupon ledger issue")
    body, updated = response.get("body"), response.get("updated_at")
    if (not isinstance(body, str) or len(body.encode("utf-8")) > 65000
            or not isinstance(updated, str) or not updated):
        raise PublishError("GitHub coupon ledger metadata missing or too large")
    matches = list(BLOCK.finditer(body))
    if len(matches) != 1 or body.count(MARKER) != 1:
        raise PublishError("Coupon ledger marker must occur exactly once")
    try:
        doc = json.loads(matches[0].group(1))
    except (ValueError, TypeError) as exc:
        raise PublishError("Coupon ledger JSON is malformed") from exc
    if (not isinstance(doc, dict) or set(doc) != {
        "schema", "purpose", "attempted_ids",
    } or doc["schema"] != 1 or
            doc["purpose"] != "xfit_coupon_one_attempt_only"):
        raise PublishError("Coupon ledger schema drift")
    ids = _valid_ids(doc["attempted_ids"], allow_empty=True)
    return Ledger(updated, body, ids, fingerprint(ids))


def load():
    return decode(_request())


def reserve(old, post_ids):
    """Reserve *all* selected post IDs before any WordPress write.

    If issue state drifted, permissions are denied or POST response is
    ambiguous, stop before touching WordPress (even if GitHub saved IDs).
    """
    if not isinstance(old, Ledger) or not isinstance(post_ids, list):
        raise PublishError("Missing validated prewrite coupon ledger")
    if len(post_ids) > MAX_ONE_BATCH:
        raise PublishError("A coupon wave exceeded eight attempted posts")
    selected = _valid_ids(sorted(post_ids), allow_empty=True)
    if not selected:
        return old
    current = load()
    if (current.updated_at != old.updated_at or
            current.fingerprint != old.fingerprint or
            current.body != old.body or
            set(selected) & set(current.ids)):
        raise PublishError("Coupon ledger changed since rollback snapshot")
    combined = sorted(set(current.ids) | set(selected))
    if len(combined) > MAX_ATTEMPTS:
        raise PublishError("Coupon attempt ledger is full, no WP POST")
    match = BLOCK.search(current.body)
    doc = json.dumps({
        "schema": 1, "purpose": "xfit_coupon_one_attempt_only",
        "attempted_ids": combined,
    }, separators=(",", ":"), ensure_ascii=False)
    new_body = current.body[:match.start(1)] + doc + current.body[match.end(1):]
    if len(new_body.encode("utf-8")) > 65000:
        raise PublishError("Coupon attempt ledger size limit exceeded")
    # Exactly one GitHub PATCH. Read back before *any* WordPress POST.
    _request("PATCH", new_body)
    confirmed = load()
    if confirmed.ids != tuple(combined):
        raise PublishError("Coupon attempt reservation not verified; no WP writes")
    return confirmed
