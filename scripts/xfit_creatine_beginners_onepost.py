"""Source-pinned single-post creatine beginner correction.

GET-only diagnosis can run without a source pin; publication is disabled until
a separate reviewed commit sets exact WP id, source SHA and raw title. The old
article contains contradictory high-dose instructions and fixed post-training
claims. Never silently remove a different editor's more recent work.
"""
from html import unescape
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.wp_publish import (PublishError, normalized_base, wp_request,
    article_visible, editorial_links, normalize_visible, verify_public)

DOC = Path("content/revisions/creatine-beginners-20261121.json")
BACKUP = Path("reports/backups/xfit-creatine-beginners-onepost.json")
SLUG = "kreatin-pro-zacatecniky-v-fitness-kdy-zacit-a-jakymi-davkami-zacinat"
URL = "https://xfit.cz/" + SLUG + "/"
OLD_TITLE = "Kreatin pro začátečníky v fitness – kdy začít a jakými dávkami začínat"
NEW_TITLE = "Kreatin pro začátečníky: kdy začít, kolik a kdy užívat"
MARKER = 'data-xfit-revision="beginner-creatine-20261121"'
# HARD RELEASE DISABLED until exact authenticated source receipt reviewed.
PINNED_POST_ID = 0
PINNED_SOURCE_SHA256 = ""
PINNED_SOURCE_LENGTH = 0
EXPECTED_LINKS = [
    "https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/",
    "https://xfit.cz/kreatin-a-jeho-nevyhody-co-byste-meli-vedet-nez-ho-zacnete-uzivat-v-fitness/",
    "https://xfit.cz/xfit-os-kreatin-nebo-protein/",
    "https://xfit.cz/xfit-os-kreatin-poradce/",
    "https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/",
    "https://www.ausport.gov.au/ais/nutrition/supplements/group_a/performance-supplements2/creatine",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC7871530/",
]
LEGACY_SIGNALS = (
    "20-30g kreatinu",
    "po dobu delší než 8 týdnů",
    "ihned po tréninku",
)
UNSAFE = re.compile(r"<\s*(?:script|iframe|form|style)\b|on[a-z]+\s*=", re.I)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def approved_document():
    data = json.loads(DOC.read_text(encoding="utf-8"))
    if (data.get("schema") != 1 or
            data.get("mode") != "single_pinned_existing_wordpress_post_revision" or
            data.get("slug") != SLUG or data.get("canonical_url") != URL or
            data.get("title") != NEW_TITLE):
        raise PublishError("Unreviewed editorial document")
    raw = data.get("content")
    excerpt = data.get("excerpt")
    if (not isinstance(raw, str) or not (5500 < len(raw) < 16000) or
            not isinstance(excerpt, str) or not 80 <= len(excerpt) < 300 or
            raw.count(MARKER) != 1 or UNSAFE.search(raw) or
            "<h1" in raw.casefold() or raw.casefold().count("<h2") < 5 or
            editorial_links(raw) != EXPECTED_LINKS or
            not all(phrase in normalize_visible(raw) for phrase in (
                "není podmínkou", "3–5 g denně", "vysoký úvodní příjem není nutný",
                "vhodnost doplňku řešte", "bez nákupu"))):
        raise PublishError("Editorial body/link/safety invariant failed")
    return raw, excerpt


def source_get():
    query = urlencode({
        "slug": SLUG, "status": "publish", "context": "edit",
        "_fields": "id,slug,status,link,title,content,excerpt,modified_gmt",
        "per_page": 2,
    })
    return wp_request(normalized_base(), "posts?" + query)


def identity(rows):
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise PublishError("No unique existing WP post")
    p = rows[0]
    raw = (p.get("content") or {}).get("raw")
    title = (p.get("title") or {}).get("raw")
    excerpt = (p.get("excerpt") or {}).get("raw")
    if (type(p.get("id")) is not int or p["id"] <= 0 or
            p.get("slug") != SLUG or p.get("link") != URL or
            p.get("status") != "publish" or
            not isinstance(title, str) or not isinstance(raw, str) or
            not 1000 <= len(raw) <= 80000 or
            not isinstance(excerpt, str) or
            not isinstance(p.get("modified_gmt"), str) or not p["modified_gmt"]):
        raise PublishError("WP edit source missing or identity drift")
    return p, raw, title, excerpt


def diagnosis(*, rows=None):
    p, raw, title, excerpt = identity(source_get() if rows is None else rows)
    report = {
        "state": "READ_ONLY_CREATIVE_BEG_IN_SOURCE",
        "post_id": p["id"],
        "published_slug_canonical_verified": True,
        "title_exact_reviewed_old": unescape(title) == OLD_TITLE,
        "title_exact_reviewed_new": title == NEW_TITLE,
        "title_length": len(title),
        "raw_length": len(raw),
        "raw_sha256": sha(raw),
        "has_modified_gmt": bool(p["modified_gmt"]),
        "source_structure": {
            tag: len(re.findall(r"<\s*" + tag + r"\b", raw, re.I))
            for tag in ("html", "head", "title", "body", "h1", "h2", "iframe", "script")
        },
        "doctype_count": len(re.findall(r"<!\s*doctype\b", raw, re.I)),
        "reviewed_old_dosing_claims_present": [
            t.casefold() in unescape(raw).casefold() for t in LEGACY_SIGNALS
        ],
        "new_revision_marker": MARKER in raw,
        "source_has_excerpt": bool(excerpt),
        "wordpress_writes": 0,
        "release_approved": False,
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return report


def checked_existing(rows, approved, excerpt_new):
    p, raw, title, excerpt = identity(rows)
    if (PINNED_POST_ID <= 0 or not PINNED_SOURCE_SHA256 or
            PINNED_SOURCE_LENGTH <= 0 or p["id"] != PINNED_POST_ID):
        raise PublishError("Production post ID/source lease not yet pinned")
    if (title == NEW_TITLE and
            normalize_visible(excerpt) == normalize_visible(excerpt_new) and
            article_visible(raw)[0] == article_visible(approved)[0] and
            editorial_links(raw) == EXPECTED_LINKS):
        return p, "already_applied"
    if (unescape(title) != OLD_TITLE or
            len(raw) != PINNED_SOURCE_LENGTH or
            sha(raw) != PINNED_SOURCE_SHA256 or MARKER in raw):
        raise PublishError("Original post changed since preflight; no write")
    return p, "update"


def details(p):
    return {
        "id": p["id"], "slug": p["slug"], "status": p["status"], "url": p["link"],
        "raw": p["content"]["raw"], "title": p["title"]["raw"],
        "excerpt": p["excerpt"]["raw"], "modified_gmt": p["modified_gmt"],
    }


def snapshot():
    approved, excerpt_new = approved_document()
    p, mode = checked_existing(source_get(), approved, excerpt_new)
    if BACKUP.exists():
        raise PublishError("Refusing to overwrite original prewrite backup")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    before = details(p)
    BACKUP.write_text(json.dumps({
        "schema": 1, "before": before, "mode": mode,
        "before_sha256": sha(before["raw"]), "after_sha256": sha(approved),
        "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "BACKUP_READY_NO_WRITE", "post_id": p["id"],
                      "mode": mode, "remote_writes": 0}))


def apply():
    approved, excerpt_new = approved_document()
    if not BACKUP.is_file():
        raise PublishError("Missing full prewrite backup")
    saved = json.loads(BACKUP.read_text(encoding="utf-8"))
    original = saved.get("before") or {}
    if (saved.get("schema") != 1 or saved.get("remote_writes") != 0 or
            saved.get("mode") not in ("update", "already_applied") or
            original.get("id") != PINNED_POST_ID or original.get("slug") != SLUG or
            original.get("url") != URL or not isinstance(original.get("raw"), str) or
            sha(original["raw"]) != saved.get("before_sha256") or
            sha(approved) != saved.get("after_sha256")):
        raise PublishError("Backup contract/source lease invalid")
    p, mode = checked_existing(source_get(), approved, excerpt_new)
    if details(p) != original or mode != saved["mode"]:
        raise PublishError("Another editor changed the post after backup; no POST")
    if mode == "already_applied":
        verify_public(URL, NEW_TITLE, approved)
        print(json.dumps({"state": "ALREADY_LIVE_NO_WRITE", "wp_posts_changed": 0,
                          "post_attempts": 0, "post_id": p["id"]}))
        return
    try:
        wp_request(normalized_base(), "posts/" + str(PINNED_POST_ID), payload={
            "title": NEW_TITLE, "content": approved, "excerpt": excerpt_new,
        })
    except (OSError, ValueError, TypeError, PublishError):
        pass  # POST outcome might already have committed. NEVER repeat.
    try:
        after, after_mode = checked_existing(source_get(), approved, excerpt_new)
    except (OSError, ValueError, TypeError, PublishError) as exc:
        raise PublishError("POST uncertain; no automatic retry") from exc
    if after["id"] != PINNED_POST_ID or after_mode != "already_applied":
        raise PublishError("Write not proved by authenticated source; no retry")
    verify_public(URL, NEW_TITLE, approved)
    print(json.dumps({
        "state": "PUBLIC_VERIFIED", "post_id": PINNED_POST_ID,
        "posts_changed": 1, "post_attempts": 1,
        "new_posts": 0, "redirects": 0, "url": URL,
    }))


def main():
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("diagnose", "snapshot", "apply"):
            raise PublishError("Usage diagnose|snapshot|apply")
        if sys.argv[1] == "diagnose":
            diagnosis()
        elif sys.argv[1] == "snapshot":
            snapshot()
        else:
            apply()
    except (PublishError, OSError, ValueError, TypeError, KeyError):
        print("XFIT_BEGINNER_CREATINE_ERROR: PREWRITE_OR_VERIFY_GUARD", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
