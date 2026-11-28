"""Add one apparel shopping path to the exact previously released beginner hub."""
import json
from pathlib import Path
import sys
from scripts.xfit_beginner_four_lane_hub import (
    V2_NAV, public_choice_check, POST_ID, SLUG, URL, source_get, identity,
    preserve_unchanged, sha, card_rank, homepage_get, archive_rank,
    category_public_get,
)
from scripts.wp_publish import (
    PublishError, normalized_base, wp_request, verify_public, editorial_links,
)
from scripts.xfit_beginner_extra_lanes_hub import EXTRA_MARKER, EXTRA_NAV, DRINK_URL, BUTTER_URL, public_complete as previous_public_complete
from scripts.xfit_apparel_refresh import read_source as apparel_source, URL as APPAREL_URL, TITLE as APPAREL_TITLE

BACKUP = Path("reports/backups/xfit-beginner-apparel-hub-20261128.json")
APPAREL_MARKER = 'data-xfit-route="apparel-20261128"'
APPAREL_LINK = (
    '<p style="margin:0" ' + APPAREL_MARKER + '><a href="' + APPAREL_URL + '" style="display:block;padding:10px 0;min-height:44px;box-sizing:border-box">'
    '<strong>Fitness oblečení</strong> – trička, mikiny a legíny, velikost a cena varianty</a></p>'
)
NOTE = '<p style="margin:6px 0 0"><small>'
if EXTRA_NAV.count(NOTE) != 1:
    raise PublishError("Reviewed extra nav anchor drifted")
NEW_NAV = EXTRA_NAV.replace(NOTE, APPAREL_LINK + NOTE, 1).replace(
    'Jídlo a praktické pomůcky', 'Jídlo, oblečení a praktické pomůcky', 1)

def public_complete(raw):
    return (previous_public_complete(raw) and raw.count(APPAREL_MARKER) == 1
            and APPAREL_URL in editorial_links(raw))

def revised(raw):
    if not isinstance(raw, str) or raw.count(V2_NAV) != 1 or not previous_public_complete(raw):
        raise PublishError("Prior released navigation missing or drifted")
    if APPAREL_MARKER in raw:
        if raw.count(NEW_NAV) != 1 or not public_complete(raw):
            raise PublishError("Existing apparel navigation drifted")
        return raw
    old_links = editorial_links(raw)
    if raw.count(EXTRA_NAV) != 1 or APPAREL_URL in old_links:
        raise PublishError("Existing extra navigation requires review")
    new = raw.replace(EXTRA_NAV, NEW_NAV, 1)
    if (not public_complete(new) or len(new) > 30000
            or set(editorial_links(new)) != set(old_links) | {APPAREL_URL}
            or [link for link in editorial_links(new) if link != APPAREL_URL] != old_links):
        raise PublishError("Unexpected source mutation")
    return new

def destination_check():
    raw, _ = apparel_source()
    verify_public(APPAREL_URL, APPAREL_TITLE, raw)

def snapshot():
    destination_check()
    before = identity(source_get())
    raw = before["content"]["raw"]
    after = revised(raw)
    if card_rank(homepage_get()) != 1 or archive_rank(category_public_get()) != 1:
        raise PublishError("Existing first-card discovery lost")
    if BACKUP.exists():
        raise PublishError("Refusing to overwrite original")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({"schema": 1, "post_id": POST_ID, "before": before,
        "before_sha": sha(raw), "after_sha": sha(after), "wordpress_writes": 0},
        ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "APPAREL_HUB_BACKUP_READY", "post_id": POST_ID,
                      "wordpress_writes": 0, "change_required": raw != after}))

def apply():
    backup = json.loads(BACKUP.read_text(encoding="utf-8"))
    before = identity(backup["before"])
    raw = before["content"]["raw"]
    after = revised(raw)
    if (backup.get("schema") != 1 or backup.get("post_id") != POST_ID
            or backup.get("wordpress_writes") != 0
            or backup.get("before_sha") != sha(raw) or backup.get("after_sha") != sha(after)
            or identity(source_get()) != before):
        raise PublishError("Original source drifted after backup")
    if card_rank(homepage_get()) != 1 or archive_rank(category_public_get()) != 1:
        raise PublishError("Existing first-card discovery lost")
    if raw != after:
        try:
            wp_request(normalized_base(), "posts/" + str(POST_ID), payload={"content": after})
        except (PublishError, OSError, ValueError, TypeError):
            pass  # Exactly one POST, never retry unknown outcome.
        current = identity(source_get())
        if not preserve_unchanged(before, current) or current["content"]["raw"] != after:
            raise PublishError("Exact changed source not verified; no retry")
    verify_public(URL, before["title"]["raw"], after)
    from scripts.xfit_affiliate_public_audit import read_public_page
    if not public_complete(read_public_page(SLUG)):
        raise PublishError("Original six and three additional public links not verified")
    if card_rank(homepage_get()) != 1 or archive_rank(category_public_get()) != 1:
        raise PublishError("First-card discovery not verified after release")
    print(json.dumps({"state": "PUBLIC_APPAREL_HUB_VERIFIED", "post_id": POST_ID,
        "url": URL, "public_choices": 9, "post_attempts": int(raw != after),
        "posts_changed": int(raw != after), "new_posts": 0,
        "public_site_modified": raw != after, "home_rank": 1, "category_rank": 1}))

if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Unsupported step")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, ValueError, OSError, KeyError, TypeError) as exc:
        print("XFIT_APPAREL_HUB_BLOCKED: " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)
