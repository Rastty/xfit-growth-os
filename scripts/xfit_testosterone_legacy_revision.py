"""Single-URL, evidence-backed correction of an unsafe legacy booster ranking.

The WP post ID is discovered by its *exact* pinned slug via authenticated REST,
then frozen in a full backup before one possible POST. No bulk edits, no
redirects, no repeated POST after an ambiguous timeout and no auto retries.
"""

import html
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from scripts.wp_publish import PublishError, normalized_base, wp_request, verify_public
from scripts.xfit_coupon_cleanup import sha
from scripts.xfit_editorial_gate import check_document, EditorialError


SLUG = "pripravky-na-zvyseni-hladiny-testosteronu-srovnani"
URL = "https://xfit.cz/" + SLUG + "/"
TITLE = "Testosteronové boostery: účinky, rizika a co víme z výzkumu"
SOURCE = Path("content/revisions/testosterone-booster-evidence.html")
BACKUP = Path("reports/backups/xfit-testosterone-ranking-original.json")
OLD_PRODUCT_MARKERS = ("prime male", "testo fuel", "proman plus", "primulus")
OLD_TITLE_MARKERS = ("testosteronu", "srovnání")
NEW_MARKERS = (
    "Rychlá odpověď:",
    "Co je na původních",
    "Kdy má smysl řešit hladinu testosteronu",
    "Zdroje, omezení a aktualizace",
    "Redakční revize: 17. listopadu 2026",
)
FIELDS = "id,slug,status,link,title,modified_gmt,content,featured_media"


def visible(body):
    if not isinstance(body, str):
        return ""
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", body)).split()).casefold()


def revised(body):
    text = visible(body)
    return (isinstance(body, str) and len(body.encode("utf-8")) >= 4000
            and all(marker.casefold() in text for marker in NEW_MARKERS)
            and not any(product in text for product in OLD_PRODUCT_MARKERS)
            and not re.search(r"<\s*(?:script|iframe|form)\b|on\w+\s*=", body, re.I))


def reviewed_body():
    content = SOURCE.read_text(encoding="utf-8")
    if not revised(content):
        raise PublishError("Editorial evidence markers or safety restrictions failed")
    try:
        result = check_document({"content": content}, commercial=False)
    except EditorialError as exc:
        raise PublishError("Editorial gate rejected rewrite") from exc
    if result["word_count"] < 600 or result["h2_count"] < 5:
        raise PublishError("Revised explanation lacks substantive depth")
    return content


def _identity(post):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] <= 0 or post.get("slug") != SLUG
            or post.get("status") != "publish" or post.get("link") != URL):
        raise PublishError("Legacy article identity/status drift")
    parsed = urlsplit(post["link"])
    if (parsed.scheme != "https" or parsed.netloc != "xfit.cz"
            or parsed.query or parsed.fragment):
        raise PublishError("Unexpected legacy public identity")
    modified = post.get("modified_gmt")
    if not isinstance(modified, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d\d:\d\d:\d\d", modified):
        raise PublishError("Missing modification metadata")
    raw = (post.get("content") or {}).get("raw")
    if not isinstance(raw, str) or not 1000 <= len(raw.encode("utf-8")) <= 500000:
        raise PublishError("Missing or oversized editable source")
    if type(post.get("featured_media")) is not int:
        raise PublishError("Missing featured media metadata")
    title = (post.get("title") or {}).get("raw")
    if not isinstance(title, str) or not 12 <= len(title) <= 200:
        raise PublishError("Missing original editable title")
    return raw, title, modified


def _legacy(post):
    raw, title, modified = _identity(post)
    old_text = visible(raw)
    if (not all(value in old_text for value in OLD_PRODUCT_MARKERS)
            or not all(value in visible(title) for value in OLD_TITLE_MARKERS)
            or revised(raw)):
        raise PublishError("Unsafe old ranking is no longer exactly observed")
    return raw, title, modified


def discover():
    result = wp_request(normalized_base(), (
        "posts?slug=" + SLUG + "&context=edit&status=any&per_page=10&_fields=" + FIELDS))
    if not isinstance(result, list) or len(result) != 1:
        raise PublishError("Expected exactly one legacy post for pinned slug")
    _identity(result[0])
    return result[0]


def by_id(post_id):
    if type(post_id) is not int or post_id <= 0:
        raise PublishError("Invalid frozen post ID")
    result = wp_request(normalized_base(), f"posts/{post_id}?context=edit&_fields={FIELDS}")
    _identity(result)
    if result["id"] != post_id:
        raise PublishError("Frozen post ID drift")
    return result


def snapshot():
    after = reviewed_body()
    post = discover()
    before, title, modified = _legacy(post)
    if BACKUP.exists():
        raise PublishError("Immutable rollback file already exists")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": 1, "post_id": post["id"], "slug": SLUG, "url": URL,
        "original_raw": before, "original_title": title,
        "original_sha256": sha(before), "original_title_sha256": sha(title),
        "modified_gmt": modified, "featured_media": post["featured_media"],
        "revised_sha256": sha(after), "revised_title_sha256": sha(TITLE),
        "remote_writes": 0,
    }
    BACKUP.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "BACKUP_READY_NO_WRITE", "post_id": post["id"],
                      "original_sha256": sha(before), "remote_writes": 0}))


def deploy():
    if not BACKUP.is_file():
        raise PublishError("Mandatory rollback artifact absent")
    record = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (record.get("schema") != 1 or record.get("slug") != SLUG
            or record.get("url") != URL or record.get("remote_writes") != 0
            or type(record.get("post_id")) is not int):
        raise PublishError("Unexpected rollback metadata")
    post_id = record["post_id"]
    post = by_id(post_id)
    raw, title, modified = _legacy(post)
    body = reviewed_body()
    if (raw != record.get("original_raw") or title != record.get("original_title")
            or sha(raw) != record.get("original_sha256")
            or sha(title) != record.get("original_title_sha256")
            or modified != record.get("modified_gmt")
            or post["featured_media"] != record.get("featured_media")
            or sha(body) != record.get("revised_sha256")
            or sha(TITLE) != record.get("revised_title_sha256")):
        raise PublishError("Legacy source changed since mandatory snapshot")
    uncertain = False
    try:
        response = wp_request(normalized_base(), f"posts/{post_id}",
                              payload={"content": body, "title": TITLE})
        uncertain = not isinstance(response, dict) or response.get("id") != post_id
    except (PublishError, OSError, ValueError, TypeError):
        uncertain = True
    try:
        readback = by_id(post_id)
    except (PublishError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"state": "UNKNOWN_NO_RETRY", "post_id": post_id}))
        raise PublishError("Ambiguous POST; do not retry") from exc
    current, current_title, _ = _identity(readback)
    if (not revised(current) or visible(current) != visible(body)
            or visible(current_title) != visible(TITLE)):
        raise PublishError("Authenticated readback mismatch; no retry")
    # Public check may fail while cache is stale: never repeat the content POST.
    verify_public(URL, TITLE, body)
    print(json.dumps({"state": "PUBLIC_VERIFIED", "post_id": post_id,
                      "url": URL, "legacy_posts_revised": 1,
                      "write_response_uncertain": uncertain, "post_attempts": 1,
                      "new_posts": 0, "deletes": 0, "redirects": 0}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "deploy"):
            raise PublishError("Usage: snapshot|deploy")
        {"snapshot": snapshot, "deploy": deploy}[sys.argv[1]]()
    except (PublishError, OSError, ValueError, TypeError, KeyError) as exc:
        print("XFIT_TESTOSTERONE_SAFETY_ERROR: " + type(exc).__name__, file=sys.stderr)
        sys.exit(2)
