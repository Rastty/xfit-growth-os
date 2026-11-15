"""One-time evidence-led revision of malformed legacy creatine article 11945.

Pinned canonical URL, uploaded complete backup, no concurrency overwrite,
at most one content-only POST, authenticated readback and independent public
verification. No archive-wide change, redirects, plugins or new articles.
"""
import html
import json
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts.xfit_coupon_cleanup import get_post, sha
from scripts.xfit_editorial_gate import check_document, EditorialError

POST_ID = 11945
SLUG = "jak-kreatin-muze-pomoci-ziskat-svalovy-objem-v-fitness"
URL = "https://xfit.cz/" + SLUG + "/"
TARGET = Path("content/revisions/creatine-muscle-11945.html")
BACKUP = Path("reports/backups/xfit-creatine-11945-before-revision.json")
SIGNATURE = "Může kreatin pomoci nabrat svaly?"
REQUIRED_PHRASES = (
    SIGNATURE,
    "Potřebuji kreatin, nebo stačí změnit trénink?",
    "Forma, dávkování a čas užívání bez mýtů",
    "Zdroje, omezení a redakční metodika",
    "ods.od.nih.gov",
    "pubmed.ncbi.nlm.nih.gov",
)


def pinned(post):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("status") != "publish"
            or post.get("slug") != SLUG or post.get("link") != URL):
        raise PublishError("Canonical WordPress article identity changed")
    url = urlsplit(post["link"])
    if (url.scheme != "https" or url.hostname != "xfit.cz"
            or url.username or url.password or url.port
            or url.query or url.fragment):
        raise PublishError("Unexpected canonical WordPress URL")
    raw = (post.get("content") or {}).get("raw")
    if not isinstance(raw, str) or not 3000 <= len(raw.encode("utf-8")) <= 500000:
        raise PublishError("Unexpected raw article size")
    return raw


def old_body(post):
    raw = pinned(post)
    # This is a precise repair of the observed malformed legacy page only.
    # If another editor has already repaired it, do not overwrite them.
    if raw.lower().count("<!doctype html") < 3 or raw.lower().count("<html") < 3:
        raise PublishError("Malformed legacy HTML signature changed; manual review")
    if "5nm2022" in raw.casefold():
        raise PublishError("Expired coupon still present; finish its isolated recovery first")
    return raw


def new_body():
    body = TARGET.read_text(encoding="utf-8")
    if (SIGNATURE not in body or len(body.encode("utf-8")) < 4500
            or re.search(r"<\s*(?:script|iframe|form|html|head|body)\b|on\w+\s*=", body, re.I)
            or "5nm2022" in body.casefold()):
        raise PublishError("Revised article failed static content checks")
    try:
        result = check_document({"content": body}, commercial=False)
    except EditorialError as exc:
        raise PublishError("Editorial gate rejected article") from exc
    if result["h2_count"] < 5 or result["word_count"] < 500:
        raise PublishError("Revision missing significant reader value")
    return body


def snapshot():
    before = old_body(get_post(POST_ID))
    after = new_body()
    if BACKUP.exists():
        raise PublishError("Refusing to overwrite existing backup")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "post_id": POST_ID, "slug": SLUG, "url": URL,
        "original_raw": before, "original_sha256": sha(before),
        "target_sha256": sha(after), "remote_writes": 0
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "REVISION_BACKUP_READY", "post_id": POST_ID,
                      "original_sha256": sha(before), "remote_writes": 0}))


def clean_revision(body):
    if not isinstance(body, str) or len(body.encode("utf-8")) < 4500:
        return False
    normalized = html.unescape(body).casefold()
    return (all(phrase.casefold() in normalized for phrase in REQUIRED_PHRASES)
            and "<!doctype" not in normalized and "<html" not in normalized
            and "5nm2022" not in normalized)


def public_verified():
    request = urllib.request.Request(URL, headers={
        "User-Agent": "XfitGrowthOS/1.0", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise PublishError("Unexpected public HTTP response")
            page = response.read(2_000_000).decode("utf-8", errors="replace")
    except (OSError, ValueError) as exc:
        raise PublishError("Public URL not available") from exc
    article_text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    compact = " ".join(article_text.split()).casefold()
    if (SIGNATURE.casefold() not in compact
            or "forma, dávkování a čas užívání bez mýtů" not in compact):
        raise PublishError("Public HTML did not confirm revised article")
    # The *site* legitimately starts with <!DOCTYPE html>; check the public
    # WordPress article body, not the whole document, for nested legacy HTML.
    api = URL.replace("/" + SLUG + "/", "/wp-json/wp/v2/posts/" + str(POST_ID) +
                      "?_fields=id,slug,status,link,content")
    try:
        with urllib.request.urlopen(urllib.request.Request(
                api, headers={"User-Agent": "XfitGrowthOS/1.0",
                              "Cache-Control": "no-cache"}), timeout=30) as response:
            public = json.loads(response.read(2_000_000).decode("utf-8"))
    except (OSError, ValueError, KeyError) as exc:
        raise PublishError("Public WordPress REST readback unavailable") from exc
    if (public.get("id") != POST_ID or public.get("slug") != SLUG
            or public.get("status") != "publish" or public.get("link") != URL
            or not clean_revision((public.get("content") or {}).get("rendered"))):
        raise PublishError("Public WordPress article body is not the revision")
    return True


def deploy():
    if not BACKUP.exists():
        raise PublishError("Mandatory full-body backup missing")
    saved = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (not isinstance(saved, dict) or saved.get("schema") != 1
            or saved.get("post_id") != POST_ID or saved.get("slug") != SLUG
            or saved.get("url") != URL or saved.get("remote_writes") != 0):
        raise PublishError("Untrusted rollback manifest")
    before = old_body(get_post(POST_ID))
    after = new_body()
    if (sha(before) != saved.get("original_sha256")
            or before != saved.get("original_raw")
            or sha(after) != saved.get("target_sha256")):
        raise PublishError("Production source or revision changed after backup")

    write_error = False
    try:
        response = wp_request(normalized_base(), "posts/" + str(POST_ID),
                              payload={"content": after})
        if not isinstance(response, dict) or response.get("id") != POST_ID:
            write_error = True
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        write_error = True

    try:
        current_raw = pinned(get_post(POST_ID))
    except (PublishError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"state": "REVISION_UNKNOWN_NO_RETRY",
                          "post_id": POST_ID, "stage": "readback",
                          "write_error": write_error}))
        raise PublishError("Uncertain write state; no retry") from exc
    if sha(current_raw) == saved["original_sha256"]:
        raise PublishError("WordPress retained original malformed article")
    if not clean_revision(current_raw):
        raise PublishError("New article failed authenticated readback; manual review")
    public_verified()
    print(json.dumps({"state": "PUBLIC_VERIFIED", "post_id": POST_ID,
                      "url": URL, "articles_revised": 1, "post_attempts": 1,
                      "deletes": 0, "redirects": 0, "plugins": 0}))


def verify_only():
    """Reconcile a previously attempted release without another POST."""
    current = pinned(get_post(POST_ID))
    if not clean_revision(current):
        raise PublishError("Authenticated WordPress body is not the revision")
    public_verified()
    print(json.dumps({"state": "ALREADY_LIVE_VERIFIED",
                      "post_id": POST_ID, "url": URL, "remote_writes": 0,
                      "original_workflow": 43695394920}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "deploy", "verify"):
            raise PublishError("Usage: snapshot|deploy|verify")
        {"snapshot": snapshot, "deploy": deploy, "verify": verify_only}[sys.argv[1]]()
    except (PublishError, OSError, ValueError, TypeError, KeyError) as exc:
        print("XFIT_11945_REVISION_ERROR: " + type(exc).__name__, file=sys.stderr)
        sys.exit(2)
