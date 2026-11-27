"""Add two compact shopping paths after the already-live homepage-first decision strip."""
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
from scripts.xfit_drinkware_refresh import read_source as drink_source, URL as DRINK_URL, TITLE as DRINK_TITLE
from scripts.xfit_nut_butter_refresh import read_source as butter_source, URL as BUTTER_URL, TITLE as BUTTER_TITLE

BACKUP = Path("reports/backups/xfit-beginner-extra-lanes-20261127.json")
EXTRA_MARKER = 'id="xfit-dalsi-nabidky-20261127"'
EXTRA_NAV = (
    '<section ' + EXTRA_MARKER + ' aria-label="Další praktické nákupy" '
    'style="border:1px solid #dbe5e2;border-radius:12px;padding:12px;margin:12px 0;background:#fff">'
    '<h2 style="margin:0 0 6px;font-size:1.15em">Jídlo a praktické pomůcky</h2>'
    '<p style="margin:0 0 6px">Pokud je opravdu využijete, porovnejte nabídky. Není nutné kupovat nic navíc.</p>'
    '<p style="margin:0"><a href="' + DRINK_URL + '" style="display:block;padding:10px 0;min-height:44px;box-sizing:border-box">'
    '<strong>Šejkry a sportovní lahve</strong> – míchání a přenášení nápojů</a></p>'
    '<p style="margin:0"><a href="' + BUTTER_URL + '" style="display:block;padding:10px 0;min-height:44px;box-sizing:border-box">'
    '<strong>Arašídová a ořechová másla</strong> – cena za 100 g a balení</a></p>'
    '<p style="margin:6px 0 0"><small>Nabídky jednoho prodejce s označenými partnerskými odkazy. '
    'Ověřte cenu s dopravou, etiketu a alergeny.</small></p></section>\n'
)

def public_complete(raw):
    return (public_choice_check(raw) and raw.count(EXTRA_MARKER) == 1
            and DRINK_URL in editorial_links(raw) and BUTTER_URL in editorial_links(raw))

def revised(raw):
    if not isinstance(raw, str) or raw.count(V2_NAV) != 1 or not public_choice_check(raw):
        raise PublishError("Exact released navigation missing or drifted")
    if EXTRA_MARKER in raw:
        if raw.count(EXTRA_NAV) != 1 or not public_complete(raw):
            raise PublishError("Existing additional navigation drifted")
        return raw
    old_links = editorial_links(raw)
    if DRINK_URL in old_links or BUTTER_URL in old_links:
        raise PublishError("Existing additional route requires separate review")
    new = raw.replace(V2_NAV, V2_NAV + EXTRA_NAV, 1)
    if (not public_complete(new) or len(new) > 30000
            or set(editorial_links(new)) != set(old_links) | {DRINK_URL, BUTTER_URL}
            or [link for link in editorial_links(new) if link not in (DRINK_URL,BUTTER_URL)] != old_links):
        raise PublishError("Unexpected source mutation")
    return new

def destination_check():
    for reader, url, title in ((drink_source, DRINK_URL, DRINK_TITLE),
                               (butter_source, BUTTER_URL, BUTTER_TITLE)):
        raw, _ = reader()
        verify_public(url, title, raw)

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
    print(json.dumps({"state": "EXTRA_LANES_BACKUP_READY", "post_id": POST_ID,
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
        raise PublishError("Original six and two additional public links not verified")
    if card_rank(homepage_get()) != 1 or archive_rank(category_public_get()) != 1:
        raise PublishError("First-card discovery not verified after release")
    print(json.dumps({"state": "PUBLIC_EXTRA_LANES_HUB_VERIFIED", "post_id": POST_ID,
        "url": URL, "public_choices": 8, "post_attempts": int(raw != after),
        "posts_changed": int(raw != after), "new_posts": 0,
        "public_site_modified": raw != after, "home_rank": 1, "category_rank": 1}))

if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Unsupported step")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, ValueError, OSError, KeyError, TypeError) as exc:
        print("XFIT_EXTRA_LANES_HUB_BLOCKED: " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)
