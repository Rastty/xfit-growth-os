"""Read-only evidence gate for the PAUSED supplements-category advisers placement.

The former two-post category writer failed before confirmed writes, so this
does not retry it. Verify exact current WordPress identities and archive
positions, and report bounded source fingerprints; no editor payloads, no
affiliate identifiers, no raw content, no interaction with the merchant.
"""
import hashlib
import json
import sys

from scripts.wp_publish import PublishError
from scripts.xfit_supplements_two_advisors_category import (
    PAGES, read_all, positions, category_public_get,
)
from scripts.xfit_supplements_category_hub_onepost import (
    guide_get, guide_identity,
)
from scripts.xfit_home_sticky_guide_onepost import (
    homepage_get, card_rank,
)


def assess(*, source_reader=read_all, archive_reader=category_public_get,
           guide_reader=guide_get, home_reader=homepage_get):
    category_id, posts = source_reader()
    if type(category_id) is not int or category_id <= 0 or len(posts) != 2:
        raise PublishError("Exact supplement source scope unavailable")
    guide = guide_identity(guide_reader())
    if category_id not in guide["categories"]:
        raise PublishError("Previously verified first-position guide missing term")
    category_positions = positions(archive_reader())
    homepage_rank = card_rank(home_reader())
    if category_positions[guide["slug"]] != 1 or homepage_rank != 1:
        raise PublishError("Guide prominence drift: no category release eligible")
    rows=[]
    for approved, item in zip(PAGES, posts):
        if item["id"] != approved[0] or item["slug"] != approved[1]:
            raise PublishError("Adviser category evidence wrong identity")
        content=item["content"]["raw"]
        cats=item["categories"]
        rows.append({
            "post_id":item["id"], "slug":item["slug"],
            "source_sha256":hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "modified_gmt":item["modified_gmt"],
            "categories":cats,
            "already_in_supplement_category":category_id in cats,
            "is_homepage_sticky":item["sticky"],
            "public_archive_rank":category_positions[item["slug"]],
        })
    # This audit does not grant permission to write. A separate
    # owner-scoped release with fresh full source CAS is necessary.
    return {
        "state":"SOURCE_BACKED_CATEGORY_REVIEW_ONLY",
        "category_id":category_id,
        "guide_category_rank":1,
        "homepage_guide_rank":1,
        "advisers":rows,
        "source_bound":True,
        "write_approved":False,
        "wordpress_post_attempts":0,
        "affiliate_click_requests":0,
        "checkout_stock":"UNKNOWN",
        "commission":"UNKNOWN",
    }


def main():
    try:
        print(json.dumps(assess(),ensure_ascii=False))
    except (PublishError,OSError,ValueError,TypeError,KeyError,AttributeError):
        print(json.dumps({
            "state":"CATEGORY_SOURCE_OR_PUBLIC_UNAVAILABLE",
            "write_approved":False,
            "wordpress_post_attempts":0,
        }))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
