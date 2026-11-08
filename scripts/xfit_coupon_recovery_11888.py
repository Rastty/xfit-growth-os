"""Complete only the one unresolved 2022 coupon post from the Nov 1 wave.

Historical authenticated rollback artifact 13077688224 proves this exact
original source and its three removable 5NM2022 shortcode blocks. On ANY
source drift do not write. Mandatory fresh backup before one possible POST.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from scripts.xfit_coupon_cleanup import get_post, sha, stripped
from scripts.wp_publish import PublishError, normalized_base, wp_request

POST_ID = 11888
SLUG = "nejnovejsi-vyzkum-ktery-kreatin-je-nejucinnejsi-pro-fitness-v-roce-2022"
URL = "https://xfit.cz/" + SLUG + "/"
BEFORE_SHA = "9ba46c6319b124cc708acbba32f7aa9e53abf6871a999bea4555799c7f597f37"
AFTER_SHA = "e10d06a0a2bebe3f7ac3b6500515b4cb91f6aa36cf3514d0500902ac672cd496"
REMOVALS = 3
BACKUP = Path("reports/backups/xfit-coupon-11888-recovery.json")


def state(post):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("status") != "publish"
            or post.get("slug") != SLUG):
        raise PublishError("Pinned WordPress owner/status mismatch")
    value = post.get("link")
    if not isinstance(value, str):
        raise PublishError("Missing canonical WordPress permalink")
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != "https" or parsed.hostname not in ("xfit.cz", "www.xfit.cz")
            or parsed.username or parsed.password or parsed.port or parsed.query
            or parsed.fragment or parsed.path.rstrip("/") != "/" + SLUG):
        raise PublishError("Unexpected canonical URL")
    raw = (post.get("content") or {}).get("raw")
    if not isinstance(raw, str) or len(raw) < 500 or len(raw.encode("utf-8")) > 500000:
        raise PublishError("Missing or invalid raw WordPress body")
    current_sha = sha(raw)
    if current_sha == AFTER_SHA:
        if "5nm2022" in raw.casefold():
            raise PublishError("Already-clean checksum but stale promo still present")
        return {"mode": "clean", "before": raw, "after": raw,
                "before_sha": current_sha}
    if current_sha != BEFORE_SHA:
        raise PublishError("Live article differs from the Nov 1 backup; do not overwrite")
    updated, count = stripped(raw)
    if (count != REMOVALS or sha(updated) != AFTER_SHA
            or "5nm2022" in updated.casefold()):
        raise PublishError("Expected three safe promo shortcodes not found")
    return {"mode": "update", "before": raw, "after": updated,
            "before_sha": current_sha}


def snapshot():
    current = state(get_post(POST_ID))
    if BACKUP.exists():
        raise PublishError("Refusing to overwrite rollback backup")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "post_id": POST_ID, "slug": SLUG,
        "source": "original Nov 1 backup artifact 13077688224 + current WP GET",
        "mode": current["mode"], "before_sha": current["before_sha"],
        "after_sha": sha(current["after"]),
        "original_raw": current["before"], "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "BACKUP_READY_11888", "post_id": POST_ID,
                      "needs_write": current["mode"] == "update",
                      "remote_writes": 0}))


def public_clean(*, reader=None):
    """Independently check exactly the owned public page, no cache-busting URL."""
    def acceptable(body):
        if not isinstance(body, str) or len(body) < 700:
            return False
        low = body.casefold()
        return "5nm2022" not in low and "<h1" in low and "kreatin" in low

    if reader is not None:
        return acceptable(reader(URL))
    request = urllib.request.Request(URL, headers={
        "User-Agent": "XFITCouponOnePostReadback/1.0",
        "Cache-Control": "no-cache", "Pragma": "no-cache",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                final = urllib.parse.urlsplit(response.geturl())
                if (response.status != 200 or final.scheme != "https"
                        or final.hostname not in ("xfit.cz", "www.xfit.cz")
                        or final.username or final.password or final.port
                        or final.query or final.fragment
                        or final.path.rstrip("/") != "/" + SLUG):
                    raise PublishError("Unexpected public permalink/redirect")
                body = response.read(2_000_001)
                if len(body) > 2_000_000:
                    raise PublishError("Public page too large")
                if acceptable(body.decode("utf-8", errors="replace")):
                    return True
        except (OSError, ValueError) as exc:
            if attempt == 2:
                raise PublishError("Public readback unavailable") from exc
        if attempt < 2:
            time.sleep(3)
    return False


def apply():
    if not BACKUP.exists():
        raise PublishError("Mandatory prewrite rollback missing")
    saved = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (not isinstance(saved, dict) or saved.get("schema") != 1
            or saved.get("post_id") != POST_ID or saved.get("slug") != SLUG
            or saved.get("remote_writes") != 0):
        raise PublishError("Invalid rollback snapshot")
    current = state(get_post(POST_ID))
    if (current["mode"] != saved.get("mode")
            or current["before_sha"] != saved.get("before_sha")
            or current["before"] != saved.get("original_raw")
            or sha(current["after"]) != saved.get("after_sha")):
        raise PublishError("Concurrent source drift since snapshot; no write")

    if current["mode"] == "clean":
        if not public_clean():
            raise PublishError("Authenticated WP clean but public page stale")
        print(json.dumps({"state": "ALREADY_CLEAN_NO_WRITE",
                          "post_id": POST_ID, "public_site_modified": False,
                          "post_attempts": 0, "url": URL}))
        return

    # One and only one POST. An exception does NOT imply it failed remotely.
    write_error = False
    try:
        accepted = wp_request(normalized_base(), "posts/" + str(POST_ID),
                              payload={"content": current["after"]})
        if (not isinstance(accepted, dict)
                or accepted.get("id") != POST_ID
                or accepted.get("status") != "publish"):
            write_error = True
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        write_error = True

    try:
        verified = get_post(POST_ID)
        if (verified.get("id") != POST_ID or verified.get("slug") != SLUG
                or verified.get("status") != "publish"):
            raise PublishError("Post identity changed after POST")
        raw = (verified.get("content") or {}).get("raw")
        final_sha = sha(raw) if isinstance(raw, str) else None
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"state": "BLOCKED_MANUAL_REVIEW", "post_id": POST_ID,
                          "reason": "ambiguous_authenticated_readback",
                          "write_response_uncertain": write_error}))
        raise PublishError("Unknown remote write state; do not repeat POST")

    if final_sha == BEFORE_SHA:
        print(json.dumps({"state": "UNRESOLVED_UNCHANGED", "post_id": POST_ID,
                          "post_attempts": 1, "public_site_modified": False}))
        raise PublishError("Post remained unchanged after one write attempt")
    if final_sha != AFTER_SHA:
        print(json.dumps({"state": "BLOCKED_MANUAL_REVIEW", "post_id": POST_ID,
                          "reason": "unexpected_final_content",
                          "post_attempts": 1}))
        raise PublishError("WordPress transformed or changed the body")

    if not public_clean():
        print(json.dumps({"state": "API_VERIFIED_PUBLIC_STALE",
                          "post_id": POST_ID, "post_attempts": 1,
                          "public_site_modified": True}))
        raise PublishError("Public page still displays the old promotion")
    print(json.dumps({
        "state": "PUBLIC_VERIFIED", "post_id": POST_ID,
        "slug": SLUG, "url": URL,
        "posts_changed": 1, "shortcodes_removed": REMOVALS,
        "post_attempts": 1, "public_site_modified": True,
        "deletes": 0, "redirects": 0, "new_posts": 0,
    }))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Usage: snapshot|apply")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, OSError, ValueError, KeyError, TypeError) as exc:
        print("XFIT_11888_RECOVERY_ERROR: " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)
