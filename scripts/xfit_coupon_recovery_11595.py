"""Recover only Xfit WordPress post 11595 after 2026-11-08 partial 2022 coupon wave.

The earlier batch has seven verified successful posts. NEVER re-run that
batch here. This task snapshots one precisely pinned post before a single
possible POST; no delete, draft, redirects or edits beyond stale 5NM2022
su_button shortcodes. A failed POST is reconciled by authenticated readback.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts.xfit_coupon_cleanup import get_post, sha, stripped

POST_ID = 11595
EXPECTED_REMOVALS = 3
BACKUP = Path("reports/backups/xfit-coupon-post-11595-recovery.json")
HOSTS = frozenset(("xfit.cz", "www.xfit.cz"))
SAFE_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
MAX_RAW_BYTES = 500000


def classify(post):
    """A single known owned published article and exact narrow expired promo."""
    if not isinstance(post, dict) or type(post.get("id")) is not int or post["id"] != POST_ID:
        raise PublishError("Pinned WordPress ID mismatch")
    slug = post.get("slug")
    if post.get("status") != "publish" or not isinstance(slug, str) or not SAFE_SLUG.fullmatch(slug):
        raise PublishError("Unexpected WordPress slug/status")
    url = post.get("link")
    if not isinstance(url, str):
        raise PublishError("Missing canonical post URL")
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in HOSTS or
            parsed.username or parsed.password or parsed.port or
            parsed.query or parsed.fragment or parsed.path.rstrip("/") != "/" + slug):
        raise PublishError("Unexpected published permalink")
    raw = (post.get("content") or {}).get("raw")
    if not isinstance(raw, str) or not 500 <= len(raw) <= MAX_RAW_BYTES:
        raise PublishError("Missing or unsafe source body")
    after, removals = stripped(raw)
    if removals not in (0, EXPECTED_REMOVALS):
        raise PublishError("Expired promotion match count changed; manual review required")
    if removals == EXPECTED_REMOVALS and "5nm2022" in after.casefold():
        # Removing buttons must not accidentally leave an active unreviewed
        # expired code or rewrite unrelated mentions without a review.
        raise PublishError("Other coupon mention requires manual review")
    return {
        "post_id": POST_ID,
        "slug": slug,
        "url": "https://xfit.cz/" + slug + "/",
        "before_sha256": sha(raw),
        "after_sha256": sha(after),
        "shortcodes_to_remove": removals,
        "original_raw": raw,
    }


def snapshot():
    prepared = classify(get_post(POST_ID))
    if BACKUP.exists():
        raise PublishError("Backup path unexpectedly exists; no overwrite")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema_version": 1, "purpose": "one_post_2022_coupon_recovery",
        "target_id": POST_ID, "entry": prepared,
        "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "state": "SINGLE_POST_BACKUP_READY",
        "post_id": POST_ID,
        "shortcodes_to_remove": prepared["shortcodes_to_remove"],
        "remote_writes": 0,
    }))


def verify_public_coupon_absent(url, *, public_reader=None):
    """Read-only, no-cache check that the current canonical page lacks the code."""
    if public_reader is not None:
        body = public_reader(url)
        return isinstance(body, str) and "5NM2022" not in body.upper()
    req = urllib.request.Request(url, headers={
        "User-Agent": "XfitExpiredCouponReadback/1.0",
        "Cache-Control": "no-cache", "Pragma": "no-cache",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                final = urllib.parse.urlsplit(response.geturl())
                expected = urllib.parse.urlsplit(url)
                if (response.status != 200 or final.scheme != "https" or
                        final.hostname not in HOSTS or final.path.rstrip("/") != expected.path.rstrip("/")
                        or final.query or final.fragment):
                    raise PublishError("Unexpected public redirect/identity")
                data = response.read(2_000_001)
                if len(data) > 2_000_000:
                    raise PublishError("Oversized public page; no proof")
                body = data.decode("utf-8", errors="replace")
                if "<h1" in body.casefold() and "5NM2022" not in body.upper():
                    return True
        except (OSError, ValueError) as exc:
            if attempt == 2:
                raise PublishError("Public readback unavailable") from exc
        if attempt < 2:
            time.sleep(3)
    return False


def apply():
    if not BACKUP.exists():
        raise PublishError("Mandatory pre-write backup missing")
    obj = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (not isinstance(obj, dict) or obj.get("schema_version") != 1 or
            obj.get("target_id") != POST_ID or
            obj.get("purpose") != "one_post_2022_coupon_recovery" or
            obj.get("remote_writes") != 0):
        raise PublishError("Untrusted recovery manifest")
    prior = obj.get("entry")
    if not isinstance(prior, dict) or prior.get("post_id") != POST_ID:
        raise PublishError("Untrusted recovery target")

    # On any drift, fail closed. Do not overwrite a concurrent editor.
    current = classify(get_post(POST_ID))
    for field in ("slug", "url", "before_sha256", "after_sha256",
                  "shortcodes_to_remove"):
        if current[field] != prior.get(field):
            raise PublishError("Source changed after snapshot; do not write")

    if current["shortcodes_to_remove"] == 0:
        print(json.dumps({
            "state": "ALREADY_CLEAN_NO_WRITE", "post_id": POST_ID,
            "shortcodes_removed": 0, "public_site_modified": False,
        }))
        return

    original = current["original_raw"]
    after, count = stripped(original)
    if count != EXPECTED_REMOVALS or sha(after) != current["after_sha256"]:
        raise PublishError("Target no longer matches expected safe edit")

    # Exactly one attempted authenticated POST. Never retry a timed-out
    # write: WordPress may have saved it despite a network error.
    write_error = False
    try:
        response = wp_request(normalized_base(), "posts/" + str(POST_ID),
                              payload={"content": after})
        if (not isinstance(response, dict) or response.get("id") != POST_ID
                or response.get("status") != "publish"):
            write_error = True
    except (PublishError, OSError, ValueError, TypeError, KeyError):
        write_error = True

    # Reconcile success/failure via a fresh authenticated API read, without
    # trusting an HTTP 200 alone or silently posting a second time.
    try:
        readback = get_post(POST_ID)
        if (readback.get("id") != POST_ID or readback.get("slug") != prior["slug"]
                or readback.get("status") != "publish"):
            raise PublishError("Post identity/status changed after POST")
        final_body = (readback.get("content") or {}).get("raw")
        digest = sha(final_body) if isinstance(final_body, str) else ""
    except (PublishError, OSError, ValueError, TypeError, KeyError):
        print(json.dumps({"state":"BLOCKED_MANUAL_REVIEW","post_id":POST_ID,
                          "stage":"authenticated_readback_unavailable",
                          "write_response_uncertain":write_error}))
        raise PublishError("Write final state unknown; NEVER retry blindly")

    if digest == prior["before_sha256"]:
        print(json.dumps({"state":"UNRESOLVED_UNCHANGED","post_id":POST_ID,
                          "post_attempts":1,"public_site_modified":False}))
        raise PublishError("Post remained unchanged after the single authorized write")
    if digest != prior["after_sha256"]:
        print(json.dumps({"state":"BLOCKED_MANUAL_REVIEW","post_id":POST_ID,
                          "stage":"content_hash_drift","post_attempts":1}))
        raise PublishError("Unexpected WordPress transformation/concurrent edit")

    # A successful authenticated readback is still not public evidence.
    if not verify_public_coupon_absent(prior["url"]):
        print(json.dumps({"state":"API_VERIFIED_PUBLIC_STALE","post_id":POST_ID,
                          "post_attempts":1,"public_site_modified":True}))
        raise PublishError("WP updated but public cache still renders expired coupon")

    print(json.dumps({
        "state": "PUBLIC_VERIFIED", "post_id":POST_ID,
        "shortcodes_removed":count, "posts_changed":1,
        "post_attempts":1, "public_site_modified":True,
        "url": prior["url"], "deletes":0, "redirects":0,
    }))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Usage: snapshot|apply")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, OSError, ValueError, TypeError, KeyError) as exc:
        # Never expose raw content, WordPress app passwords or affiliate IDs.
        print("XFIT_COUPON_RECOVERY_ERROR: " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)
