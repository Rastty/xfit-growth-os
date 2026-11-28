"""Reviewed onepost: remove fake example links and expired promotions, add useful fit guidance."""
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from scripts.wp_publish import normalized_base, wp_request, PublishError, verify_public, normalize_visible, article_visible, editorial_links
from scripts.xfit_legacy_mat_release import stable_metadata
from scripts.xfit_coupon_cleanup import stripped, QUARANTINE_IDS
from scripts.xfit_coupon_attempt_ledger import load as ledger_load, reserve as ledger_reserve
from scripts.xfit_public_coupon_watch import probe
from scripts.xfit_apparel_refresh import read_source, URL as TARGET, TITLE as TARGET_TITLE

SLUG = "damske-obleceni-do-posilovny-inspirace-pro-ruzne-typy-tel"
URL = "https://xfit.cz/" + SLUG + "/"
TITLE = "Dámské oblečení do posilovny: Inspirace pro různé typy těl"
MARKER = 'id="xfit-gymwear-practical-20261128"'
BACKUP = Path("reports/backups/xfit-legacy-gymwear-original.json")
FIELDS = "id,slug,status,link,title,content,excerpt,categories,tags,sticky,featured_media,modified_gmt"
BODY = Path("content/revisions/legacy-gymwear-practical.html")
ANCHORS = ("Ve své kolekci nabízíme", "Naše styly jsou navrženy", "Naše nabídka zahrnuje",
           "Prozkoumejte naši inspirativní kolekci", "Pro ženy se štíhlou postavou",
           "Dámské sportovní legíny", "Dámské sportovní boty")
FAKE_LABELS = {
    "Tipy pro ženy s pevnými nohami", "Vyberte si legíny podle tvaru zadku",
    "Jak vybrat správné kalhoty do posilovny pro ženy s kulatým břichem",
    "Jak vybrat správné sportovní podprsenky pro ženy s většími poprsími",
    "Tipy na trička a tílka pro Hubené ženy",
    "Pro ženy s širšími rameny doporučujeme tento typ sportovního tílka",
    "Jak vybrat správné sportovní boty pro kardio tréninky",
    "Doporučené doplňky pro všechny typy těl", "Chcete vypadat stylově? Zkuste sportovní hodinky!",
    "náš blog",
}
REPLACEMENTS = (
    ("Ve své kolekci nabízíme širokou škálu oblečení, včetně legín, tišortek, sportovních podprsenek a dalších doplňků.",
     "Mezi základní možnosti patří legíny, kraťasy, trička a sportovní podprsenky; vyberte podle pohybu, nikoli podle nutnosti koupit celý set."),
    ("Naše styly jsou navrženy tak, abychom zdůraznili vaše přednosti a vykreslili vás v nejlepším světle.",
     "Pohodlný střih není podmíněn typem postavy; poměřte své rozměry s tabulkou konkrétního výrobce."),
    ("Naše nabídka zahrnuje materiály, které jsou pro pohyb a potřeby sportovců ideální – elastické, odvodňující pot, prodyšné a pohodlné.",
     "Xfit.cz je redakční poradce, nikoli výrobce ani prodejce vlastního oblečení. Funkčnost závisí na konkrétním materiálu, střihu a zpracování."),
    ("Prozkoumejte naši inspirativní kolekci dámského oblečení do posilovny a najděte si svůj oblíbený styl, který bude korespondovat s vaší osobností a jedinečností.",
     "Při výběru se řiďte pohodlím, vlastním stylem a tím, jak oblečení funguje při konkrétním tréninku."),
)
LINK = re.compile(r'<a\b[^>]*\bhref\s*=\s*(["\x27])([^"\x27]+)\1[^>]*>(.*?)</a\s*>', re.I | re.S)
H2 = re.compile(r"<h2(?:\s+[^>]*)?>", re.I)

def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def read():
    rows = wp_request(normalized_base(), "posts?" + urlencode({
        "slug": SLUG, "context": "edit", "status": "publish", "per_page": 2, "_fields": FIELDS}))
    if not isinstance(rows, list) or len(rows) != 1:
        raise PublishError("Expected one exact published legacy article")
    row = rows[0]
    if (type(row.get("id")) is not int or row["id"] in QUARANTINE_IDS
            or row.get("slug") != SLUG or row.get("link") != URL or row.get("status") != "publish"
            or normalize_visible(row.get("title", {}).get("raw", "")) != normalize_visible(TITLE)
            or not isinstance(row.get("modified_gmt"), str)):
        raise PublishError("Legacy source identity drift or quarantine")
    stable_metadata(row)
    return row

def fake(href):
    p = urlsplit(href)
    return (p.hostname or "").removeprefix("www.") == "example.com" and p.scheme in ("http", "https") and not p.username and not p.password and not p.port

def revise(raw):
    if not isinstance(raw, str) or not 1500 <= len(raw.encode()) <= 400000:
        raise PublishError("Unexpected source size")
    if MARKER in raw:
        raise PublishError("Existing revised article: no automatic rewrite")
    text, _ = article_visible(raw)
    if any(normalize_visible(anchor) not in text for anchor in ANCHORS):
        raise PublishError("Reviewed old article anchors missing")
    old_links = editorial_links(raw)
    if TARGET in old_links:
        raise PublishError("Existing target link requires review")
    found = []
    def unwrap(match):
        if not fake(match.group(2)):
            return match.group(0)
        label = normalize_visible(match.group(3))
        if label not in {normalize_visible(x) for x in FAKE_LABELS}:
            raise PublishError("Unreviewed placeholder label")
        found.append(label)
        return match.group(3)
    updated = LINK.sub(unwrap, raw)
    if sorted(found) != sorted(normalize_visible(x) for x in FAKE_LABELS):
        raise PublishError("Reviewed ten placeholder links differ")
    updated, count = stripped(updated)
    if count not in (0, 3) or "5nm2022" in updated.casefold():
        raise PublishError("Unexpected coupon shape")
    for old, new in REPLACEMENTS:
        if updated.count(old) != 1:
            raise PublishError("Reviewed editorial phrase changed")
        updated = updated.replace(old, new, 1)
    first = H2.search(updated)
    extra = BODY.read_text(encoding="utf-8").strip()
    if not first or extra.count(MARKER) != 1 or editorial_links(extra) != [TARGET]:
        raise PublishError("Reviewed insertion unavailable")
    updated = updated[:first.start()] + extra + "\n" + updated[first.start():]
    # Preserve all genuine original links and all existing media/metadata.
    remaining = [href for href in old_links if not fake(href)]
    if [href for href in editorial_links(updated) if href != TARGET] != remaining or editorial_links(updated).count(TARGET) != 1:
        raise PublishError("Unexpected genuine link change")
    for token in ("<img", "<iframe", "<video", "<figure", "[caption", "[embed", "[gallery"):
        if raw.casefold().count(token) != updated.casefold().count(token):
            raise PublishError("Unexpected media change")
    return updated, count, len(found)

def snapshot():
    target_raw, _ = read_source()
    verify_public(TARGET, TARGET_TITLE, target_raw)
    row = read()
    old = row["content"]["raw"]
    new, coupons, placeholders = revise(old)
    ledger = ledger_load()
    if coupons and row["id"] in ledger.ids:
        raise PublishError("Coupon ID already reserved; no repeat")
    if BACKUP.exists():
        raise PublishError("Refusing to overwrite prewrite backup")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({"schema": 1, "before": row, "before_sha": sha(old),
        "after_sha": sha(new), "coupon_count": coupons, "placeholder_count": placeholders,
        "ledger_fingerprint": ledger.fingerprint, "ledger_updated_at": ledger.updated_at,
        "wordpress_writes": 0}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "GYMWEAR_BACKUP_READY", "post_id": row["id"],
        "coupon_count": coupons, "placeholder_count": placeholders, "wordpress_writes": 0}))

def apply():
    backup = json.loads(BACKUP.read_text(encoding="utf-8"))
    row = read()
    old = row["content"]["raw"]
    new, coupons, placeholders = revise(old)
    if (backup.get("schema") != 1 or backup.get("wordpress_writes") != 0
            or backup.get("before") != row or backup.get("before_sha") != sha(old)
            or backup.get("after_sha") != sha(new) or backup.get("coupon_count") != coupons
            or backup.get("placeholder_count") != placeholders):
        raise PublishError("Source drift after immutable backup")
    if coupons:
        ledger = ledger_load()
        if ledger.fingerprint != backup["ledger_fingerprint"] or ledger.updated_at != backup["ledger_updated_at"]:
            raise PublishError("Coupon ledger changed")
        ledger_reserve(ledger, [row["id"]])
    try:
        wp_request(normalized_base(), "posts/" + str(row["id"]), payload={"content": new})
    except (PublishError, ValueError, OSError, TypeError):
        pass
    current = read()
    if current["content"]["raw"] != new or stable_metadata(current) != stable_metadata(row):
        raise PublishError("Exact source and metadata not verified; no retry")
    verify_public(URL, TITLE, current["content"].get("rendered") or new)
    result = probe(row["id"], SLUG)
    if result.get("state") != "PUBLIC_NO_COUPON_OBSERVED" or result.get("visible_mentions") != 0:
        raise PublishError("Public absence of obsolete coupon not verified; no retry")
    print(json.dumps({"state": "PUBLIC_LEGACY_GYMWEAR_VERIFIED", "post_id": row["id"],
        "url": URL, "posts_changed": 1, "post_attempts": 1, "public_site_modified": True,
        "shortcodes_removed": coupons, "placeholder_links_removed": placeholders, "new_posts": 0}))

if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Unknown scope")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, ValueError, OSError, KeyError, TypeError) as exc:
        print("XFIT_LEGACY_GYMWEAR_BLOCKED: " + type(exc).__name__ + ": " + str(exc) if isinstance(exc, PublishError) else "XFIT_LEGACY_GYMWEAR_BLOCKED: " + type(exc).__name__)
        raise SystemExit(2)
