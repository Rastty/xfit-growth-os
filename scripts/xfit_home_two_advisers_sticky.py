#!/usr/bin/env python3
"""One-time, rollback-first homepage promotion of TWO EXISTING money advisers.

Uses only WordPress's native sticky flag, not theme/menu/category/price edits.
Protects the existing reader-first no-buy hub at homepage rank #1.
A failed/uncertain POST can have committed: never retry, always reconcile GET.
Other sticky posts and all source content/metadata must remain unchanged.
"""
import hashlib
import json
from pathlib import Path
import sys

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts.xfit_home_sticky_guide_onepost import (
    POST_ID as GUIDE_ID, SLUG as GUIDE_SLUG, selected as approved_guide,
    source_get as get_guide, sticky_ids, sticky_list, homepage_get,
    HeadlineCards,
)
from scripts.xfit_supplements_two_advisors_category import (
    PAGES as ADVISERS, page_identity, source_get as get_adviser,
)

BACKUP = Path("reports/backups/xfit-home-advisers-sticky-20261122.json")
MAX_STICKIES = 8


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def public_order():
    html = homepage_get()
    if not isinstance(html, str) or len(html) < 250:
        raise PublishError("Homepage cannot be verified")
    headings = HeadlineCards()
    headings.feed(html)
    paths = list(dict.fromkeys(headings.hrefs))
    if not 8 <= len(paths) <= 200:
        raise PublishError("Unexpected public homepage cards")
    if paths[0] != "/" + GUIDE_SLUG + "/":
        raise PublishError("Reader-first guide is not homepage rank one")
    return paths


def rank(order, slug):
    path = "/" + slug + "/"
    return order.index(path) + 1 if path in order else None


def snapshot_sources():
    guide = approved_guide(get_guide())
    if guide["sticky"] is not True:
        raise PublishError("Reader-first homepage guide is no longer sticky")
    advisers = [page_identity(get_adviser(row[0]), row) for row in ADVISERS]
    if any(p["id"] == GUIDE_ID for p in advisers):
        raise PublishError("Guide and adviser identities collide")
    return guide, advisers


def snapshot():
    guide, advisers = snapshot_sources()
    sticky = sticky_ids(sticky_list())
    if not 1 <= len(sticky) <= MAX_STICKIES or GUIDE_ID not in sticky:
        raise PublishError("Homepage sticky inventory drifted")
    for row, post in zip(ADVISERS, advisers):
        if (post["id"] in sticky) != post["sticky"]:
            raise PublishError("Adviser sticky inventory differs from source")
    order = public_order()
    if BACKUP.exists():
        raise PublishError("Previous rollback artifact must never be overwritten")
    backup = {
        "schema": 1,
        "scope": "xfit-two-approved-home-advisers-sticky-20261122",
        "guide_before": guide,
        "advisers_before": advisers,
        "sticky_ids_before": sticky,
        "home_order_before": order,
        "post_attempts": 0,
        "body_hashes": {str(post["id"]): digest(post["content"]["raw"])
                        for post in [guide, *advisers]},
    }
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps(backup, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "state": "HOME_ADVISERS_PREWRITE_FULL_BACKUP_READY",
        "guide_rank": 1,
        "creatine_rank": rank(order, ADVISERS[0][1]),
        "whey_rank": rank(order, ADVISERS[1][1]),
        "existing_stickies_preserved": len(sticky),
        "advisers_to_pin": sum(not post["sticky"] for post in advisers),
        "post_attempts": 0, "wordpress_writes": 0,
    }), flush=True)


def source_without_mutable_fields(post):
    allowed = dict(post)
    allowed.pop("sticky", None)
    allowed.pop("modified_gmt", None)
    return allowed


def check_backup(saved):
    if (type(saved) is not dict or saved.get("schema") != 1
            or saved.get("scope") !=
               "xfit-two-approved-home-advisers-sticky-20261122"
            or saved.get("post_attempts") != 0
            or not isinstance(saved.get("home_order_before"), list)
            or not isinstance(saved.get("sticky_ids_before"), list)
            or not isinstance(saved.get("advisers_before"), list)
            or len(saved["advisers_before"]) != len(ADVISERS)):
        raise PublishError("Untrusted backup manifest")
    guide = approved_guide(saved.get("guide_before"))
    advisers = [page_identity(post, row)
                for row, post in zip(ADVISERS, saved["advisers_before"])]
    for post in [guide, *advisers]:
        if saved.get("body_hashes", {}).get(str(post["id"])) != digest(
                post["content"]["raw"]):
            raise PublishError("Rollback content checksum mismatch")
    if GUIDE_ID not in saved["sticky_ids_before"]:
        raise PublishError("Missing protected guide in rollback")
    return guide, advisers


def apply():
    if not BACKUP.is_file():
        raise PublishError("Missing mandatory prewrite backup")
    saved = json.loads(BACKUP.read_text(encoding="utf-8"))
    old_guide, old_advisers = check_backup(saved)
    guide, advisers = snapshot_sources()
    if guide != old_guide or advisers != old_advisers:
        raise PublishError("Concurrent WordPress source change before first write")
    if sticky_ids(sticky_list()) != saved["sticky_ids_before"]:
        raise PublishError("Concurrent sticky inventory change before first write")
    if public_order() != saved["home_order_before"]:
        raise PublishError("Concurrent public homepage order change")

    expected_ids = set(saved["sticky_ids_before"])
    attempts = 0
    for row, old in zip(ADVISERS, old_advisers):
        post_id = row[0]
        # Fail closed on concurrent updates and preserve hub & all other
        # sticky posts. This is required even after our own first POST.
        if approved_guide(get_guide()) != old_guide:
            raise PublishError("Reader-first source edited during promotion")
        now = page_identity(get_adviser(post_id), row)
        if now != old:
            raise PublishError("Adviser source modified before its POST")
        if sticky_ids(sticky_list()) != sorted(expected_ids):
            raise PublishError("Other sticky post changed during promotion")
        if rank(public_order(), GUIDE_SLUG) != 1:
            raise PublishError("Reader-first homepage rank displaced")
        if old["sticky"]:
            continue
        # Exactly one POST per target; even a timeout might mean success.
        print(json.dumps({
            "state": "HOME_STICKY_ONEPOST_ATTEMPT_START",
            "post_id": post_id, "post_attempt_number": attempts + 1,
        }), flush=True)
        attempts += 1
        try:
            wp_request(normalized_base(), "posts/" + str(post_id),
                       payload={"sticky": True})
        except (PublishError, OSError, ValueError, TypeError):
            pass
        try:
            after = page_identity(get_adviser(post_id), row)
            seen_ids = sticky_ids(sticky_list())
        except (PublishError, OSError, ValueError, TypeError) as exc:
            raise PublishError("Sticky POST outcome uncertain, never repeat") from exc
        expected_ids.add(post_id)
        if (after["sticky"] is not True
                or source_without_mutable_fields(after) !=
                   source_without_mutable_fields(old)
                or seen_ids != sorted(expected_ids)):
            raise PublishError("Unexpected post/sticky changes after POST; no retry")
        print(json.dumps({
            "state": "HOME_STICKY_AUTH_READBACK_VERIFIED",
            "post_id": post_id, "post_attempt_number": attempts,
            "content_changed": False,
        }), flush=True)

    final_guide, final_advisers = snapshot_sources()
    if final_guide != old_guide:
        raise PublishError("Protected guide changed after adviser promotion")
    for old, current in zip(old_advisers, final_advisers):
        if (not current["sticky"] or
                source_without_mutable_fields(old) !=
                source_without_mutable_fields(current)):
            raise PublishError("Adviser content or metadata changed unexpectedly")
    if sticky_ids(sticky_list()) != sorted(expected_ids):
        raise PublishError("Original sticky inventory not preserved")
    order = public_order()
    ranks = {row[1]: rank(order, row[1]) for row in ADVISERS}
    success = {ranks[row[1]] for row in ADVISERS} == {2, 3}
    result = {
        "state": ("PUBLIC_HOME_TWO_ADVISERS_TOP3_VERIFIED" if success
                  else "WP_STICKY_SET_PUBLIC_TOP3_UNVERIFIED"),
        "reader_first_guide_rank": rank(order, GUIDE_SLUG),
        "creatine_adviser_rank": ranks[ADVISERS[0][1]],
        "whey_adviser_rank": ranks[ADVISERS[1][1]],
        "old_other_stickies_preserved": True,
        "post_attempts": attempts,
        "new_posts": 0, "post_content_changes": 0,
        "offer_or_affiliate_link_edits": 0, "category_or_menu_edits": 0,
        "approved_or_paid_commissions": "UNKNOWN",
    }
    print(json.dumps(result), flush=True)
    if not success:
        # Do not automatically undo a possibly successful write either;
        # reconcile source and public on the next owner-controlled action.
        raise PublishError("Public homepage ranking not verified; no retry")
    return result


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Use snapshot or apply")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, OSError, ValueError, TypeError, KeyError) as exc:
        # Never emit original body, token or product URLs into action logs.
        print("XFIT_HOME_ADVISERS_STICKY_ERROR: " + type(exc).__name__,
              file=sys.stderr)
        sys.exit(2)
