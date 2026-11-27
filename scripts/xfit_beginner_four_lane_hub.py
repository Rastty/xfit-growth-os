"""One owned homepage-first beginner article. Promote the four actual offer lanes.

Reuse original sticky/category identity and freshness contracts; never replay
the older ready file or alter a merchant link, title, sticky flag or category.
"""
import json
from pathlib import Path
import sys
from scripts.xfit_beginner_hub_choice_onepost import (
    CHOICES, NEW_NAV, REVISION_MARKER, POST_ID, SLUG, URL,
    PublicChoiceLinks, source_get, identity, preserve_unchanged, sha,
    card_rank, homepage_get, archive_rank, category_public_get,
)
from scripts.xfit_verified_inlink_release import ALLOWLIST
from scripts.wp_publish import (
    PublishError, normalized_base, wp_request, verify_public, editorial_links,
)
from scripts.xfit_plant_refresh import read_source as plant_source, URL as PLANT_URL, TITLE as PLANT_TITLE
from scripts.xfit_equipment_refresh import read_source as equipment_source, URL as GEAR_URL, TITLE as GEAR_TITLE

BACKUP = Path("reports/backups/xfit-beginner-four-lane-20261127.json")
V2_MARKER = 'data-xfit-choice-version="four-lanes-20261127"'
V2_CHOICES = (CHOICES[0], CHOICES[1], PLANT_URL, CHOICES[2], GEAR_URL, CHOICES[3])
PLANT_HANDOFF = ALLOWLIST["beginner_plant_25458"].paragraph
PLANT_COMMERCE = ALLOWLIST["beginner_plant_commerce_25458"].paragraph
EDUCATION_URL = ALLOWLIST["beginner_plant_25458"].target

def card(href, title, note):
    return ('<p style="margin:0 0 8px"><a href="' + href +
            '" style="display:block;box-sizing:border-box;min-height:44px;padding:12px 14px;'
            'border-radius:8px;background:#fff;border:1px solid #cdded7;overflow-wrap:anywhere">'
            '<strong>' + title + '</strong><span style="display:block">' + note + '</span></a></p>')

V2_NAV = (
    '<section id="xfit-rychla-volba-20261121" ' + V2_MARKER +
    ' aria-label="První krok: rozhodovací rozcestník Xfit" style="border:1px solid #dbe5e2;'
    'border-radius:12px;padding:14px;margin:20px 0;background:#f6faf8">\n'
    '<h2 style="margin:0 0 8px">Co potřebujete právě teď?</h2>\n'
    '<p style="margin:0 0 14px">Vyberte jednu cestu. Pokud vám běžné jídlo a vybavení stačí, nic nekupujte.</p>\n'
    + card(V2_CHOICES[0], "Začínám cvičit – bez nákupu", "Nejdřív návyky, jídlo a trénink") + "\n"
    + card(V2_CHOICES[1], "Hledám syrovátkový protein", "Ceny a velikosti balení mléčných proteinů") + "\n"
    + card(V2_CHOICES[2], "Hledám rostlinný protein", "Ceny sójových, hrachových a dalších prášků") + "\n"
    + card(V2_CHOICES[3], "Hledám kreatin", "Monohydrát a cena za 100 g prášku") + "\n"
    + card(V2_CHOICES[4], "Vybavení na domácí cvičení", "Podložky a odporové gumy podle účelu") + "\n"
    + '<p style="margin:12px 0 0"><strong>Ještě nevím, co má smysl?</strong> '
    '<a href="' + V2_CHOICES[5] + '">Porovnat kreatin a protein, včetně možnosti nic nekoupit.</a></p>\n'
    '<p style="margin:8px 0 0"><small>Srovnání nabídek vycházejí z jednoho prodejce a obsahují označené partnerské odkazy. '
    'Cenu včetně dopravy, složení a dostupnost ověřte v obchodě.</small></p>\n</section>\n'
)
V2_PLANT_CONTEXT = (
    '<p data-xfit-handoff="xfit-beginner-plant-choice-25458-20261122">'
    '<strong>Nejdřív etiketa, až potom cena rostlinného proteinu.</strong> '
    'Pokud se stravujete vegansky nebo vám nevyhovuje mléčná bílkovina, '
    '<a href="' + EDUCATION_URL + '">projděte si návod k výběru rostlinného proteinu podle etikety, alergenů a ceny za skutečné bílkoviny</a>. '
    'Rostlinný původ nezaručuje nepřítomnost alergenů ani vhodnost při alergii. '
    'Pokud stačí běžné jídlo, prášek nepotřebujete; tento odkaz není doporučení doplněk koupit.</p>'
)

def public_choice_check(raw):
    parser = PublicChoiceLinks()
    parser.feed(raw)
    return (raw.count(REVISION_MARKER) == 1 and raw.count(V2_MARKER) == 1
            and tuple(parser.hrefs) == V2_CHOICES)

def revised(raw):
    if not isinstance(raw, str) or raw.count(REVISION_MARKER) != 1:
        raise PublishError("Beginner source marker missing or ambiguous")
    if V2_MARKER in raw:
        if not public_choice_check(raw):
            raise PublishError("Existing revised choice strip drifted")
        return raw
    # Compare exact previously reviewed blocks, not stale complete ready JSON.
    # No guessing around headings or replacement of intervening unrelated HTML.
    if any(raw.count(block) != 1 for block in (NEW_NAV, PLANT_HANDOFF, PLANT_COMMERCE)):
        raise PublishError("Exact previously released nav/context blocks unavailable")
    if not raw.index(NEW_NAV) < raw.index(PLANT_HANDOFF) < raw.index(PLANT_COMMERCE):
        raise PublishError("Unexpected plant context order")
    new = raw.replace(NEW_NAV, V2_NAV, 1).replace(PLANT_HANDOFF, V2_PLANT_CONTEXT, 1).replace(PLANT_COMMERCE + "\n", "", 1)
    if PLANT_COMMERCE in new:
        # A harmless absent trailing newline is permitted; exact block only.
        new = new.replace(PLANT_COMMERCE, "", 1)
    if (not public_choice_check(new) or set(editorial_links(new)) != set(editorial_links(raw)) | {GEAR_URL}
            or any("namaximum.cz" in url for url in editorial_links(new))):
        raise PublishError("Unexpected navigation or original link mutation")
    return new

def destination_check():
    for reader, url, title in ((plant_source, PLANT_URL, PLANT_TITLE),
                               (equipment_source, GEAR_URL, GEAR_TITLE)):
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
    print(json.dumps({"state": "FOUR_LANE_BACKUP_READY", "post_id": POST_ID,
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
    if not public_choice_check(read_public_page(SLUG)):
        raise PublishError("Six exact public links not verified")
    if card_rank(homepage_get()) != 1 or archive_rank(category_public_get()) != 1:
        raise PublishError("First-card discovery not verified after release")
    print(json.dumps({"state": "PUBLIC_FOUR_LANE_HUB_VERIFIED", "post_id": POST_ID,
        "url": URL, "public_choices": 6, "post_attempts": int(raw != after),
        "posts_changed": int(raw != after), "new_posts": 0,
        "public_site_modified": raw != after, "home_rank": 1, "category_rank": 1}))

if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Unsupported step")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, ValueError, OSError, KeyError, TypeError) as exc:
        print("XFIT_FOUR_LANE_HUB_BLOCKED: " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)
