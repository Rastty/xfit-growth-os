"""Guarded single-post rescue of damaged Japanese-exercise WP #9462.

Exact preflight -> immutable upload -> one content-only POST -> authenticated
and public canonical/ID/readback. Unknown status never triggers another POST.
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

from scripts.wp_publish import (PublishError, normalized_base, wp_request,
                                classify_wp_write_failure)
from scripts.xfit_editorial_gate import check_document
from scripts.xfit_public_coupon_watch import classify_html, exact_article_url

POST_ID = 9462
SLUG = "japonske-cviceni-na-hubnuti-objasnujeme-zakladni-principy"
URL = "https://xfit.cz/" + SLUG + "/"
TITLE = "– Japonské cvičení na hubnutí: Objasňujeme základní principy"
TITLE_RAW = "- Japonské cvičení na hubnutí: Objasňujeme základní principy"
REVIEWED_MODIFIED_GMT = "2023-10-22T02:51:47"
SOURCE = Path("content/revisions/japanese-exercise-9462.html")
BACKUP = Path("reports/backups/xfit-japanese-exercise-9462-original.json")
MARK = 'data-xfit-radio-taiso="v1"'
SIGNATURE = "Pod názvem „japonské cvičení na hubnutí“ se na internetu"
BAD_LINK = "https://www.example.com/relevant-post"
TARGETS = (
    "#desetiminutovy-plan",
    "https://xfit.cz/pilates-vs-kardio-co-je-lepsi-pro-hubnuti/",
    "https://xfit.cz/kolik-bilkovin-potrebujete-pro-budovani-svalu-pruvodce-spravnym-stravovanim/",
)
SOURCES = (
    "https://www.jp-life.japanpost.jp/radio/",
    "https://www.jp-life.japanpost.jp/radio/instruction/radio_first.html",
    "https://www.who.int/europe/news-room/fact-sheets/item/physical-activity",
    "https://www.cdc.gov/healthy-weight-growth/physical-activity/",
    "https://ods.od.nih.gov/factsheets/WeightLoss-HealthProfessional/",
)
OLD_SENTENCES = (
    "Harmonizace energie",
    "Japonské cvičení na hubnutí nehrozí zranění",
    "spalovat tuk, zlepšit funkci orgánů",
)
MAX_BYTES = 350_000


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def title_of(post):
    field = post.get("title") or {}
    if not isinstance(field, dict):
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", field.get("raw") or field.get("rendered") or "")).strip()


def title_matches(post, *, authenticated):
    """Pin the real WP raw ASCII hyphen AND its publicly rendered en dash."""
    field = post.get("title") or {}
    if not isinstance(field, dict):
        return False
    rendered = html.unescape(re.sub(r"<[^>]+>", "", field.get("rendered") or "")).strip()
    return rendered == TITLE and (not authenticated or field.get("raw") == TITLE_RAW)


def identity(post, *, authenticated=True):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("slug") != SLUG
            or post.get("status") != "publish"
            or not exact_article_url(post.get("link"), SLUG)
            or not title_matches(post, authenticated=authenticated)
            or not isinstance(post.get("modified_gmt"), str)
            or not post["modified_gmt"]):
        raise PublishError("Unexpected WordPress article identity or title")
    content = post.get("content") or {}
    body = content.get("raw" if authenticated else "rendered")
    if not isinstance(body, str) or len(body) < 1000 or len(body.encode()) > MAX_BYTES:
        raise PublishError("Missing or oversized article body")
    return body


def revision():
    source = SOURCE.read_text(encoding="utf-8")
    if (len(source) < 7000 or source.count(MARK) != 1
            or source.count("<nav ") != 1 or source.count("min-height:48px") != 3
            or any(source.count('href="' + target + '"') < 1 for target in TARGETS)
            or any(source.count('href="' + link + '"') < 1 for link in SOURCES)
            or any(s in source.lower() for s in ("5nm2022", "example.com", "ketomix",
                    "<!doctype", "<html", "<head", "<body", "<link", "<script",
                    "<iframe", "<form", "<style"))
            or re.search(r"\bon\w+\s*=", source, re.I)):
        raise PublishError("Reviewed body is malformed or unexpectedly changed")
    quality = check_document({"content": source})
    if quality["word_count"] < 800 or quality["h2_count"] < 7:
        raise PublishError("Insufficient editorial depth")
    return source


def old_source(value):
    plain = html.unescape(re.sub(r"<[^>]*>", " ", value))
    return (len(value) > 5000 and value.lower().count("<!doctype html>") == 4
            and value.count(BAD_LINK) == 2 and "https://xfit.cz/ketomix" in value
            and all(term.casefold() in plain.casefold() for term in OLD_SENTENCES)
            and "5nm2022" not in value.casefold() and MARK not in value)


def classify(post):
    raw = identity(post)
    candidate = revision()
    if raw == candidate:
        mode = "already_applied"
    elif post["modified_gmt"] == REVIEWED_MODIFIED_GMT and old_source(raw):
        mode = "update"
    else:
        print(json.dumps({"state": "REVIEWED_SOURCE_MISMATCH", "post_id": POST_ID,
                          "modified_gmt": post.get("modified_gmt"),
                          "old_markup": old_source(raw), "remote_writes": 0}))
        raise PublishError("Unreviewed or concurrently changed post")
    return {"mode": mode, "raw_sha": sha(raw), "revision_sha": sha(candidate),
            "modified_gmt": post["modified_gmt"]}


def remote():
    return wp_request(normalized_base(), "posts/" + str(POST_ID)
                      + "?context=edit&_fields=id,slug,status,title,link,modified_gmt,content")


def diagnose():
    """Read-only identity audit, with no article content or credentials in logs."""
    post = remote()
    field = post.get("title") or {}
    content = post.get("content") or {}
    raw = content.get("raw") or ""
    print(json.dumps({
        "state": "READ_ONLY_AUTH_IDENTITY", "post_id": POST_ID,
        "id_matches": type(post.get("id")) is int and post["id"] == POST_ID,
        "slug_matches": post.get("slug") == SLUG,
        "published": post.get("status") == "publish",
        "link_matches": exact_article_url(post.get("link"), SLUG),
        "title_matches": title_matches(post, authenticated=True),
        "title_raw": field.get("raw"), "title_rendered": field.get("rendered"),
        "expected_title": TITLE,
        "modified_gmt": post.get("modified_gmt"),
        "body_raw_bytes": len(raw.encode()) if isinstance(raw, str) else -1,
        "old_source_matches": isinstance(raw, str) and old_source(raw),
        "remote_writes": 0,
    }, ensure_ascii=False))


def public_rest():
    endpoint = "https://xfit.cz/wp-json/wp/v2/posts/9462?_fields=id,slug,status,title,link,modified_gmt,content"
    request = Request(endpoint, headers={"User-Agent": "XFITOnepost9462/1.0",
                                         "Cache-Control": "no-cache"})
    with urlopen(request, timeout=25) as response:
        parsed = urlsplit(response.geturl())
        if (response.status != 200 or parsed.scheme != "https" or parsed.hostname != "xfit.cz"
                or parsed.path != "/wp-json/wp/v2/posts/9462" or parsed.username
                or parsed.password or parsed.port or parsed.fragment):
            raise PublishError("Unexpected public REST endpoint")
        payload = response.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise PublishError("Oversized public REST response")
    return json.loads(payload)


def public_page():
    request = Request(URL, headers={"User-Agent": "XFITOnepost9462/1.0",
                                    "Cache-Control": "no-cache"})
    with urlopen(request, timeout=25) as response:
        if response.status != 200 or not exact_article_url(response.geturl(), SLUG):
            raise PublishError("Unexpected public permalink")
        payload = response.read(3_000_001)
    if len(payload) > 3_000_000:
        raise PublishError("Oversized public page")
    return payload.decode("utf-8", "strict")


def old_public_fingerprint():
    post = public_rest()
    rendered = identity(post, authenticated=False)
    page = public_page()
    if (post["modified_gmt"] != REVIEWED_MODIFIED_GMT
            or not old_source(rendered) or not old_source(page)
            or page.count('rel="canonical"') != 2 or "postid-9462" not in page):
        raise PublishError("Public legacy article changed since review")
    return {"rendered_sha": sha(rendered), "modified_gmt": post["modified_gmt"]}


def verify_public():
    for attempt in range(3):
        try:
            post = public_rest()
            rendered = identity(post, authenticated=False)
            page = public_page()
            state, mentions = classify_html(page, POST_ID, SLUG)
            if (SIGNATURE in rendered and SIGNATURE in page
                    and rendered.count(MARK) == 1 and page.count(MARK) == 1
                    and all(target in page and target in rendered for target in TARGETS + SOURCES)
                    and BAD_LINK not in page and BAD_LINK not in rendered
                    and state == "PUBLIC_NO_COUPON_OBSERVED" and mentions == 0
                    and page.count('rel="canonical"') == 1
                    and "<!DOCTYPE html><br" not in page
                    and "https://xfit.cz/ketomix" not in rendered):
                return True
        except (PublishError, OSError, UnicodeError, ValueError, TypeError):
            pass
        if attempt < 2:
            time.sleep(4)
    return False


def snapshot():
    if BACKUP.exists():
        raise PublishError("Immutable rollback artifact already exists")
    original = remote()
    state = classify(original)
    public_before = old_public_fingerprint() if state["mode"] == "update" else None
    if state["mode"] == "already_applied" and not verify_public():
        raise PublishError("Already-applied public article cannot be proved")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({"schema": 1, "post_id": POST_ID, "slug": SLUG,
                                  "original_authenticated_post": original,
                                  "mode": state["mode"], "raw_sha": state["raw_sha"],
                                  "revision_sha": state["revision_sha"],
                                  "modified_gmt": state["modified_gmt"],
                                  "public_before": public_before, "remote_writes": 0},
                                 ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "BACKUP_READY", "post_id": POST_ID,
                      "mode": state["mode"], "remote_writes": 0}))


def apply():
    if not BACKUP.exists():
        raise PublishError("Prewrite rollback archive missing")
    doc = json.loads(BACKUP.read_text(encoding="utf-8"))
    candidate = revision()
    if (doc.get("schema") != 1 or doc.get("post_id") != POST_ID
            or doc.get("slug") != SLUG or doc.get("remote_writes") != 0
            or doc.get("revision_sha") != sha(candidate)):
        raise PublishError("Rollback manifest mismatch")
    baseline = classify(doc.get("original_authenticated_post"))
    latest = classify(remote())
    if (baseline != latest or baseline["raw_sha"] != doc.get("raw_sha")
            or baseline["modified_gmt"] != doc.get("modified_gmt")
            or baseline["mode"] != doc.get("mode")):
        raise PublishError("Authenticated source changed since snapshot; no POST")
    if latest["mode"] == "already_applied":
        if not verify_public():
            raise PublishError("Public already-applied proof missing")
        print(json.dumps({"state": "ALREADY_APPLIED_NO_WRITE", "post_id": POST_ID,
                          "public_site_modified": False}))
        return
    if doc.get("public_before") != old_public_fingerprint():
        raise PublishError("Independent public source changed; no POST")

    uncertain = False
    post_error_category = "NONE"
    try:
        response = wp_request(normalized_base(), "posts/9462", payload={"content": candidate})
        uncertain = not isinstance(response, dict) or response.get("id") != POST_ID
        if uncertain:
            post_error_category = "INVALID_POST_RESPONSE"
    except (PublishError, OSError, TypeError, ValueError) as error:
        uncertain = True
        post_error_category = classify_wp_write_failure(error)
    try:
        saved = identity(remote())
        if saved != candidate:
            raise PublishError("Authenticated content readback mismatch")
    except (PublishError, OSError, TypeError, ValueError) as error:
        print(json.dumps({"state": "UNRESOLVED_NO_RETRY", "post_id": POST_ID,
                          "post_attempts": 1, "response_uncertain": uncertain,
                          "post_error_category": post_error_category}))
        raise PublishError("Ambiguous WordPress result; manual review required") from error
    if not verify_public():
        print(json.dumps({"state": "AUTH_VERIFIED_PUBLIC_UNVERIFIED", "post_id": POST_ID,
                          "post_attempts": 1, "response_uncertain": uncertain,
                          "post_error_category": post_error_category}))
        raise PublishError("Authenticated saved, public not independently proved")
    print(json.dumps({"state": "PUBLIC_VERIFIED", "post_id": POST_ID, "url": URL,
                      "post_attempts": 1, "posts_changed": 1, "public_site_modified": True,
                      "canonical_count": 1, "bogus_canonical_removed": True}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("diagnose", "snapshot", "apply"):
            raise PublishError("Usage: diagnose|snapshot|apply")
        {"diagnose": diagnose, "snapshot": snapshot, "apply": apply}[sys.argv[1]]()
    except (PublishError, OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        print(json.dumps({"state": "FAIL_CLOSED", "post_id": POST_ID,
                          "reason": str(error), "retry_post": False}))
        sys.exit(2)
