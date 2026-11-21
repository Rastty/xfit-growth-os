#!/usr/bin/env python3
"""Place two EXISTING verified commercial advisers beside no-buy guide in XFIT supplement category.

Follow the proven single-post additive category release; reuse its exact
category identity, public H1 and headline parsing, without duplicating
full source-edit infrastructure. Exactly two allowed original WP posts;
no new posts, content edits, price/feed changes, affiliate-link rewrites,
status/slug changes or redirects. At most one POST per target, no retry.
"""
from html import unescape
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.parse

from scripts.wp_publish import PublishError, normalized_base, normalize_visible, wp_request
from scripts.xfit_supplements_category_hub_onepost import (
    CAT_NAME, CAT_URL, category_get, category_identity,
    category_public_get, CategoryH1, HeadlineCards, archive_rank,
)
from scripts.xfit_home_sticky_guide_onepost import (
    homepage_get, card_rank, POST_ID as GUIDE_ID, SLUG as GUIDE_SLUG,
)

PAGES = (
    (25455, "xfit-os-kreatin-poradce",
     "Jak vybrat kreatin: srovnání cen a balení monohydrátu"),
    (25456, "xfit-os-syrovatkovy-protein-porovnani",
     "Srovnání syrovátkových proteinů: cena, balení a typ"),
)
BACKUP = Path("reports/backups/xfit-supplements-two-advisors-20261121.json")


def sha(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def source_get(post_id):
    if post_id not in {row[0] for row in PAGES}:
        raise PublishError("Unapproved WordPress post ID")
    return wp_request(
        normalized_base(),
        "posts/" + str(post_id) +
        "?context=edit&_fields=id,slug,status,sticky,link,title,content,excerpt,categories,modified_gmt",
    )


def page_identity(post, approved):
    post_id, slug, title_expected = approved
    if not isinstance(post, dict):
        raise PublishError("Missing approved advisor post source")
    raw = (post.get("content") or {}).get("raw")
    title = (post.get("title") or {}).get("raw")
    excerpt = (post.get("excerpt") or {}).get("raw")
    categories = post.get("categories")
    link_expected = "https://xfit.cz/" + slug + "/"
    if (type(post.get("id")) is not int or post["id"] != post_id
            or post.get("slug") != slug or post.get("status") != "publish"
            or post.get("link") != link_expected
            or type(post.get("sticky")) is not bool
            or not isinstance(title, str)
            or normalize_visible(title) != normalize_visible(title_expected)
            or not isinstance(raw, str) or not 4000 <= len(raw) <= 150000
            or raw.count('class="xfit-product-card"') != 6
            or "data-xfit-product-id" not in raw
            or "namaximum" not in raw.casefold()
            or "nekup" not in normalize_visible(raw)
            or not isinstance(excerpt, str)
            or not isinstance(post.get("modified_gmt"), str) or not post["modified_gmt"]
            or not isinstance(categories, list) or len(categories) >= 30
            or any(type(v) is not int or v <= 0 for v in categories)
            or len(categories) != len(set(categories))):
        raise PublishError("Advisor identity, expected six offers or source context drift")
    return post


def read_all():
    category_id = category_identity(category_get())
    posts = [page_identity(source_get(row[0]), row) for row in PAGES]
    return category_id, posts


def archive_order(html):
    if not isinstance(html, str) or not 400 <= len(html) <= 2_000_000:
        raise PublishError("Missing supplement category document")
    h1 = CategoryH1()
    h1.feed(html)
    if h1.h1 != [CAT_NAME]:
        raise PublishError("Wrong public category identity")
    cards = HeadlineCards()
    cards.feed(html)
    unique = list(dict.fromkeys(cards.hrefs))
    if len(unique) < 8 or len(unique) > 250:
        raise PublishError("Supplement category card count unknown")
    return unique


def positions(html):
    urls = archive_order(html)
    result = {}
    for name, slug in [(GUIDE_SLUG, GUIDE_SLUG)] + [
        (row[1], row[1]) for row in PAGES
    ]:
        path = "/" + slug + "/"
        result[name] = urls.index(path) + 1 if path in urls else None
    return result


def fingerprint(post):
    return {
        "original_post": post,
        "raw_sha256": sha(post["content"]["raw"]),
        "old_categories": post["categories"],
    }


def snapshot():
    category_id, posts = read_all()
    order = positions(category_public_get())
    home = card_rank(homepage_get())
    if order[GUIDE_SLUG] != 1 or home is None or home > 3:
        raise PublishError("Previously deployed first-position decision guide drifted")
    for row, post in zip(PAGES, posts):
        if category_id in post["categories"]:
            if order[row[1]] is None or order[row[1]] > 3:
                raise PublishError("Advisor in category but not publicly visible")
        elif order[row[1]] is not None and order[row[1]] <= 12:
            raise PublishError("Archive already lists advisor without term identity")
    if BACKUP.exists():
        raise PublishError("Cannot overwrite original two-advisor backup")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": 1, "category_id": category_id,
        "before": [fingerprint(p) for p in posts],
        "archive_before": order,
        "homepage_guide_rank": home,
        "wordpress_writes": 0,
    }
    BACKUP.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "state": "TWO_ADVISORS_ROLLBACK_READY_NO_WRITE",
        "category_id": category_id,
        "posts_backed_up": [row[0] for row in PAGES],
        "archive_guide_rank": order[GUIDE_SLUG],
        "wordpress_writes": 0,
    }))


def no_category_or_timestamp(post):
    payload = dict(post)
    payload.pop("categories", None)
    payload.pop("modified_gmt", None)
    return payload


def apply():
    if not BACKUP.is_file():
        raise PublishError("Mandatory original post backups missing")
    saved = json.loads(BACKUP.read_text(encoding="utf-8"))
    snapshots = saved.get("before")
    if (saved.get("schema") != 1 or
            saved.get("wordpress_writes") != 0 or
            type(saved.get("category_id")) is not int or
            not isinstance(snapshots, list) or len(snapshots) != 2):
        raise PublishError("Untrusted backup manifest")
    prior = []
    for entry, approved in zip(snapshots, PAGES):
        original = entry.get("original_post") if isinstance(entry, dict) else None
        if (not isinstance(original, dict) or
                original.get("id") != approved[0] or
                not isinstance((original.get("content") or {}).get("raw"), str) or
                sha(original["content"]["raw"]) != entry.get("raw_sha256") or
                original.get("categories") != entry.get("old_categories")):
            raise PublishError("Invalid rollback/source contract")
        prior.append(original)
    cat_id, now = read_all()
    if cat_id != saved["category_id"] or now != prior:
        raise PublishError("Concurrent editor/term source change before POST")
    if (positions(category_public_get()) != saved["archive_before"]
            or card_rank(homepage_get()) != saved["homepage_guide_rank"]):
        raise PublishError("Public category/homepage changed since backup")
    attempts = 0
    for approved, original in zip(PAGES, prior):
        post_id = approved[0]
        previous = original["categories"]
        if cat_id in previous:
            continue
        # Recheck this post before each POST, because parallel publisher runs
        # may have refreshed pricing/body after the batch baseline.
        if source_get(post_id) != original:
            raise PublishError("Advisor source drift during batch; no next POST")
        expected = sorted(previous + [cat_id])
        print(json.dumps({"state": "ONE_CATEGORY_POST_ATTEMPT_START",
                          "post_id": post_id, "attempt_number": attempts + 1}))
        attempts += 1
        try:
            wp_request(normalized_base(), "posts/" + str(post_id),
                       payload={"categories": expected})
        except (PublishError, OSError, ValueError, TypeError):
            pass  # A failed response may conceal a successful WP write.
        try:
            after = page_identity(source_get(post_id), approved)
        except (PublishError, OSError, ValueError, TypeError) as exc:
            raise PublishError("POST result uncertain; no retry and no next post") from exc
        if (no_category_or_timestamp(after) != no_category_or_timestamp(original)
                or sorted(after["categories"]) != expected):
            raise PublishError("Post or category verification failed; no retry")
    # Final GET proves all original categories and all editorial fields intact.
    _, final = read_all()
    for item, original in zip(final, prior):
        if (no_category_or_timestamp(item) != no_category_or_timestamp(original)
                or sorted(item["categories"])
                   != sorted(set(original["categories"]) | {cat_id})):
            raise PublishError("After batch, an advisor changed unexpectedly")
    result = None
    for trial in range(5):
        result = positions(category_public_get())
        pair = [result[row[1]] for row in PAGES]
        if (result[GUIDE_SLUG] == 1 and
                all(value is not None and value <= 3 for value in pair) and
                len(set(pair)) == 2):
            break
        if trial < 4:
            time.sleep(3)
    home = card_rank(homepage_get())
    success = bool(result[GUIDE_SLUG] == 1 and
                   all(result[row[1]] is not None and result[row[1]] <= 3
                       for row in PAGES) and
                   len({result[row[1]] for row in PAGES}) == 2 and
                   home is not None and home <= 3)
    print(json.dumps({
        "state": ("PUBLIC_TWO_ADVISORS_IN_SUPPLEMENT_TOP3" if success
                  else "WP_TWO_CATEGORY_MEMBERSHIPS_PUBLIC_TOP3_NOT_PROVEN"),
        "category_id": cat_id,
        "existing_guide_rank": result[GUIDE_SLUG],
        "creatine_advisor_rank": result[PAGES[0][1]],
        "whey_advisor_rank": result[PAGES[1][1]],
        "homepage_guide_rank": home,
        "wordpress_post_attempts": attempts,
        "original_categories_preserved": True,
        "article_contents_and_commercial_links_unchanged": True,
        "posts_created": 0, "posts_deleted": 0, "redirects": 0,
    }))
    if not success:
        raise PublishError("REST categories accepted, public listing not fully verified")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Usage snapshot|apply")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        print("XFIT_TWO_ADVISORS_CATEGORY_ERROR: SOURCE_OR_PUBLIC_GUARD", file=sys.stderr)
        sys.exit(2)
