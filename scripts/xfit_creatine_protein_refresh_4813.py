"""Pinned, source-backed replacement of one inaccurate legacy article.

Use only snapshot -> upload rollback artifact -> apply. Never bulk update or
silently retry a WP POST after an ambiguous response. Keep the original ID,
slug, metadata, excerpt, categories, author and featured image unchanged.
"""
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts.xfit_editorial_gate import check_document


POST_ID = 4813
SLUG = "kreatin-a-protein-rozdily-vyhody-a-nevyhody-pro-sportovce"
URL = "https://xfit.cz/" + SLUG + "/"
TITLE = "Kreatin a protein: Rozdíly, výhody a nevýhody pro sportovce"
MODIFIED_GMT = "2023-05-03T18:40:23"
PUBLIC_RENDERED_SHA = "ae41348d8dce8fc2a940c8dcfe54b65927027aa06b758a0a727d3561b352e97a"
CONTENT = Path("content/revisions/kreatin-protein-4813.html")
BACKUP = Path("reports/backups/xfit-creatine-protein-4813-original.json")
SIGNATURE = "Kreatin a protein řeší dvě různé věci."
SOURCE = "https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/"
DESTINATION = "https://xfit.cz/xfit-os-kreatin-nebo-protein/"


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def public_rest():
    # Use the immutable numeric ID for REST and validate the returned URL.
    endpoint = ("https://xfit.cz/wp-json/wp/v2/posts/" + str(POST_ID) +
                "?_fields=id,slug,status,link,modified_gmt,title,content")
    req = Request(endpoint, headers={"User-Agent": "XFIT4813SafetyRelease/1.0",
                                     "Cache-Control": "no-cache"})
    with urlopen(req, timeout=25) as resp:
        if resp.status != 200:
            raise PublishError("Public REST status not 200")
        data = resp.read(2_000_001)
    if len(data) > 2_000_000:
        raise PublishError("Public REST body too large")
    return json.loads(data)


def remote():
    return wp_request(normalized_base(), "posts/" + str(POST_ID) +
        "?context=edit&_fields=id,slug,status,link,title,content,modified_gmt")


def identity(post):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("slug") != SLUG
            or post.get("status") != "publish"
            or post.get("modified_gmt") != MODIFIED_GMT):
        raise PublishError("Legacy post identity, status or version drifted")
    uri = urlsplit(post.get("link") or "")
    if (uri.scheme != "https" or uri.hostname not in ("xfit.cz", "www.xfit.cz")
            or uri.username or uri.password or uri.port or uri.query or uri.fragment
            or uri.path.rstrip("/") != "/" + SLUG):
        raise PublishError("Legacy permalink drifted")
    title = (post.get("title") or {}).get("raw") or (post.get("title") or {}).get("rendered")
    if html.unescape(re.sub(r"<[^>]+>", "", title or "")).strip() != TITLE:
        raise PublishError("Legacy title drifted")


def before_public():
    post = public_rest()
    identity(post)
    rendered = (post.get("content") or {}).get("rendered")
    if not isinstance(rendered, str) or sha(rendered) != PUBLIC_RENDERED_SHA:
        raise PublishError("Public content changed since pinned read-only review")
    if "5NM2022" not in rendered:
        raise PublishError("Legacy coupon fingerprint missing")
    return post


def revision():
    body = CONTENT.read_text(encoding="utf-8")
    if (len(body) < 8000 or SIGNATURE not in body
            or body.count(DESTINATION) != 1
            or body.count(SOURCE) != 1
            or "5NM2022" in body or "kortikálního záření" in body
            or re.search(r"<\s*(?:script|iframe|form)\b|\bon\w+\s*=", body, re.I)):
        raise PublishError("Revision failed single-article editorial guard")
    checks = check_document({"title": TITLE, "content": body})
    if checks["word_count"] < 900 or checks["h2_count"] < 6:
        raise PublishError("Revision too thin for full legacy replacement")
    if len(checks["source_hosts"]) < 2:
        raise PublishError("Insufficient scientific source diversity")
    return body


def raw(post):
    body = (post.get("content") or {}).get("raw")
    if not isinstance(body, str):
        raise PublishError("Authenticated raw source missing")
    return body


def snapshot():
    revision_body = revision()
    before_public()
    post = remote()
    identity(post)
    original = raw(post)
    if len(original) < 5000 or "5NM2022" not in original:
        raise PublishError("Legacy authenticated content cannot be safely identified")
    if BACKUP.exists():
        raise PublishError("Backup target exists; refusing overwrite")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "post_id": POST_ID, "slug": SLUG,
        "modified_gmt": MODIFIED_GMT, "public_rendered_sha": PUBLIC_RENDERED_SHA,
        "original_sha": sha(original), "revision_sha": sha(revision_body),
        "original_authenticated_post": post, "remote_writes": 0,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"state": "BACKUP_READY", "post_id": POST_ID,
                      "original_sha": sha(original), "remote_writes": 0}))


def public_page():
    req = Request(URL, headers={"User-Agent": "XFIT4813SafetyRelease/1.0",
                                "Cache-Control": "no-cache"})
    with urlopen(req, timeout=25) as resp:
        final = urlsplit(resp.geturl())
        if (resp.status != 200 or final.scheme != "https"
                or final.hostname not in ("xfit.cz", "www.xfit.cz")
                or final.path.rstrip("/") != "/" + SLUG
                or final.query or final.fragment):
            raise PublishError("Public page did not preserve exact URL")
        page = resp.read(2_000_001)
    if len(page) > 2_000_000:
        raise PublishError("Public page too large")
    return page.decode("utf-8", errors="replace")


def verify_public():
    for attempt in range(3):
        try:
            page = public_page()
            public_post = public_rest()
            rendered = (public_post.get("content") or {}).get("rendered") or ""
            if (public_post.get("id") == POST_ID and public_post.get("slug") == SLUG
                    and public_post.get("status") == "publish"
                    and SIGNATURE in page and SIGNATURE in rendered
                    and DESTINATION in page and SOURCE in rendered
                    and "5NM2022" not in page and "5NM2022" not in rendered):
                return True
        except (OSError, ValueError, PublishError):
            pass
        if attempt < 2:
            time.sleep(4)
    return False


def apply():
    if not BACKUP.exists():
        raise PublishError("Missing uploaded prewrite backup")
    backup = json.loads(BACKUP.read_text(encoding="utf-8"))
    body = revision()
    old = backup.get("original_authenticated_post")
    if (backup.get("schema") != 1 or backup.get("post_id") != POST_ID
            or backup.get("slug") != SLUG or backup.get("modified_gmt") != MODIFIED_GMT
            or backup.get("public_rendered_sha") != PUBLIC_RENDERED_SHA
            or backup.get("remote_writes") != 0 or not isinstance(old, dict)
            or backup.get("revision_sha") != sha(body)):
        raise PublishError("Backup or revision integrity mismatch")
    identity(old)
    original = raw(old)
    if backup.get("original_sha") != sha(original):
        raise PublishError("Original backup content hash mismatch")
    before_public()
    current = remote()
    identity(current)
    if raw(current) != original:
        raise PublishError("Authenticated source changed after snapshot")

    # One POST only: an HTTP timeout might mean the server has already written.
    uncertain = False
    try:
        response = wp_request(normalized_base(), "posts/" + str(POST_ID),
                              payload={"content": body})
        if (not isinstance(response, dict) or response.get("id") != POST_ID
                or response.get("status") != "publish"):
            uncertain = True
    except (PublishError, OSError, ValueError, TypeError):
        uncertain = True
    try:
        after = remote()
        if (after.get("id") != POST_ID or after.get("slug") != SLUG
                or after.get("status") != "publish"):
            raise PublishError("Post-write identity drift")
        verified_raw = raw(after) == body
    except (PublishError, OSError, ValueError, TypeError, AttributeError):
        print(json.dumps({"state": "UNRESOLVED_NO_RETRY", "post_id": POST_ID,
                          "post_attempts": 1, "write_response_uncertain": uncertain}))
        raise PublishError("Cannot safely retry ambiguous post write")
    if not verified_raw:
        print(json.dumps({"state": "UNRESOLVED_NO_RETRY", "post_id": POST_ID,
                          "post_attempts": 1, "write_response_uncertain": uncertain}))
        raise PublishError("Authenticated post-write raw body mismatch")
    if not verify_public():
        print(json.dumps({"state": "API_VERIFIED_PUBLIC_STALE", "post_id": POST_ID,
                          "post_attempts": 1, "write_response_uncertain": uncertain}))
        raise PublishError("Authenticated change saved but public verification pending")
    print(json.dumps({"state": "LIVE_VERIFIED", "post_id": POST_ID, "url": URL,
                      "post_attempts": 1, "posts_changed": 1,
                      "public_site_modified": True, "coupon_removed": True}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Usage: snapshot|apply")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print("XFIT4813_RELEASE_ERROR: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
