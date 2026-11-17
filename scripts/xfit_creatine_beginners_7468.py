"""One-post, rollback-backed correction of contradictory legacy creatine advice.

Only WP 7468 / its exact permalink is in scope. Snapshot and immutable Actions
backup must finish before the one possible authenticated content POST.
"""

import html
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts.xfit_coupon_cleanup import sha
from scripts.xfit_editorial_gate import EditorialError, check_document


POST_ID = 7468
SLUG = "kreatin-pro-zacatecniky-v-fitness-kdy-zacit-a-jakymi-davkami-zacinat"
URL = "https://xfit.cz/" + SLUG + "/"
TARGET = Path("content/revisions/creatine-beginners-7468.html")
BACKUP = Path("reports/backups/xfit-creatine-beginners-7468-original.json")
OLD_MARKERS = ("20-30g", "5-10g", "30 minut před tréninkem", "8 týdnů")
REVISED_MARKERS = (
    "Rychlá odpověď:",
    "Potřebuji kreatin hned na začátku?",
    "Jaké dávkování se objevuje ve studiích?",
    "Zdroje, omezení a aktualizace",
    "ods.od.nih.gov",
    "www.opss.org",
)


def get_post():
    return wp_request(normalized_base(),
        f"posts/{POST_ID}?context=edit&_fields=id,slug,status,link,modified_gmt,content")


def pinned(post):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("slug") != SLUG
            or post.get("status") != "publish" or post.get("link") != URL):
        raise PublishError("Target article identity changed")
    parsed = urlsplit(post["link"])
    if (parsed.scheme != "https" or parsed.hostname != "xfit.cz"
            or parsed.netloc != "xfit.cz" or parsed.query or parsed.fragment):
        raise PublishError("Unexpected URL identity")
    modified = post.get("modified_gmt")
    if not isinstance(modified, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d\d:\d\d:\d\d", modified):
        raise PublishError("Missing WP modification evidence")
    raw = (post.get("content") or {}).get("raw")
    if not isinstance(raw, str) or not 1000 <= len(raw.encode("utf-8")) <= 200000:
        raise PublishError("Unexpected raw body length")
    return raw, modified


def text_only(body):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", body)).split()).casefold()


def legacy(post):
    raw, modified = pinned(post)
    flattened = text_only(raw)
    if not all(marker.casefold() in flattened for marker in OLD_MARKERS):
        raise PublishError("Old contradictory evidence no longer matches; manual review")
    if "5nm2022" in flattened:
        raise PublishError("Unrecovered expired coupon detected")
    return raw, modified


def new_body():
    body = TARGET.read_text(encoding="utf-8")
    if (len(body.encode("utf-8")) < 4500 or not clean_revision(body)
            or re.search(r"<\s*(?:script|iframe|form|html|head|body)\b|on\w+\s*=", body, re.I)):
        raise PublishError("Unsafe or incomplete editorial revision")
    try:
        evidence = check_document({"content": body}, commercial=False)
    except EditorialError as exc:
        raise PublishError("Editorial gate blocked rewrite") from exc
    if evidence["word_count"] < 550 or evidence["h2_count"] < 5:
        raise PublishError("Article lacks practical depth")
    return body


def clean_revision(raw):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) < 4500:
        return False
    normalized = html.unescape(raw).casefold()
    visible = text_only(raw)
    return (all(marker.casefold() in normalized or marker.casefold() in visible
                for marker in REVISED_MARKERS)
            # The old timing claim may be quoted to explicitly debunk it.
            and not any(marker in visible for marker in ("20-30g", "5-10g"))
            and not re.search(r"<\s*(?:script|iframe|form|html|head|body)\b", raw, re.I))


def snapshot():
    before, modified = legacy(get_post())
    after = new_body()
    if BACKUP.exists():
        raise PublishError("Existing rollback backup cannot be overwritten")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "post_id": POST_ID, "slug": SLUG, "url": URL,
        "original_raw": before, "original_sha256": sha(before),
        "modified_gmt": modified, "target_sha256": sha(after),
        "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "BACKUP_READY_NO_WRITE", "post_id": POST_ID,
                      "original_sha256": sha(before), "remote_writes": 0}))


def public_verified():
    api_url = f"https://xfit.cz/wp-json/wp/v2/posts/{POST_ID}?_fields=id,slug,status,link,content"
    for url in (api_url, URL):
        try:
            with urlopen(Request(url, headers={"User-Agent": "XfitGrowthOS/1.0",
                                              "Cache-Control": "no-cache"}), timeout=25) as response:
                target = urlsplit(response.geturl())
                if response.status != 200 or target.hostname != "xfit.cz" or target.path != urlsplit(url).path:
                    raise PublishError("Public verification redirected or failed")
                content = response.read(2_000_001)
                if len(content) > 2_000_000:
                    raise PublishError("Public verification exceeded size limit")
        except (OSError, ValueError) as exc:
            raise PublishError("Public verification unavailable") from exc
        decoded = content.decode("utf-8", errors="replace")
        if url == api_url:
            post = json.loads(decoded)
            if (post.get("id") != POST_ID or post.get("slug") != SLUG
                    or post.get("status") != "publish" or post.get("link") != URL
                    or not clean_revision((post.get("content") or {}).get("rendered"))):
                raise PublishError("Public WordPress body not verified")
        else:
            compact = text_only(decoded)
            if not all(marker.casefold() in compact for marker in REVISED_MARKERS[:4]):
                raise PublishError("Public page missing updated user guidance")
    return True


def deploy():
    if not BACKUP.is_file():
        raise PublishError("Mandatory rollback file missing")
    saved = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (saved.get("schema") != 1 or saved.get("post_id") != POST_ID
            or saved.get("slug") != SLUG or saved.get("url") != URL
            or saved.get("remote_writes") != 0):
        raise PublishError("Invalid backup identity")
    before, modified = legacy(get_post())
    after = new_body()
    if (before != saved.get("original_raw") or sha(before) != saved.get("original_sha256")
            or modified != saved.get("modified_gmt")
            or sha(after) != saved.get("target_sha256")):
        raise PublishError("Source drift after mandatory snapshot")
    write_error = False
    try:
        result = wp_request(normalized_base(), f"posts/{POST_ID}", payload={"content": after})
        write_error = not isinstance(result, dict) or result.get("id") != POST_ID
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        write_error = True
    try:
        current, _modified = pinned(get_post())
    except (PublishError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"state": "UNKNOWN_NO_RETRY", "post_id": POST_ID,
                          "write_error": write_error}))
        raise PublishError("Ambiguous write, do not retry POST") from exc
    if sha(current) == saved["original_sha256"] or not clean_revision(current):
        raise PublishError("Write did not publish verified revision; no retry")
    public_verified()
    print(json.dumps({"state": "PUBLIC_VERIFIED", "post_id": POST_ID,
                      "url": URL, "articles_revised": 1, "post_attempts": 1,
                      "write_response_uncertain": write_error,
                      "new_posts": 0, "deletes": 0, "redirects": 0}))


def verify_only():
    current, _modified = pinned(get_post())
    if not clean_revision(current):
        raise PublishError("Expected revision not present")
    public_verified()
    print(json.dumps({"state": "ALREADY_LIVE_VERIFIED", "post_id": POST_ID,
                      "url": URL, "remote_writes": 0}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "deploy", "verify"):
            raise PublishError("Usage: snapshot|deploy|verify")
        {"snapshot": snapshot, "deploy": deploy, "verify": verify_only}[sys.argv[1]]()
    except (PublishError, OSError, ValueError, TypeError, KeyError) as exc:
        print("XFIT_CREATINE_7468_ERROR: " + type(exc).__name__, file=sys.stderr)
        sys.exit(2)
