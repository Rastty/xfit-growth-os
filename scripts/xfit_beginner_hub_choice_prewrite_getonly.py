#!/usr/bin/env python3
"""One-time sanitized GET-only explanation of prewrite reader-hub refusal.

Never print raw article text, private URLs/IDs beyond approved WP post identity,
credentials, affiliate parameters or visitor data. This process cannot POST.
"""
import json
from pathlib import Path
import sys

from scripts.wp_publish import (
    PublishError, assert_prewrite_source, article_visible, editorial_links,
)
from scripts import xfit_beginner_hub_choice_onepost as b
from scripts.xfit_home_sticky_guide_onepost import homepage_get, card_rank
from scripts.xfit_supplements_category_hub_onepost import category_public_get, archive_rank

REPORT=Path("reports/xfit-beginner-choice-prewrite-readonly.json")


def run(*, read_ready=b.ready, read_post=b.source_get,
        read_home=homepage_get, read_category=category_public_get):
    result = {
        "state":"GET_ONLY_BEGINNER_CHOICE_PREFLIGHT",
        "wordpress_writes":0, "post_attempts":0,
        "post_id":b.POST_ID,
        "approved_git_document":"UNKNOWN",
        "published_wp_identity":"UNKNOWN",
        "ready_git_body_and_links_match_live_wp":False,
        "intro_navigation_rewrite_eligible":False,
        "expected_old_nav_marker_count":None,
        "expected_first_section_count":None,
        "home_page_rank":None, "category_page_rank":None,
        "failure_stage":None,
    }
    try:
        previous=read_ready()
        result["approved_git_document"]="VALID"
    except (PublishError,OSError,ValueError,TypeError):
        result["failure_stage"]="READY_DOCUMENT"
        return result
    try:
        post=b.identity(read_post())
        result["published_wp_identity"]="EXACT_PUBLISHED_STICKY_CATEGORY"
    except (PublishError,OSError,ValueError,TypeError):
        result["failure_stage"]="WORDPRESS_IDENTITY"
        return result
    raw=post["content"]["raw"]
    result["original_content_sha256"]=b.sha(raw)
    result["original_content_bytes"]=len(raw.encode("utf-8"))
    result["expected_old_nav_marker_count"]=raw.count(b.OLD_START)
    result["expected_first_section_count"]=raw.count(b.END_NEXT_SECTION)
    try:
        assert_prewrite_source(post,previous)
        result["ready_git_body_and_links_match_live_wp"]=True
    except (PublishError,OSError,ValueError,TypeError):
        result["failure_stage"]="GIT_APPROVED_SOURCE_DRIFT"
        return result
    try:
        updated=b.revised_from_original(post,previous)
        result["intro_navigation_rewrite_eligible"]=True
        result["approved_new_content_bytes"]=len(updated.encode("utf-8"))
    except (PublishError,OSError,ValueError,TypeError):
        result["failure_stage"]="NAVIGATION_EXTRACTION_OR_GUARD"
        return result
    try:
        result["home_page_rank"]=card_rank(read_home())
    except (PublishError,OSError,ValueError,TypeError):
        result["failure_stage"]="PUBLIC_HOME"
        return result
    try:
        result["category_page_rank"]=archive_rank(read_category())
    except (PublishError,OSError,ValueError,TypeError):
        result["failure_stage"]="PUBLIC_CATEGORY"
        return result
    if result["home_page_rank"]!=1 or result["category_page_rank"]!=1:
        result["failure_stage"]="PUBLIC_DISCOVERY_DRIFT"
    else:
        result["failure_stage"]="ALL_PREWRITE_CHECKS_PASS"
    return result


def main():
    report=run()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__=="__main__":
    sys.exit(main())
