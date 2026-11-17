"""Exact-post, immutable-backup WordPress revision of unsafe postoperative Pilates claims.

This is a one-off editorial release: only WP 5929 content can be modified,
only once, after the complete original source is uploaded as an Actions artifact.
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


POST_ID = 5929
SLUG = "jak-pilates-pro-zada-muze-pomoci-pri-rehabilitaci-po-urazu-nebo-operaci-zad"
URL = "https://xfit.cz/" + SLUG + "/"
TARGET = Path("content/revisions/pilates-after-surgery-5929.html")
BACKUP = Path("reports/backups/xfit-pilates-after-surgery-5929-original.json")
LEGACY_MARKERS = (
    "pilates pro záda je skvělou volbou",
    "nenechte se omezovat bolestivými zády",
    "s naším pilates instruktorem",
)
REVISED_MARKERS = (
    "Rychlá odpověď:",
    "Operace zad: čí plán má přednost?",
    "Po úrazu bez operace:",
    "Kdy je nutná okamžitá pomoc",
    "Pět otázek na fyzioterapeuta",
    "Zdroje, rozsah a aktualizace",
    "www.rnoh.nhs.uk",
    "www.cuh.nhs.uk",
)
UNSAFE_ELEMENTS = re.compile(r"<\s*(?:script|iframe|form|html|head|body)\b|on\w+\s*=", re.I)


def get_post():
    return wp_request(normalized_base(),
        f"posts/{POST_ID}?context=edit&_fields=id,slug,status,link,modified_gmt,content")


def text_only(body):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", body)).split()).casefold()


def pinned(post):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("slug") != SLUG
            or post.get("status") != "publish" or post.get("link") != URL):
        raise PublishError("Post identity no longer exact")
    parsed = urlsplit(post["link"])
    if (parsed.scheme != "https" or parsed.netloc != "xfit.cz"
            or parsed.query or parsed.fragment):
        raise PublishError("Unexpected post permalink")
    modified = post.get("modified_gmt")
    if not isinstance(modified, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d\d:\d\d:\d\d", modified):
        raise PublishError("Missing modified timestamp")
    raw = (post.get("content") or {}).get("raw")
    if not isinstance(raw, str) or not 1000 <= len(raw.encode("utf-8")) <= 200000:
        raise PublishError("Unexpected WordPress source body")
    return raw, modified


def old_body():
    before, modified = pinned(get_post())
    visible = text_only(before)
    if not all(marker in visible for marker in LEGACY_MARKERS):
        raise PublishError("Legacy medical-risk evidence changed; stop for review")
    return before, modified


def clean_revision(body):
    if not isinstance(body, str) or not 5500 <= len(body.encode("utf-8")) <= 30000:
        return False
    visible = text_only(body)
    normalized = html.unescape(body).casefold()
    return (all(marker.casefold() in visible or marker.casefold() in normalized
                for marker in REVISED_MARKERS)
            and not any(marker in visible for marker in LEGACY_MARKERS)
            and not UNSAFE_ELEMENTS.search(body)
            and "https://xfit.cz/jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates/" in body)


def new_body():
    revised = TARGET.read_text(encoding="utf-8")
    if not clean_revision(revised):
        raise PublishError("Incomplete or unsafe Pilates correction")
    try:
        stats = check_document({"content": revised}, commercial=False)
    except EditorialError as exc:
        raise PublishError("Editorial gate rejected correction") from exc
    if stats["word_count"] < 600 or stats["h2_count"] < 6:
        raise PublishError("Medical guidance depth inadequate")
    return revised


def snapshot():
    before, modified = old_body()
    after = new_body()
    if BACKUP.exists():
        raise PublishError("Refusing to overwrite existing rollback backup")
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
    public_api = f"https://xfit.cz/wp-json/wp/v2/posts/{POST_ID}?_fields=id,slug,status,link,content"
    for url in (public_api, URL):
        try:
            with urlopen(Request(url, headers={"User-Agent": "XfitGrowthOS/1.0",
                                              "Cache-Control": "no-cache"}), timeout=25) as response:
                target = urlsplit(response.geturl())
                if (response.status != 200 or target.hostname != "xfit.cz"
                        or target.path != urlsplit(url).path):
                    raise PublishError("Public readback redirected or failed")
                payload = response.read(2_000_001)
                if len(payload) > 2_000_000:
                    raise PublishError("Oversized public readback")
        except (OSError, ValueError) as exc:
            raise PublishError("Public readback unavailable") from exc
        decoded = payload.decode("utf-8", errors="replace")
        if url == public_api:
            record = json.loads(decoded)
            if (record.get("id") != POST_ID or record.get("slug") != SLUG
                    or record.get("status") != "publish" or record.get("link") != URL
                    or not clean_revision((record.get("content") or {}).get("rendered"))):
                raise PublishError("Public REST content failed identity or revision check")
        else:
            visible = text_only(decoded)
            if not all(marker.casefold() in visible for marker in REVISED_MARKERS[:6]):
                raise PublishError("Public page missing revised guidance")


def deploy():
    if not BACKUP.is_file():
        raise PublishError("Mandatory prewrite rollback missing")
    saved = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (saved.get("schema") != 1 or saved.get("post_id") != POST_ID
            or saved.get("slug") != SLUG or saved.get("url") != URL
            or saved.get("remote_writes") != 0):
        raise PublishError("Backup identity or write count invalid")
    before, modified = old_body()
    revised = new_body()
    if (before != saved.get("original_raw") or sha(before) != saved.get("original_sha256")
            or modified != saved.get("modified_gmt")
            or sha(revised) != saved.get("target_sha256")):
        raise PublishError("WordPress source changed since snapshot")
    write_error = False
    try:
        response = wp_request(normalized_base(), f"posts/{POST_ID}", payload={"content": revised})
        write_error = not isinstance(response, dict) or response.get("id") != POST_ID
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        write_error = True
    try:
        current, _modified = pinned(get_post())
    except (PublishError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"state": "UNKNOWN_NO_RETRY", "post_id": POST_ID}))
        raise PublishError("Ambiguous write outcome; no second POST") from exc
    if sha(current) == saved["original_sha256"] or not clean_revision(current):
        raise PublishError("WP write not confirmed; do not retry")
    public_verified()
    print(json.dumps({"state": "PUBLIC_VERIFIED", "post_id": POST_ID,
                      "url": URL, "articles_revised": 1, "post_attempts": 1,
                      "write_response_uncertain": write_error,
                      "new_posts": 0, "deletes": 0, "redirects": 0}))


def verify_only():
    current, _modified = pinned(get_post())
    if not clean_revision(current):
        raise PublishError("Correction not yet active")
    public_verified()
    print(json.dumps({"state": "ALREADY_LIVE_VERIFIED", "post_id": POST_ID,
                      "url": URL, "remote_writes": 0}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "deploy", "verify"):
            raise PublishError("Usage: snapshot|deploy|verify")
        {"snapshot": snapshot, "deploy": deploy,
         "verify": verify_only}[sys.argv[1]]()
    except (PublishError, OSError, ValueError, TypeError, KeyError) as exc:
        print("XFIT_PILATES_5929_ERROR: " + type(exc).__name__, file=sys.stderr)
        sys.exit(2)
