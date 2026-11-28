"""One owned drinkware comparison: refresh generated offers only, preserving editorial source."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from scripts.xfit_drinkware_comparison import CATALOG, PREPARED, SLUG, URL, build_document
from scripts.xfit_catalog_retrieval import verified_catalog_fetch_time
from scripts.xfit_editorial_gate import check_document
from scripts.wp_publish import (
    MARKER, PublishError, normalized_base, wp_request, verify_public,
    editorial_links, classify_wp_write_failure,
)

POST_ID = 26176
TITLE = "Šejkry a sportovní lahve: aktuální nabídky a praktický výběr"
SNAPSHOT = Path("reports/backups/xfit-drinkware-before-refresh.json")
RETRIEVAL = re.compile(r'<p class="xfit-feed-retrieval"><small>[^<]*(?:<strong>[^<]+</strong>)[^<]*</small></p>')
START = '<h2 id="xfit-drink-shaker">Šejkry na míchání – aktuální nabídky</h2>'
END = "<h2>Kolik zaplatíte při samostatné objednávce</h2>"
OFFER_HEADING = '<h2 id="xfit-drink-bottle">'
MAX_BYTES = 400000
GUIDE = Path("content/revisions/drinkware-buying-guide.html")
GUIDE_MARKER = 'id="xfit-drinkware-buying-guide-v1"'
GUIDE_ANCHOR = "<h2>Metodika výběru</h2>"



def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def segments(body):
    if (not isinstance(body, str) or not 1000 <= len(body.encode("utf-8")) <= MAX_BYTES
            or body.count(START) != 1 or body.count(END) != 1 or body.count(OFFER_HEADING) != 1):
        raise PublishError("Drinkware generated block boundaries missing or ambiguous")
    dates = list(RETRIEVAL.finditer(body))
    begin, end = body.index(START), body.index(END)
    if len(dates) != 1 or dates[0].end() >= begin or not begin < body.index(OFFER_HEADING) < end:
        raise PublishError("Drinkware retrieval date or offer block order invalid")
    block = body[begin:end]
    if not 3 <= block.count('class="xfit-product-card"') <= 8 or not 3 <= block.count('rel="sponsored nofollow noopener noreferrer"') <= 8:
        raise PublishError("Unexpected drinkware generated card structure")
    return dates[0].span(), (begin, end)


def splice(old, new):
    if not old.startswith(MARKER + "\n") or old.count(MARKER) != 1:
        raise PublishError("Missing original drinkware ownership marker")
    (d1, d2), (b1, b2) = segments(old)
    (n1, n2), (m1, m2) = segments(new)
    # Copy only the catalog retrieval date and contiguous commercial section.
    # All other existing editorial HTML survives byte-for-byte, even if a human
    # or a separate authorized editor has added a paragraph since launch.
    output = old[:d1] + new[n1:n2] + old[d2:b1] + new[m1:m2] + old[b2:]
    if GUIDE_MARKER not in output:
        guide = GUIDE.read_text(encoding="utf-8").strip()
        if guide.count(GUIDE_MARKER) != 1 or output.count(GUIDE_ANCHOR) != 1:
            raise PublishError("Reviewed drinkware buying guide insertion unavailable")
        output = output.replace(GUIDE_ANCHOR, guide + "\n" + GUIDE_ANCHOR, 1)
    elif output.count(GUIDE_MARKER) != 1:
        raise PublishError("Duplicate drinkware buying guide marker")
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
        raise PublishError("Pinned drinkware post identity/title/source changed")
    if not raw.startswith(MARKER + "\n"):
        raise PublishError("Missing drinkware post ownership")
    segments(raw)
    return raw, modified


def fresh_document():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    doc = json.loads(PREPARED.read_text(encoding="utf-8"))
    expected = build_document(catalog, os.environ["XFIT_AFFIL_DEFAULT_LINK"],
                              os.environ["XFIT_AFFIL_SAMPLE_PRODUCT_LINK"])
    if doc != expected or doc["slug"] != SLUG or doc["title"] != TITLE:
        raise PublishError("Prepared drinkware source does not match the current feed")
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
    print(json.dumps({"state": "DRINKWARE_PREWRITE_BACKUP_READY", "post_id": POST_ID,
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
        raise PublishError("Drinkware backup manifest invalid")
    new = splice(old, doc["content"])
    if sha(new) != saved.get("after_sha256"):
        raise PublishError("Drinkware prepared replacement differs from backup")
    # Fail closed on any intervening source edit, including modification time.
    current, modified = read_source()
    if current != old or modified != saved.get("modified_gmt"):
        raise PublishError("Drinkware source changed after immutable backup")
    if new == old:
        verify_public(URL, TITLE, old)
        print(json.dumps({"state": "unchanged_public_verified", "post_id": POST_ID,
                          "slug": SLUG, "url": URL, "public_site_modified": False,
                          "post_attempts": 0}))
        return
    try:
        answer = wp_request(normalized_base(), "posts/" + str(POST_ID), payload={"content": new})
        if answer.get("id") != POST_ID or answer.get("status") != "publish":
            raise PublishError("Unexpected drinkware write response identity")
    except (PublishError, OSError, ValueError, KeyError) as exc:
        # Exactly one POST; diagnose by GET, never blindly retry.
        print(json.dumps({"state": "DRINKWARE_WRITE_DIAGNOSTIC", "post_id": POST_ID,
                          "classification": classify_wp_write_failure(exc), "post_attempts": 1}))
    try:
        actual, _ = read_source()
    except (PublishError, OSError, ValueError, KeyError):
        print(json.dumps({"state": "DRINKWARE_REFRESH_UNCERTAIN", "post_id": POST_ID, "post_attempts": 1}))
        raise PublishError("Authenticated drinkware readback unavailable; do not retry")
    if actual != new or editorial_links(actual) != editorial_links(new):
        state = "DRINKWARE_REFRESH_UNCHANGED" if actual == old else "DRINKWARE_REFRESH_UNCERTAIN"
        print(json.dumps({"state": state, "post_id": POST_ID, "post_attempts": 1}))
        raise PublishError("Drinkware source did not match intended content; no retry")
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
        print("XFIT_DRINKWARE_REFRESH_BLOCKED: " + type(exc).__name__)
        raise SystemExit(2)
