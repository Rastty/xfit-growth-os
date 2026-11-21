#!/usr/bin/env python3
"""Read-only reconciliation of XFIT two adviser category release after a failed job.

Never assume the failed GitHub Action means no WP write; a REST response can
time out after commit. This independent read compares exact published WP post
identity and current category membership with current public category cards.
Do not log editorial text, merchant URLs, affiliate IDs or credentials.
"""
import hashlib
import json
from pathlib import Path
import sys

from scripts.wp_publish import PublishError
from scripts.xfit_supplements_two_advisors_category import (
    PAGES, category_get, category_identity, source_get,
    page_identity, positions, category_public_get,
    homepage_get, card_rank, GUIDE_SLUG,
)
REPORT = Path("reports/xfit-two-advisors-postfail-getonly.json")


def state(*, get_category=category_get, get_post=source_get,
          get_archive=category_public_get, get_home=homepage_get):
    result = {
        "state": "WP_AND_ARCHIVE_READ_ONLY_RECONCILIATION",
        "wordpress_writes": 0, "post_attempts": 0,
        "affiliate_clicks_sent": 0, "analytics_events_sent": 0,
        "category_identity": "UNKNOWN", "post_statuses": [],
        "public_archive_state": "UNKNOWN", "public_home_state": "UNKNOWN",
    }
    try:
        category = category_identity(get_category())
        result["category_identity"] = "EXACT_CHILD_TERM_VERIFIED"
        result["category_id"] = category
    except (PublishError, OSError, ValueError, TypeError):
        category = None
        result["category_identity"] = "UNAVAILABLE_OR_CHANGED"
    statuses = []
    for approved in PAGES:
        post_id = approved[0]
        row = {
            "post_id": post_id, "identity": "UNKNOWN",
            "in_supplements_category": None,
            "category_count": None, "raw_sha256": None,
            "commercial_source_shape_verified": False,
        }
        try:
            post = get_post(post_id)
            # Exact published adviser identity, source and six source product
            # cards; handles independent editor updates without raw text logs.
            validated = page_identity(post, approved)
            row["identity"] = "PUBLISHED_REVIEWED_SOURCE"
            row["in_supplements_category"] = (
                category in validated["categories"] if category is not None
                else None
            )
            row["category_count"] = len(validated["categories"])
            row["raw_sha256"] = hashlib.sha256(
                validated["content"]["raw"].encode("utf-8")
            ).hexdigest()
            row["commercial_source_shape_verified"] = True
        except (PublishError, OSError, ValueError, TypeError):
            row["identity"] = "SOURCE_CHANGED_OR_UNAVAILABLE"
        statuses.append(row)
    result["post_statuses"] = statuses
    try:
        positions_now = positions(get_archive())
        result["public_archive_state"] = "PUBLIC_CATEGORY_HTML_VERIFIED"
        result["public_category_ranks"] = {
            "guide": positions_now.get(GUIDE_SLUG),
            "creatine_adviser": positions_now.get(PAGES[0][1]),
            "whey_adviser": positions_now.get(PAGES[1][1]),
        }
    except (PublishError, OSError, ValueError, TypeError):
        result["public_archive_state"] = "PUBLIC_CATEGORY_UNKNOWN"
    try:
        rank = card_rank(get_home())
        result["public_home_state"] = "PUBLIC_HOMEPAGE_PARSED"
        result["home_guide_rank"] = rank
    except (PublishError, OSError, ValueError, TypeError):
        result["public_home_state"] = "PUBLIC_HOMEPAGE_UNKNOWN"
    category_yes = all(r["in_supplements_category"] is True for r in statuses)
    positions_found = result.get("public_category_ranks") or {}
    visible = (positions_found.get("guide") == 1
               and all(type(positions_found.get(key)) is int
                       and positions_found[key] <= 3
                       for key in ("creatine_adviser", "whey_adviser"))
               and len({positions_found.get("creatine_adviser"),
                        positions_found.get("whey_adviser")}) == 2
               and type(result.get("home_guide_rank")) is int
               and result["home_guide_rank"] <= 3)
    if category_yes and visible:
        result["conclusion"] = "TWO_ADVISORS_CATEGORY_AND_PUBLIC_VISIBLE"
    elif category_yes:
        result["conclusion"] = "BOTH_CATEGORIES_SET_PUBLIC_VISIBILITY_UNPROVEN"
    elif any(r["in_supplements_category"] is True for r in statuses):
        result["conclusion"] = "PARTIAL_POST_MEMBERSHIP_VERIFIED"
    elif all(r["in_supplements_category"] is False for r in statuses):
        result["conclusion"] = "BOTH_POSTS_STILL_OUTSIDE_CATEGORY"
    else:
        result["conclusion"] = "POST_OUTCOME_UNCERTAIN"
    return result


def main():
    result = state()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    # GET-only diagnostics always report what they could prove. Do not make
    # non-visibility an excuse to retry an unknown prior POST.
    return 0


if __name__ == "__main__":
    sys.exit(main())
