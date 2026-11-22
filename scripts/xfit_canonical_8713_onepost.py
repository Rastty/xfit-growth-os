"""Fail-closed, source-bound canonical repair for original WordPress post 8713.

Only one exact example.com canonical link token may be removed from its raw
content. Full original authenticated source is archived before one content-only
POST. Public verification is required. Never retry an uncertain POST.
Uses the already-tested surgical token parser from the #9008 release.
"""
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts.xfit_canonical_9008_onepost import (
    bogus, canonicals, digest, remove_one_bogus_canonical,
)

POST_ID = 8713
BASE = "https://xfit.cz"
FIELDS = "id,slug,status,link,title,content,modified_gmt,featured_media"
BACKUP = Path("reports/backups/xfit-canonical-8713-full-original.json")
MAX_PAGE_BYTES = 2_000_000
DATE_RE = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\Z")


def canonical_url(url, slug):
    if not isinstance(url, str) or not isinstance(slug, str):
        return False
    try:
        u = urlsplit(url)
        return (u.scheme == "https" and u.netloc == "xfit.cz"
                and u.path == "/" + slug + "/" and u.port is None
                and not u.username and not u.password and not u.query
                and not u.fragment and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug))
    except ValueError:
        return False


def source(post):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("status") != "publish"
            or not canonical_url(post.get("link"), post.get("slug"))):
        raise PublishError("Wrong pinned original WordPress identity")
    raw = (post.get("content") or {}).get("raw")
    title = (post.get("title") or {}).get("raw")
    modified = post.get("modified_gmt")
    media = post.get("featured_media")
    if (not isinstance(raw, str) or not 1000 <= len(raw.encode("utf-8")) <= 350000
            or not isinstance(title, str) or len(title.strip()) < 8
            or not isinstance(modified, str) or not DATE_RE.fullmatch(modified)
            or type(media) is not int):
        raise PublishError("Authenticated source is missing or incomplete")
    return {"id": POST_ID, "slug": post["slug"], "link": post["link"],
            "raw": raw, "title": title, "modified_gmt": modified,
            "featured_media": media, "original_sha256": digest(raw)}


def remote():
    return wp_request(normalized_base(), f"posts/{POST_ID}?context=edit&_fields={FIELDS}")


def get_public(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc != "xfit.cz"
            or parsed.username or parsed.password or parsed.fragment):
        raise PublishError("Public verification URL is outside exact XFIT origin")
    req = Request(url, headers={"User-Agent": "XFIT8713Onepost/1.0",
                                "Cache-Control": "no-cache"}, method="GET")
    with urlopen(req, timeout=25) as response:
        if response.status != 200 or response.geturl() != url:
            raise PublishError("Public origin redirected or response not 200")
        blob = response.read(MAX_PAGE_BYTES + 1)
    if len(blob) > MAX_PAGE_BYTES:
        raise PublishError("Oversized public page")
    return blob.decode("utf-8", errors="replace")


def public_rest(src):
    route = f"{BASE}/wp-json/wp/v2/posts/{POST_ID}?_fields=id,slug,status,link,modified_gmt"
    result = json.loads(get_public(route))
    if (not isinstance(result, dict) or result.get("id") != POST_ID
            or result.get("slug") != src["slug"]
            or result.get("link") != src["link"]
            or result.get("status") != "publish"
            or not isinstance(result.get("modified_gmt"), str)):
        raise PublishError("Public REST original ID/slug/permalink mismatch")
    return result


def public_counts(html, permalink):
    values = canonicals(html)
    return {"total": len(values),
            "self": sum(u == permalink for u in values),
            "wrong_example": sum(bogus(u) for u in values)}


def before_ok(html, permalink):
    return public_counts(html, permalink) == {
        "total": 2, "self": 1, "wrong_example": 1}


def after_ok(html, permalink):
    return public_counts(html, permalink) == {
        "total": 1, "self": 1, "wrong_example": 0}


def snapshot():
    first = source(remote())
    fresh = source(remote())
    if first != fresh:
        raise PublishError("Authenticated source changed during preflight")
    updated = remove_one_bogus_canonical(first["raw"])
    rest = public_rest(first)
    if rest["modified_gmt"] != first["modified_gmt"]:
        raise PublishError("Public REST source modification time differs")
    public = get_public(first["link"])
    if not before_ok(public, first["link"]):
        raise PublishError("Fresh public page does not prove one wrong body canonical")
    if BACKUP.exists():
        raise PublishError("Immutable original backup exists; no overwriting")
    record = {
        "schema": 1, "source": first, "revised_sha256": digest(updated),
        "public_before_sha256": hashlib.sha256(public.encode("utf-8")).hexdigest(),
        "public_canonical_counts": public_counts(public, first["link"]),
        "wordpress_post_attempts": 0,
    }
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps(record, ensure_ascii=False),
                      encoding="utf-8")
    print(json.dumps({"state": "SOURCE_AND_PUBLIC_VERIFIED_BACKUP_READY",
                      "post_id": POST_ID, "wordpress_post_attempts": 0}))


def deploy():
    if not BACKUP.is_file():
        raise PublishError("Original source archive not uploaded")
    record = json.loads(BACKUP.read_text(encoding="utf-8"))
    current = source(remote())
    updated = remove_one_bogus_canonical(current["raw"])
    if (record.get("schema") != 1 or record.get("source") != current
            or record.get("wordpress_post_attempts") != 0
            or record.get("revised_sha256") != digest(updated)
            or record.get("public_canonical_counts")
            != {"total": 2, "self": 1, "wrong_example": 1}):
        raise PublishError("Source changed after rollback backup; refusing POST")
    rest = public_rest(current)
    if rest["modified_gmt"] != current["modified_gmt"]:
        raise PublishError("Public REST unexpectedly changed before POST")
    if not before_ok(get_public(current["link"]), current["link"]):
        raise PublishError("Fresh page no longer shows exactly the reviewed defect")
    uncertain_response = False
    try:
        response = wp_request(normalized_base(), f"posts/{POST_ID}",
                              payload={"content": updated})
        if (not isinstance(response, dict) or response.get("id") != POST_ID
                or response.get("status") != "publish"):
            uncertain_response = True
    except (PublishError, OSError, ValueError, TypeError):
        uncertain_response = True
    # Never retry, even if HTTP timed out; the server might have committed.
    try:
        verified = source(remote())
    except (PublishError, OSError, ValueError, TypeError) as exc:
        raise PublishError("Postwrite authenticated state UNKNOWN_NO_RETRY") from exc
    if (verified["raw"] != updated or
            any(verified[k] != current[k] for k in
                ("id", "slug", "link", "title", "featured_media"))
            or canonicals(verified["raw"])):
        raise PublishError("Postwrite source mismatch; UNKNOWN_NO_RETRY")
    for attempt in range(3):
        try:
            rest_new = public_rest(verified)
            if (rest_new["modified_gmt"] == verified["modified_gmt"]
                    and after_ok(get_public(current["link"]), current["link"])):
                print(json.dumps({"state": "PUBLIC_CANONICAL_VERIFIED",
                                  "post_id": POST_ID, "url": current["link"],
                                  "wordpress_post_attempts": 1,
                                  "posts_changed": 1, "new_posts": 0,
                                  "redirects": 0, "deletes": 0,
                                  "public_canonicals": 1,
                                  "uncertain_write_response": uncertain_response}))
                return
        except (PublishError, OSError, ValueError, TypeError):
            pass
        if attempt < 2:
            time.sleep(3)
    raise PublishError("Public proof incomplete; UNKNOWN_NO_RETRY")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in {"snapshot", "deploy"}:
            raise PublishError("Expected snapshot or deploy")
        (snapshot if sys.argv[1] == "snapshot" else deploy)()
    except (PublishError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"state": "BLOCKED_NO_BLIND_RETRY",
                          "post_id": POST_ID, "error_type": type(exc).__name__}),
              file=sys.stderr)
        raise SystemExit(2)
