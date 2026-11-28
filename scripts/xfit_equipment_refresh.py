"""One owned equipment comparison: refresh generated offers only, preserving editorial source."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from scripts.xfit_equipment_comparison import CATALOG, PREPARED, SLUG, URL, build_document, BUDGET_MARKER, MAX_CARDS, NAV_MARKER, LEGACY_NAV, LEGACY_INTRO, INTRO
from scripts.xfit_catalog_retrieval import verified_catalog_fetch_time
from scripts.xfit_editorial_gate import check_document
from scripts.wp_publish import (
    MARKER, PublishError, normalized_base, wp_request, verify_public,
    editorial_links, classify_wp_write_failure,
)

POST_ID = 26154
TITLE = "Vybavení na domácí cvičení: nabídky podložek a odporových gum"
SNAPSHOT = Path("reports/backups/xfit-equipment-before-refresh.json")
RETRIEVAL = re.compile(r'<p class="xfit-feed-retrieval"><small>[^<]*(?:<strong>[^<]+</strong>)[^<]*</small></p>')
START = '<h2 id="xfit-gear-mat">Podložky na cvičení – aktuální nabídky</h2>'
END = "<h2>Co zkontrolovat v obchodě před objednávkou</h2>"
OFFER_HEADING = '<h2 id="xfit-gear-band">'
MAX_BYTES = 400000
NAV_BLOCK = re.compile(r'<nav ' + re.escape(NAV_MARKER) + r'[^>]*>.*?</nav>', re.S)
GUIDE = Path("content/revisions/equipment-buying-guide.html")
GUIDE_MARKER = 'id="xfit-gear-buying-guide-v1"'
GUIDE_ANCHOR = "<h2>Metodika výběru</h2>"
STRENGTH_GUIDE = Path("content/revisions/strength-accessory-buying-guide.html")
STRENGTH_MARKER = 'id="xfit-strength-accessory-guide-v1"'
GYM_TARGET = "https://xfit.cz/domaci-posilovny-a-workout-hriste/"
GYM_MARKER = 'data-xfit-handoff="xfit-gear-home-gym-plan-v1"'
GYM_ANCHOR = '<h3>Výběr podle místa, které máte k dispozici</h3>'
GYM_LINK = (
    '<p ' + GYM_MARKER + '><strong>Plánujete celou domácí posilovnu nebo workout na zahradě?</strong> '
    'Projděte si <a href="' + GYM_TARGET + '">průvodce rozvržením prostoru, rozpočtem a venkovním workoutem</a> '
    's modelovými rozpočty a postupem od cvičení bez vybavení až po větší investici.</p>'
)


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def segments(body):
    if (not isinstance(body, str) or not 1000 <= len(body.encode("utf-8")) <= MAX_BYTES
            or body.count(START) != 1 or body.count(END) != 1 or body.count(OFFER_HEADING) != 1):
        raise PublishError("Equipment generated block boundaries missing or ambiguous")
    dates = list(RETRIEVAL.finditer(body))
    begin, end = body.index(START), body.index(END)
    if len(dates) != 1 or dates[0].end() >= begin or not begin < body.index(OFFER_HEADING) < end:
        raise PublishError("Equipment retrieval date or offer block order invalid")
    budget_start = '<section ' + BUDGET_MARKER
    if BUDGET_MARKER in body:
        if body.count(BUDGET_MARKER) != 1 or body.count(budget_start) != 1:
            raise PublishError("Ambiguous equipment budget section")
        budget_begin = body.index(budget_start)
        if not dates[0].end() < budget_begin < begin or not body[budget_begin:begin].rstrip().endswith("</section>"):
            raise PublishError("Equipment budget boundary drifted")
        begin = budget_begin
    block = body[begin:end]
    if not 2 <= block.count('class="xfit-product-card"') <= MAX_CARDS or not 2 <= block.count('rel="sponsored nofollow noopener noreferrer"') <= MAX_CARDS:
        raise PublishError("Unexpected equipment generated card structure")
    return dates[0].span(), (begin, end)


def splice(old, new):
    if not old.startswith(MARKER + "\n") or old.count(MARKER) != 1:
        raise PublishError("Missing original equipment ownership marker")
    (d1, d2), (b1, b2) = segments(old)
    (n1, n2), (m1, m2) = segments(new)
    # Copy only the catalog retrieval date and contiguous commercial section.
    # All other existing editorial HTML survives byte-for-byte, even if a human
    # or a separate authorized editor has added a paragraph since launch.
    output = old[:d1] + new[n1:n2] + old[d2:b1] + new[m1:m2] + old[b2:]
    # Refresh the single generated category navigation with the same feed as
    # the cards. Initial migration is restricted to the exact owned HTML.
    new_nav = list(NAV_BLOCK.finditer(new))
    if len(new_nav) != 1 or new.count(NAV_MARKER) != 1:
        raise PublishError("Expected exactly one generated category navigation")
    existing = list(NAV_BLOCK.finditer(output))
    if NAV_MARKER in output:
        if len(existing) != 1 or output.count(NAV_MARKER) != 1 or LEGACY_NAV in output:
            raise PublishError("Ambiguous equipment category navigation")
        output = output[:existing[0].start()] + new_nav[0].group() + output[existing[0].end():]
    else:
        if output.count(LEGACY_NAV) != 1:
            raise PublishError("Exact legacy equipment navigation missing")
        output = output.replace(LEGACY_NAV, new_nav[0].group(), 1)
    if output.count(LEGACY_INTRO) == 1 and INTRO not in output:
        output = output.replace(LEGACY_INTRO, INTRO, 1)
    elif output.count(INTRO) != 1 or LEGACY_INTRO in output:
        raise PublishError("Equipment introduction drifted")
    if GUIDE_MARKER not in output:
        guide = GUIDE.read_text(encoding="utf-8").strip()
        if guide.count(GUIDE_MARKER) != 1 or output.count(GUIDE_ANCHOR) != 1:
            raise PublishError("Reviewed equipment buying guide insertion unavailable")
        output = output.replace(GUIDE_ANCHOR, guide + "\n" + GUIDE_ANCHOR, 1)
    elif output.count(GUIDE_MARKER) != 1:
        raise PublishError("Duplicate equipment buying guide marker")
    if GYM_MARKER not in output:
        if output.count(GYM_ANCHOR) != 1 or GYM_TARGET in editorial_links(output):
            raise PublishError("Reviewed gym planning route insertion unavailable")
        output = output.replace(GYM_ANCHOR, GYM_LINK + "\n" + GYM_ANCHOR, 1)
    elif output.count(GYM_MARKER) != 1 or output.count(GYM_LINK) != 1:
        raise PublishError("Ambiguous gym planning handoff")
    if STRENGTH_MARKER not in output:
        guide = STRENGTH_GUIDE.read_text(encoding="utf-8").strip()
        if guide.count(STRENGTH_MARKER) != 1 or output.count(GUIDE_ANCHOR) != 1:
            raise PublishError("Reviewed strength accessory guide insertion unavailable")
        output = output.replace(GUIDE_ANCHOR, guide + "\n" + GUIDE_ANCHOR, 1)
    elif output.count(STRENGTH_MARKER) != 1:
        raise PublishError("Duplicate strength accessory guide marker")
    check_document({"content": output}, commercial=True)
    return output


def read_source():
    post = wp_request(normalized_base(),
        "posts/" + str(POST_ID) + "?context=edit&_fields=id,slug,status,link,content,title,modified_gmt")
    raw = (post.get("content") or {}).get("raw")
    title = (post.get("title") or {}).get("raw")
    modified = post.get("modified_gmt")
    if (type(post.get("id")) is not int or post["id"] != POST_ID or post.get("slug") != SLUG
            or post.get("status") != "publish" or post.get("link") != URL or title != TITLE
            or not isinstance(raw, str) or not isinstance(modified, str) or not modified):
        raise PublishError("Pinned equipment post identity/title/source changed")
    if not raw.startswith(MARKER + "\n"):
        raise PublishError("Missing equipment post ownership")
    segments(raw)
    return raw, modified


def fresh_document():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    doc = json.loads(PREPARED.read_text(encoding="utf-8"))
    expected = build_document(catalog, os.environ["XFIT_AFFIL_DEFAULT_LINK"],
                              os.environ["XFIT_AFFIL_SAMPLE_PRODUCT_LINK"])
    if doc != expected or doc["slug"] != SLUG or doc["title"] != TITLE:
        raise PublishError("Prepared equipment source does not match the current feed")
    return doc


def snapshot():
    doc = fresh_document()
    old, modified = read_source()
    new = splice(old, doc["content"])
    if GYM_MARKER not in old:
        # Check the exact published destination before adding its first link.
        from scripts.xfit_legacy_home_gym_workout import read as read_gym, MARKER as GYM_GUIDE_MARKER
        gym = read_gym()
        if gym["link"] != GYM_TARGET or GYM_GUIDE_MARKER not in gym["content"]["raw"]:
            raise PublishError("New gym planning guide not live")
        verify_public(GYM_TARGET, gym["title"]["raw"], gym["content"]["rendered"])
    if SNAPSHOT.exists():
        raise PublishError("Refusing to overwrite prewrite backup")
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps({
        "schema": 1, "post_id": POST_ID, "slug": SLUG, "url": URL,
        "original_raw": old, "modified_gmt": modified,
        "before_sha256": sha(old), "after_sha256": sha(new),
        "prepared_body_sha256": sha(doc["content"]), "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "EQUIPMENT_PREWRITE_BACKUP_READY", "post_id": POST_ID,
                      "remote_writes": 0, "change_required": new != old}))


def apply():
    doc = fresh_document()
    saved = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    old = saved.get("original_raw")
    if (not isinstance(old, str) or saved.get("schema") != 1
            or saved.get("post_id") != POST_ID or saved.get("slug") != SLUG
            or saved.get("url") != URL or saved.get("remote_writes") != 0
            or sha(old) != saved.get("before_sha256")
            or sha(doc["content"]) != saved.get("prepared_body_sha256")):
        raise PublishError("Equipment backup manifest invalid")
    new = splice(old, doc["content"])
    if sha(new) != saved.get("after_sha256"):
        raise PublishError("Equipment prepared replacement differs from backup")
    # Fail closed on any intervening source edit, including modification time.
    current, modified = read_source()
    if current != old or modified != saved.get("modified_gmt"):
        raise PublishError("Equipment source changed after immutable backup")
    if new == old:
        verify_public(URL, TITLE, old)
        print(json.dumps({"state": "unchanged_public_verified", "post_id": POST_ID,
                          "slug": SLUG, "url": URL, "public_site_modified": False,
                          "post_attempts": 0}))
        return
    try:
        answer = wp_request(normalized_base(), "posts/" + str(POST_ID), payload={"content": new})
        if answer.get("id") != POST_ID or answer.get("status") != "publish":
            raise PublishError("Unexpected equipment write response identity")
    except (PublishError, OSError, ValueError, KeyError) as exc:
        # Exactly one POST; diagnose by GET, never blindly retry.
        print(json.dumps({"state": "EQUIPMENT_WRITE_DIAGNOSTIC", "post_id": POST_ID,
                          "classification": classify_wp_write_failure(exc), "post_attempts": 1}))
    try:
        actual, _ = read_source()
    except (PublishError, OSError, ValueError, KeyError):
        print(json.dumps({"state": "EQUIPMENT_REFRESH_UNCERTAIN", "post_id": POST_ID, "post_attempts": 1}))
        raise PublishError("Authenticated equipment readback unavailable; do not retry")
    if actual != new or editorial_links(actual) != editorial_links(new):
        state = "EQUIPMENT_REFRESH_UNCHANGED" if actual == old else "EQUIPMENT_REFRESH_UNCERTAIN"
        print(json.dumps({"state": state, "post_id": POST_ID, "post_attempts": 1}))
        raise PublishError("Equipment source did not match intended content; no retry")
    verify_public(URL, TITLE, new)
    print(json.dumps({"state": "live_verified", "post_id": POST_ID, "slug": SLUG,
                      "url": URL, "public_site_modified": True, "posts_changed": 1,
                      "post_attempts": 1, "new_posts": 0, "deletes": 0, "redirects": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=("snapshot", "apply"))
    args = parser.parse_args()
    try:
        (snapshot if args.step == "snapshot" else apply)()
    except (PublishError, ValueError, OSError, KeyError, TypeError) as exc:
        print("XFIT_EQUIPMENT_REFRESH_BLOCKED: " + type(exc).__name__)
        raise SystemExit(2)
