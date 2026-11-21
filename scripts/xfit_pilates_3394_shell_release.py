"""Source-pinned onepost rescue for GSC-visible Pilates article WP #3394.

2026-11-21 independent, authenticated and public GETs established exactly
one embedded <!DOCTYPE>/<html>/<head>/<title>/<body> shell inside the legacy
post body and two public document <title> tags. This removes ONLY the embedded
document shell, keeps its substantive <body> markup byte-for-byte, and inserts
one useful contextual navigation paragraph pointing to the already verified
Pilates style comparison. It does not change original title, slug, excerpt,
media, author, or affiliate links. No blind retry after an ambiguous POST.
"""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts.xfit_editorial_gate import Inspector
from scripts.xfit_pilates_gsc_preflight import (
    canonical_path, read_public, parse_public,
)
from scripts.xfit_pilates_sibling_source import Structure
from scripts.xfit_pilates_gsc_title_release import SLUG as MAIN_SLUG

POST_ID = 3394
SLUG = ("pilates-vs-klasicke-cviceni-jake-jsou-hlavni-rozdily-a-"
        "ktere-cviceni-je-pro-vas-lepsi")
URL = "https://xfit.cz/" + SLUG + "/"
TARGET = "https://xfit.cz/" + MAIN_SLUG + "/"
EXPECTED_SHA = "1602c1ada91fc13b27f1742eec59da787cbb4b4bb6b78dedff5b2cd0b7b19bef"
EXPECTED_MODIFIED = "2023-04-19T05:27:37"
MARKER = 'data-xfit-pilates-topic-handoff="v1-3394"'
BACKUP = Path("reports/backups/xfit-pilates-3394-shell-original.json")
MAX_BYTES = 250_000

HANDOFF = (
    '<p ' + MARKER + '><strong>Vybrat vhodný styl pilates:</strong> '
    'Když začínáte, rozhoduje hlavně přiměřená obtížnost a dobré vedení '
    'techniky. Pod názvem power pilates bývají často dynamičtější lekce, '
    'ale samotný název nezaručuje určitou náročnost. '
    '<a href="' + TARGET + '" style="display:inline-block;'
    'min-height:44px;box-sizing:border-box;padding:10px 0;">'
    'Klasické a power pilates – porovnání tempa a vhodnosti pro začátečníky'
    '</a>. Před rezervací si ověřte úroveň kurzu a možnost lehčích variant.</p>'
)
SHELL = re.compile(
    r"\A\s*<!DOCTYPE\s+html[^>]*>\s*<html\b[^>]*>\s*"
    r"<head\b[^>]*>.*?</head\s*>\s*"
    r"<body\b[^>]*>(?P<body>.*?)</body\s*>\s*</html\s*>\s*\Z",
    re.I | re.S,
)


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source():
    return wp_request(
        normalized_base(), "posts/" + str(POST_ID) +
        "?context=edit&_fields=id,slug,status,link,title,excerpt,"
        "featured_media,author,categories,tags,modified_gmt,content"
    )


def identify(post, *, expected_original=True):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("slug") != SLUG
            or post.get("status") != "publish"
            or not canonical_path(post.get("link"), SLUG)):
        raise PublishError("Unexpected legacy Pilates article identity")
    raw = (post.get("content") or {}).get("raw")
    if (not isinstance(raw, str) or not 1500 <= len(raw) <= MAX_BYTES
            or len(raw.encode("utf-8")) > MAX_BYTES):
        raise PublishError("Invalid legacy content size")
    modified = post.get("modified_gmt")
    if expected_original and (
            sha(raw) != EXPECTED_SHA or modified != EXPECTED_MODIFIED):
        raise PublishError("Source SHA/date drifted; no WordPress POST")
    return raw


def metadata(post):
    return {
        "slug": post.get("slug"), "status": post.get("status"),
        "link": post.get("link"),
        "title": (post.get("title") or {}).get("raw"),
        "excerpt": (post.get("excerpt") or {}).get("raw"),
        "featured_media": post.get("featured_media"),
        "author": post.get("author"),
        "categories": post.get("categories"),
        "tags": post.get("tags"),
    }


def transform(original):
    # Recheck the literal original shape, not only a loosely matching regex.
    counts = {
        "doctype": len(re.findall(r"<!\s*doctype\b", original, re.I)),
        "html": len(re.findall(r"<\s*html\b", original, re.I)),
        "head": len(re.findall(r"<\s*head\b", original, re.I)),
        "body": len(re.findall(r"<\s*body\b", original, re.I)),
        "title": len(re.findall(r"<\s*title\b", original, re.I)),
        "title_end": len(re.findall(r"</\s*title\s*>", original, re.I)),
        "h2": len(re.findall(r"<\s*h2\b", original, re.I)),
        "p": len(re.findall(r"<\s*p(?:\s|>)", original, re.I)),
    }
    if counts != {
        "doctype": 1, "html": 1, "head": 1, "body": 1,
        "title": 1, "title_end": 1, "h2": 6, "p": 15,
    } or re.search(r"<\s*(?:script|style|iframe|form)\b|"
                   r"<\s*link\b[^>]*\bcanonical\b|\bon\w+\s*=",
                   original, re.I):
        raise PublishError("Legacy shell structure differs from reviewed source")
    match = SHELL.fullmatch(original)
    if match is None:
        raise PublishError("Cannot remove only the outer document shell")
    body = match.group("body")
    if (len(body) < 3500 or TARGET in body or MARKER in body
            or re.search(r"<\s*(?:/?(?:html|head|body)|title|meta)\b|<!doctype",
                         body, re.I)
            or len(re.findall(r"<\s*h2\b", body, re.I)) != 6
            or len(re.findall(r"<\s*p(?:\s|>)", body, re.I)) != 15):
        raise PublishError("Extracted editorial body fails exact source safety")
    intro = re.search(r"</p\s*>", body, re.I)
    if intro is None:
        raise PublishError("No reviewed introduction paragraph")
    revised = body[:intro.end()] + "\n" + HANDOFF + body[intro.end():]
    if (revised.count(MARKER) != 1 or revised.count(TARGET) != 1
            or re.search(r"<!doctype|<\s*(?:html|head|body|title|meta)\b",
                         revised, re.I)):
        raise PublishError("Unexpected revised article markup")
    old, new = Inspector(), Inspector()
    old.feed(body)
    new.feed(revised)
    if (old.headers != new.headers or old.images != new.images
            or [link for link in new.links if link[0] != TARGET] != old.links
            or sum(link[0] == TARGET for link in new.links) != 1):
        raise PublishError("Non-target editorial headings, media or links drifted")
    return revised


def snapshot():
    post = source()
    raw = identify(post)
    after = transform(raw)
    if BACKUP.exists():
        raise PublishError("Existing rollback artifact path; no overwrite")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "post_id": POST_ID,
        "original": post, "source_sha": sha(raw),
        "replacement_sha": sha(after), "modified_gmt": EXPECTED_MODIFIED,
        "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "state": "PILATES_3394_PREWRITE_BACKUP_READY",
        "post_id": POST_ID, "old_sha": sha(raw),
        "replacement_sha": sha(after), "post_attempts": 0,
    }))


def verify_public():
    body, robots = read_public(SLUG)
    public = parse_public(SLUG, body, robot_header=robots)
    structure = Structure()
    structure.feed(body)
    return (
        public["canonical"] == "SELF_CANONICAL"
        and public["robots"] == "NO_NOINDEX_OBSERVED"
        and len(public["h1"]) == 1
        and structure.head_title_count == 1
        and structure.body_title_count == 0
        and public["links_to_primary"]
        and MARKER in body
    )


def apply():
    if not BACKUP.exists():
        raise PublishError("Missing immutable prewrite rollback")
    backup = json.loads(BACKUP.read_text(encoding="utf-8"))
    old = backup.get("original")
    before = identify(old)
    candidate = transform(before)
    if (backup.get("schema") != 1 or backup.get("post_id") != POST_ID
            or backup.get("source_sha") != EXPECTED_SHA
            or backup.get("replacement_sha") != sha(candidate)
            or backup.get("modified_gmt") != EXPECTED_MODIFIED
            or backup.get("remote_writes") != 0):
        raise PublishError("Prewrite artifact differs from reviewed source")
    current = source()
    current_raw = identify(current)
    if current_raw != before or metadata(current) != metadata(old):
        raise PublishError("Article metadata or source changed since snapshot")
    # One and only one content-only POST, no blind transport retry.
    uncertain = False
    try:
        response = wp_request(normalized_base(), "posts/" + str(POST_ID),
                              payload={"content": candidate})
        if (not isinstance(response, dict) or response.get("id") != POST_ID
                or response.get("status") != "publish"):
            uncertain = True
    except (PublishError, OSError, ValueError, TypeError):
        uncertain = True
    try:
        observed = source()
        actual = identify(observed, expected_original=False)
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        print(json.dumps({
            "state": "UNRESOLVED_NO_RETRY", "post_id": POST_ID,
            "post_attempts": 1, "response_uncertain": uncertain,
        }))
        raise PublishError("Post attempt was ambiguous; never repeat") from None
    if actual != candidate or metadata(observed) != metadata(old):
        print(json.dumps({
            "state": "POST_NOT_VERIFIED_NO_RETRY", "post_id": POST_ID,
            "post_attempts": 1, "source_unchanged": actual == before,
        }))
        raise PublishError("Authenticated updated content not verified")
    if not verify_public():
        print(json.dumps({
            "state": "WP_UPDATED_PUBLIC_UNVERIFIED", "post_id": POST_ID,
            "post_attempts": 1, "source_committed": True,
        }))
        raise PublishError("Public SEO and inlink state not verified")
    print(json.dumps({
        "state": "PUBLIC_VERIFIED", "post_id": POST_ID,
        "post_attempts": 1, "posts_changed": 1,
        "public_site_modified": True, "seo_title_tags": 1,
        "body_links_added": 1, "new_posts": 0, "deletes": 0,
        "permalink_preserved": True,
    }))


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
        raise PublishError("Usage snapshot|apply")
    (snapshot if sys.argv[1] == "snapshot" else apply)()


if __name__ == "__main__":
    try:
        main()
    except (PublishError, OSError, ValueError, KeyError, TypeError, AttributeError):
        print("XFIT_PILATES_3394_ONEPOST_STOPPED", file=sys.stderr)
        raise SystemExit(2) from None
