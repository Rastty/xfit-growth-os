"""Single, rollback-safe removal of expired coupon blocks from WP 11945.

Keep this independently auditable: only one pinned WordPress article may be
updated, only after a full-source rollback artifact has been uploaded by CI.
Never retry a POST whose final state has not been reconciled.
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts.xfit_coupon_cleanup import get_post, sha, stripped
from scripts.xfit_coupon_recovery_11595 import verify_public_coupon_absent

POST_ID = 11945
SLUG = "jak-kreatin-muze-pomoci-ziskat-svalovy-objem-v-fitness"
URL = "https://xfit.cz/" + SLUG + "/"
EXPECTED_REMOVALS = 3
BACKUP = Path("reports/backups/xfit-coupon-post-11945-recovery.json")


def inspect(post):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("status") != "publish"
            or post.get("slug") != SLUG or post.get("link") != URL):
        raise PublishError("Pinned published WordPress identity changed")
    parsed = urlsplit(post["link"])
    if (parsed.scheme != "https" or parsed.hostname != "xfit.cz"
            or parsed.username or parsed.password or parsed.port
            or parsed.query or parsed.fragment):
        raise PublishError("Unexpected canonical URL")
    raw = (post.get("content") or {}).get("raw")
    if not isinstance(raw, str) or not 500 <= len(raw.encode("utf-8")) <= 500000:
        raise PublishError("Missing or oversized raw body")
    after, count = stripped(raw)
    if count not in (0, EXPECTED_REMOVALS) or "5nm2022" in after.casefold():
        raise PublishError("Unexpected expired coupon content; manual review")
    return {"raw": raw, "after": after, "count": count,
            "before_sha256": sha(raw), "after_sha256": sha(after)}


def snapshot():
    current = inspect(get_post(POST_ID))
    if BACKUP.exists():
        raise PublishError("Refusing to overwrite existing backup")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "post_id": POST_ID, "slug": SLUG, "url": URL,
        "original_raw": current["raw"],
        "before_sha256": current["before_sha256"],
        "after_sha256": current["after_sha256"],
        "shortcodes_to_remove": current["count"], "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "SINGLE_POST_BACKUP_READY", "post_id": POST_ID,
                      "shortcodes_to_remove": current["count"], "remote_writes": 0}))


def apply():
    if not BACKUP.exists():
        raise PublishError("Mandatory prewrite backup missing")
    saved = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (not isinstance(saved, dict) or saved.get("schema") != 1
            or saved.get("post_id") != POST_ID or saved.get("slug") != SLUG
            or saved.get("url") != URL or saved.get("remote_writes") != 0):
        raise PublishError("Untrusted backup manifest")
    current = inspect(get_post(POST_ID))
    if any((current["raw"] != saved.get("original_raw"),
            current["before_sha256"] != saved.get("before_sha256"),
            current["after_sha256"] != saved.get("after_sha256"),
            current["count"] != saved.get("shortcodes_to_remove"))):
        raise PublishError("WordPress content changed since snapshot; no write")

    if current["count"] == 0:
        if not verify_public_coupon_absent(URL):
            raise PublishError("Authenticated clean state but public coupon remains")
        print(json.dumps({"state": "ALREADY_CLEAN_NO_WRITE", "post_id": POST_ID,
                          "post_attempts": 0, "public_site_modified": False}))
        return

    write_error = False
    try:
        accepted = wp_request(normalized_base(), "posts/" + str(POST_ID),
                              payload={"content": current["after"]})
        if (not isinstance(accepted, dict) or accepted.get("id") != POST_ID
                or accepted.get("status") != "publish"):
            write_error = True
    except (PublishError, OSError, ValueError, TypeError, KeyError):
        write_error = True

    try:
        remote = get_post(POST_ID)
        if (remote.get("id") != POST_ID or remote.get("status") != "publish"
                or remote.get("slug") != SLUG or remote.get("link") != URL):
            raise PublishError("Post identity drift after write")
        raw = (remote.get("content") or {}).get("raw")
        final_sha = sha(raw) if isinstance(raw, str) else None
    except (PublishError, OSError, ValueError, TypeError, KeyError):
        print(json.dumps({"state": "BLOCKED_MANUAL_REVIEW", "post_id": POST_ID,
                          "stage": "readback_unavailable", "write_error": write_error}))
        raise PublishError("Unknown write state; no retry")

    if final_sha == saved["before_sha256"]:
        print(json.dumps({"state": "UNRESOLVED_UNCHANGED", "post_id": POST_ID,
                          "post_attempts": 1, "public_site_modified": False}))
        raise PublishError("WordPress retained original body")
    if final_sha != saved["after_sha256"]:
        print(json.dumps({"state": "BLOCKED_MANUAL_REVIEW", "post_id": POST_ID,
                          "stage": "raw_body_drift", "post_attempts": 1}))
        raise PublishError("WordPress transformed content; no retry")
    if not verify_public_coupon_absent(URL):
        print(json.dumps({"state": "API_VERIFIED_PUBLIC_STALE", "post_id": POST_ID,
                          "post_attempts": 1}))
        raise PublishError("Public website still shows expired coupon")
    print(json.dumps({"state": "PUBLIC_VERIFIED", "post_id": POST_ID, "url": URL,
                      "posts_changed": 1, "shortcodes_removed": current["count"],
                      "post_attempts": 1, "public_site_modified": True,
                      "deletes": 0, "redirects": 0}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Usage: snapshot|apply")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, OSError, ValueError, TypeError, KeyError) as exc:
        print("XFIT_11945_RECOVERY_ERROR: " + type(exc).__name__, file=sys.stderr)
        sys.exit(2)
