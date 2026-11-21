#!/usr/bin/env python3
"""Add exactly one existing no-buy XFIT decision guide to correct supplement category.

The live 193-page /category/vyziva/doplnky-stravy/ archive still opens with
2023 articles while the current, source-verified guide is assigned elsewhere.
This is a taxonomy-only edit to WP #25458: no new post, no content/title/slug/
canonical edits, no removal of existing categories or sticky homepage feature.
Prewrite full edit-context backup and source/card-order leases; one POST max.
"""
from html import unescape
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import sys
import urllib.parse
import urllib.request
import time

from scripts.wp_publish import (
    PublishError, normalized_base, wp_request, normalize_visible,
)
from scripts.xfit_home_sticky_guide_onepost import (
    POST_ID, SLUG, URL, TITLE, homepage_get, card_rank, HeadlineCards,
)

CAT_SLUG = "doplnky-stravy"
CAT_NAME = "Doplňky stravy"
CAT_URL = "https://xfit.cz/category/vyziva/doplnky-stravy/"
BACKUP = Path("reports/backups/xfit-supplements-category-guide-20261121.json")
MAX_BYTES = 2_000_000


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class CategoryH1(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.h1 = []
        self._current = None

    def handle_starttag(self, tag, attrs):
        if tag == "h1":
            self._current = []

    def handle_data(self, value):
        if self._current is not None:
            self._current.append(value)

    def handle_endtag(self, tag):
        if tag == "h1" and self._current is not None:
            self.h1.append(" ".join("".join(self._current).split()))
            self._current = None


def archive_rank(html):
    if not isinstance(html, str) or not 400 <= len(html) <= MAX_BYTES:
        raise PublishError("Missing public category archive HTML")
    title = CategoryH1()
    title.feed(html)
    if title.h1 != [CAT_NAME]:
        raise PublishError("Unexpected supplement category archive H1")
    headings = HeadlineCards()
    headings.feed(html)
    distinct = list(dict.fromkeys(headings.hrefs))
    if len(distinct) < 8 or len(distinct) > 250:
        raise PublishError("Unknown supplement archive title-card structure")
    path = "/" + SLUG + "/"
    return distinct.index(path) + 1 if path in distinct else None


def category_public_get():
    request = urllib.request.Request(CAT_URL, headers={
        "User-Agent": "XFITSupplementsCategoryReadback/1.0",
        "Cache-Control": "no-cache", "Pragma": "no-cache",
    }, method="GET")
    with urllib.request.urlopen(request, timeout=25) as response:
        target = urllib.parse.urlsplit(response.geturl())
        wanted = urllib.parse.urlsplit(CAT_URL)
        if (response.status != 200 or target.scheme != "https"
                or target.hostname not in ("xfit.cz", "www.xfit.cz")
                or target.username or target.password or target.port
                or target.path != wanted.path or target.query or target.fragment):
            raise PublishError("Category archive URL mismatch or redirect")
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise PublishError("Category archive too large")
        return body.decode("utf-8", errors="replace")


def category_get():
    query = urllib.parse.urlencode({
        "context": "edit", "slug": CAT_SLUG, "per_page": 3,
        "_fields": "id,slug,name,link,parent,count",
    })
    return wp_request(normalized_base(), "categories?" + query)


def category_identity(rows):
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise PublishError("No unique WordPress supplement category")
    item = rows[0]
    if (type(item.get("id")) is not int or item["id"] <= 0
            or item.get("slug") != CAT_SLUG
            or unescape(item.get("name", "")) != CAT_NAME
            or item.get("link") != CAT_URL
            or type(item.get("parent")) is not int or item["parent"] <= 0):
        raise PublishError("Supplement term does not match exact child category")
    return item["id"]


def guide_get():
    return wp_request(
        normalized_base(),
        "posts/" + str(POST_ID) +
        "?context=edit&_fields=id,slug,status,sticky,link,title,content,excerpt,categories,modified_gmt",
    )


def guide_identity(item):
    if not isinstance(item, dict):
        raise PublishError("No pinned guide edit-context source")
    raw = (item.get("content") or {}).get("raw")
    title = (item.get("title") or {}).get("raw")
    excerpt = (item.get("excerpt") or {}).get("raw")
    cats = item.get("categories")
    if (type(item.get("id")) is not int or item["id"] != POST_ID
            or item.get("slug") != SLUG or item.get("status") != "publish"
            or item.get("link") != URL or item.get("sticky") is not True
            or not isinstance(title, str)
            or normalize_visible(title) != normalize_visible(TITLE)
            or not isinstance(raw, str) or not 2000 <= len(raw) <= 120000
            or "nekup" not in normalize_visible(raw)
            or "xfit-os-kreatin-nebo-protein" not in raw
            or not isinstance(excerpt, str)
            or not isinstance(item.get("modified_gmt"), str)
            or not item["modified_gmt"]
            or not isinstance(cats, list) or len(cats) >= 30
            or any(type(x) is not int or x <= 0 for x in cats)
            or len(set(cats)) != len(cats)):
        raise PublishError("Unexpected guide identity, content, sticky or categories")
    return item


def checked_source(*, guide_reader=guide_get, category_reader=category_get):
    category = category_identity(category_reader())
    guide = guide_identity(guide_reader())
    return category, guide


def snapshot():
    cat_id, original = checked_source()
    already = cat_id in original["categories"]
    prior = archive_rank(category_public_get())
    home_before = card_rank(homepage_get())
    if home_before is None or home_before > 3:
        raise PublishError("Previously verified first-homepage guide visibility has drifted")
    if prior is not None and prior <= 3 and not already:
        raise PublishError("Public category shows guide while term missing: ambiguous archive")
    if BACKUP.exists():
        raise PublishError("Cannot overwrite original category/source backup")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "post_id": POST_ID, "category_id": cat_id,
        "old_post": original,
        "old_content_sha256": sha(original["content"]["raw"]),
        "old_categories": original["categories"],
        "old_archive_card_rank": prior,
        "old_home_card_rank": home_before,
        "mode": "already_in_category" if already else "add_term",
        "wordpress_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "state": "BACKUP_READY_NO_WRITE", "post_id": POST_ID,
        "supplements_category_id": cat_id,
        "guide_initial_category_rank": prior,
        "guide_initial_home_rank": home_before,
        "mode": "already_in_category" if already else "add_term",
        "wordpress_writes": 0,
    }))


def _same_post_other_than_category_and_timestamp(before, after):
    a = dict(before)
    b = dict(after)
    for k in ("categories", "modified_gmt"):
        a.pop(k, None)
        b.pop(k, None)
    return a == b


def apply():
    if not BACKUP.exists():
        raise PublishError("Full source and category prewrite backup missing")
    saved = json.loads(BACKUP.read_text(encoding="utf-8"))
    before = saved.get("old_post")
    if (saved.get("schema") != 1 or saved.get("post_id") != POST_ID
            or type(saved.get("category_id")) is not int
            or not isinstance(before, dict)
            or saved.get("wordpress_writes") != 0
            or saved.get("mode") not in ("already_in_category", "add_term")
            or not isinstance((before.get("content") or {}).get("raw"), str)
            or sha(before["content"]["raw"]) != saved.get("old_content_sha256")):
        raise PublishError("Incomplete or changed rollback contract")
    cat, current = checked_source()
    if cat != saved["category_id"] or current != before:
        raise PublishError("Guide/category source drift since backup; no POST")
    if (archive_rank(category_public_get()) != saved.get("old_archive_card_rank")
            or card_rank(homepage_get()) != saved.get("old_home_card_rank")):
        raise PublishError("Public archive or homepage drift since snapshot")
    if saved["mode"] == "already_in_category":
        rank = archive_rank(category_public_get())
        if rank is None or rank > 3:
            raise PublishError("Category already assigned but guide not prominent")
        print(json.dumps({"state": "ALREADY_IN_CATEGORY_NO_WRITE", "post_id": POST_ID,
                          "archive_card_rank": rank, "wordpress_writes": 0}))
        return
    original_ids = before["categories"]
    target = sorted(original_ids + [cat])
    # No automatic retry, even after a timeout. Only exact authenticated
    # source GET may prove the *one* attempted POST took effect.
    try:
        wp_request(normalized_base(), "posts/" + str(POST_ID),
                   payload={"categories": target})
    except (PublishError, OSError, ValueError, TypeError):
        pass
    try:
        after = guide_identity(guide_get())
    except (PublishError, OSError, ValueError, TypeError) as exc:
        raise PublishError("Category POST status unknown; NEVER retry") from exc
    if (not _same_post_other_than_category_and_timestamp(before, after)
            or sorted(after["categories"]) != target
            or cat not in after["categories"]):
        raise PublishError("Category update or preservation of original guide not proven")
    # Category template may not expose new member immediately in its cache.
    # Re-read without retrying POST; do not label WP assignment as UX deployment.
    latest_rank = None
    for attempt in range(3):
        latest_rank = archive_rank(category_public_get())
        if latest_rank is not None and latest_rank <= 3:
            break
        if attempt < 2:
            time.sleep(2)
    homepage_rank = card_rank(homepage_get())
    success = latest_rank is not None and latest_rank <= 3 and homepage_rank <= 3
    print(json.dumps({
        "state": ("PUBLIC_SUPPLEMENTS_CATEGORY_PROMOTED" if success
                  else "WP_CATEGORY_SET_PUBLIC_PROMOTION_UNPROVEN"),
        "post_id": POST_ID,
        "category_id": cat,
        "before_archive_rank": saved.get("old_archive_card_rank"),
        "after_archive_rank": latest_rank,
        "before_home_rank": saved.get("old_home_card_rank"),
        "after_home_rank": homepage_rank,
        "other_categories_preserved": len(original_ids),
        "content_title_slug_canonical_sticky_unchanged": True,
        "wordpress_post_attempts": 1,
        "posts_created": 0, "posts_deleted": 0, "redirects": 0,
    }))
    if not success:
        raise PublishError("WordPress category assigned but public page not proven upgraded")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Usage snapshot|apply")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, OSError, ValueError, TypeError, KeyError):
        print("XFIT_SUPPLEMENT_CATEGORY_ERROR: SOURCE_OR_PUBLIC_GUARD", file=sys.stderr)
        sys.exit(2)
