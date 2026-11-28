"""One owned nut-butter comparison: refresh generated offers only, preserving editorial source."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from scripts.xfit_nut_butter_comparison import CATALOG, PREPARED, SLUG, URL, build_document as base_document
from scripts.xfit_select import folded
from scripts.xfit_catalog_retrieval import verified_catalog_fetch_time
from scripts.xfit_editorial_gate import check_document
from scripts.wp_publish import (
    MARKER, PublishError, normalized_base, wp_request, verify_public,
    editorial_links, classify_wp_write_failure,
)

POST_ID = 26178
TITLE = "Arašídová a ořechová másla: srovnání cen za 100 g"
SNAPSHOT = Path("reports/backups/xfit-nut-butter-before-refresh.json")
RETRIEVAL = re.compile(r'<p class="xfit-feed-retrieval"><small>[^<]*(?:<strong>[^<]+</strong>)[^<]*</small></p>')
END = "<h2>Co zkontrolovat na etiketě před nákupem</h2>"
NAV = re.compile(r'<nav aria-label="Druhy másel">.*?</nav>', re.S)
HEADING = re.compile(r'<h2 id="xfit-butter-(?:peanut|almond|cashew)">[^<]+</h2>')
MAX_BYTES = 400000


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def segments(body):
    if not isinstance(body,str) or not 1000 <= len(body.encode("utf-8")) <= MAX_BYTES or body.count(END)!=1:
        raise PublishError("Nut butter block missing")
    dates, navs, headings = list(RETRIEVAL.finditer(body)), list(NAV.finditer(body)), list(HEADING.finditer(body))
    if len(dates)!=1 or len(navs)!=1 or not headings:
        raise PublishError("Ambiguous nut butter boundaries")
    begin,end=headings[0].start(),body.index(END)
    if not dates[0].end()<navs[0].start()<navs[0].end()<begin<end or any(h.start()>=end for h in headings):
        raise PublishError("Invalid nut butter block order")
    block=body[begin:end]
    count=block.count('class="xfit-product-card"')
    if not 2<=count<=9 or block.count('rel="sponsored nofollow noopener noreferrer"')!=count:
        raise PublishError("Unexpected nut butter card count")
    return dates[0].span(),navs[0].span(),(begin,end)


def splice(old,new):
    if not old.startswith(MARKER+"\n") or old.count(MARKER)!=1:
        raise PublishError("Missing ownership")
    before, after = segments(old), segments(new)
    output=old
    for (a,b),(c,d) in reversed(list(zip(before,after))):
        output=output[:a]+new[c:d]+output[b:]
    check_document({"content":output},commercial=True)
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
        raise PublishError("Pinned nut-butter post identity/title/source changed")
    if not raw.startswith(MARKER + "\n"):
        raise PublishError("Missing nut-butter post ownership")
    segments(raw)
    return raw, modified


# Dry powdered products are not comparable gram-for-gram with ready-to-eat
# nut butter. Reject them before ranking or family deduplication.
_POWDER = re.compile(r"\b(?:v prasku|praskov\w*|powder(?:ed)?|powders)\b")
_FORM_NOTE = ('<p><strong>Hotové máslo vs. prášek:</strong> '
              'Arašídové a ořechové máslo v prášku do tohoto cenového srovnání '
              'nezahrnujeme. Po přidání vody se změní hmotnost připravené porce; '
              'cena za 100 g suchého prášku není přímo srovnatelná s cenou '
              'za 100 g hotového másla. Řiďte se návodem na konkrétní etiketě.</p>')


def build_document(catalog, base, sample):
    items = catalog.get("products")
    if not isinstance(items, list):
        raise PublishError("Unexpected nut butter catalog inventory")
    # Keep the original raw inventory limit before filtering.
    from scripts.xfit_select import MAX_FULL_CATALOG_SCAN
    if len(items) > MAX_FULL_CATALOG_SCAN:
        raise PublishError("Unexpected nut butter catalog inventory")
    # Do not let filtering hide contradictory catalog identities.
    rejected = [row for row in items
                if _POWDER.search(folded(row.get("title") or ""))]
    conflict_keys = {(key, str(row[key])) for row in rejected
                     for key in ("id", "ean", "source_url") if row.get(key)}
    filtered = dict(catalog, products=[
        row for row in items
        if not _POWDER.search(folded(row.get("title") or ""))
        and not any((key, str(row[key])) in conflict_keys
                    for key in ("id", "ean", "source_url") if row.get(key))
    ])
    doc = base_document(filtered, base, sample)
    # This paragraph belongs inside the generated region so that the daily
    # refresh preserves it without replacing the surrounding editorial copy.
    first = HEADING.search(doc["content"])
    if first is None:
        raise PublishError("No comparable nut butter offer section")
    end = first.end()
    doc["content"] = doc["content"][:end] + "\n" + _FORM_NOTE + doc["content"][end:]
    check_document(doc, commercial=True)
    return doc


def prepare():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    doc = build_document(catalog, os.environ["XFIT_AFFIL_DEFAULT_LINK"],
                         os.environ["XFIT_AFFIL_SAMPLE_PRODUCT_LINK"])
    PREPARED.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "NUT_BUTTER_COMPARABLE_FORMS_PREPARED",
                      "cards": check_document(doc)["product_cards"],
                      "wordpress_writes": 0}))


def fresh_document():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    doc = json.loads(PREPARED.read_text(encoding="utf-8"))
    expected = build_document(catalog, os.environ["XFIT_AFFIL_DEFAULT_LINK"],
                              os.environ["XFIT_AFFIL_SAMPLE_PRODUCT_LINK"])
    if doc != expected or doc["slug"] != SLUG or doc["title"] != TITLE:
        raise PublishError("Prepared nut-butter source does not match the current feed")
    return doc


def snapshot():
    doc = fresh_document()
    old, modified = read_source()
    new = splice(old, doc["content"])
    if SNAPSHOT.exists():
        raise PublishError("Refusing to overwrite prewrite backup")
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps({
        "schema": 1, "post_id": POST_ID, "slug": SLUG, "url": URL,
        "original_raw": old, "modified_gmt": modified,
        "before_sha256": sha(old), "after_sha256": sha(new),
        "prepared_body_sha256": sha(doc["content"]), "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "NUT_BUTTER_PREWRITE_BACKUP_READY", "post_id": POST_ID,
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
        raise PublishError("Nut butter backup manifest invalid")
    new = splice(old, doc["content"])
    if sha(new) != saved.get("after_sha256"):
        raise PublishError("Nut butter prepared replacement differs from backup")
    # Fail closed on any intervening source edit, including modification time.
    current, modified = read_source()
    if current != old or modified != saved.get("modified_gmt"):
        raise PublishError("Nut butter source changed after immutable backup")
    if new == old:
        verify_public(URL, TITLE, old)
        print(json.dumps({"state": "unchanged_public_verified", "post_id": POST_ID,
                          "slug": SLUG, "url": URL, "public_site_modified": False,
                          "post_attempts": 0}))
        return
    try:
        answer = wp_request(normalized_base(), "posts/" + str(POST_ID), payload={"content": new})
        if answer.get("id") != POST_ID or answer.get("status") != "publish":
            raise PublishError("Unexpected nut-butter write response identity")
    except (PublishError, OSError, ValueError, KeyError) as exc:
        # Exactly one POST; diagnose by GET, never blindly retry.
        print(json.dumps({"state": "NUT_BUTTER_WRITE_DIAGNOSTIC", "post_id": POST_ID,
                          "classification": classify_wp_write_failure(exc), "post_attempts": 1}))
    try:
        actual, _ = read_source()
    except (PublishError, OSError, ValueError, KeyError):
        print(json.dumps({"state": "NUT_BUTTER_REFRESH_UNCERTAIN", "post_id": POST_ID, "post_attempts": 1}))
        raise PublishError("Authenticated nut-butter readback unavailable; do not retry")
    if actual != new or editorial_links(actual) != editorial_links(new):
        state = "NUT_BUTTER_REFRESH_UNCHANGED" if actual == old else "NUT_BUTTER_REFRESH_UNCERTAIN"
        print(json.dumps({"state": state, "post_id": POST_ID, "post_attempts": 1}))
        raise PublishError("Nut butter source did not match intended content; no retry")
    verify_public(URL, TITLE, new)
    print(json.dumps({"state": "live_verified", "post_id": POST_ID, "slug": SLUG,
                      "url": URL, "public_site_modified": True, "posts_changed": 1,
                      "post_attempts": 1, "new_posts": 0, "deletes": 0, "redirects": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=("prepare", "snapshot", "apply"))
    args = parser.parse_args()
    try:
        {"prepare": prepare, "snapshot": snapshot, "apply": apply}[args.step]()
    except (PublishError, ValueError, OSError, KeyError, TypeError) as exc:
        print("XFIT_NUT_BUTTER_REFRESH_BLOCKED: " + type(exc).__name__)
        raise SystemExit(2)
