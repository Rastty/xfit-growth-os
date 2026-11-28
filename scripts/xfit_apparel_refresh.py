"""One owned apparel comparison: refresh generated offers only, preserving editorial source."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from scripts.xfit_apparel_comparison import CATALOG, PREPARED, SLUG, URL, build_document
from scripts.xfit_catalog_retrieval import verified_catalog_fetch_time
from scripts.xfit_editorial_gate import check_document
from scripts.wp_publish import (
    MARKER, PublishError, normalized_base, wp_request, verify_public,
    editorial_links, classify_wp_write_failure,
)

POST_ID = 26219
TITLE = "Fitness oblečení: nabídky triček, mikin a legín podle velikosti"
SNAPSHOT = Path("reports/backups/xfit-apparel-before-refresh.json")
RETRIEVAL = re.compile(r'<p class="xfit-feed-retrieval"><small>[^<]*(?:<strong>[^<]+</strong>)[^<]*</small></p>')
END = "<h2>Co ověřit před objednáním</h2>"
NAV = re.compile(r'<nav aria-label="Výběr oblečení">.*?</nav>', re.S)
HEADING = re.compile(r'<h2 id="xfit-apparel-(?:shirt|hoodie|leggings|bra)">[^<]+</h2>')
MAX_BYTES = 400000
EDITORIAL = Path("content/revisions/apparel-fit-buying-guide.html")
EDITORIAL_MARKER = 'id="xfit-apparel-fit-guide-v1"'



def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def segments(body):
    if not isinstance(body,str) or not 1000 <= len(body.encode("utf-8")) <= MAX_BYTES or body.count(END)!=1:
        raise PublishError("Apparel block missing")
    dates, navs, headings = list(RETRIEVAL.finditer(body)), list(NAV.finditer(body)), list(HEADING.finditer(body))
    if len(dates)!=1 or len(navs)!=1 or not headings:
        raise PublishError("Ambiguous apparel boundaries")
    begin,end=headings[0].start(),body.index(END)
    if not dates[0].end()<navs[0].start()<navs[0].end()<begin<end or any(h.start()>=end for h in headings):
        raise PublishError("Invalid apparel block order")
    block=body[begin:end]
    count=block.count('class="xfit-product-card"')
    size_count = block.count('data-xfit-size="')
    if not 3<=count<=12 or not 0<=size_count<=52 or block.count('rel="sponsored nofollow noopener noreferrer"')!=count+size_count:
        raise PublishError("Unexpected apparel card or size-choice count")
    if size_count and block.count('<details id="xfit-size-picker-')!=len(headings):
        raise PublishError("Apparel size picker group count mismatch")
    if size_count and len(set(re.findall(r'data-xfit-size="([^"]+)"', block)))>13:
        raise PublishError("Unexpected apparel size tokens")
    return dates[0].span(),navs[0].span(),(begin,end)


def splice(old,new):
    if not old.startswith(MARKER+"\n") or old.count(MARKER)!=1:
        raise PublishError("Missing ownership")
    before, after = segments(old), segments(new)
    output=old
    for (a,b),(c,d) in reversed(list(zip(before,after))):
        output=output[:a]+new[c:d]+output[b:]
    # One reviewed editorial insertion, outside the daily generated region.
    # Preserve later human edits and do not replace an already published guide.
    if EDITORIAL_MARKER not in output:
        extra = EDITORIAL.read_text(encoding="utf-8").strip()
        if extra.count(EDITORIAL_MARKER) != 1 or output.count(END) != 1:
            raise PublishError("Reviewed editorial insertion invalid")
        # Insert after the existing ordering checklist, before methodology.
        anchor = "<h2>Jak vzniká srovnání</h2>"
        if output.count(anchor) != 1:
            raise PublishError("Reviewed editorial anchor drifted")
        output = output.replace(anchor, extra + "\n" + anchor, 1)
    elif output.count(EDITORIAL_MARKER) != 1:
        raise PublishError("Duplicate apparel editorial marker")
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
        raise PublishError("Pinned apparel post identity/title/source changed")
    if not raw.startswith(MARKER + "\n"):
        raise PublishError("Missing apparel post ownership")
    segments(raw)
    return raw, modified


def fresh_document():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    doc = json.loads(PREPARED.read_text(encoding="utf-8"))
    expected = build_document(catalog, os.environ["XFIT_AFFIL_DEFAULT_LINK"],
                              os.environ["XFIT_AFFIL_SAMPLE_PRODUCT_LINK"])
    if doc != expected or doc["slug"] != SLUG or doc["title"] != TITLE:
        raise PublishError("Prepared apparel source does not match the current feed")
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
    print(json.dumps({"state": "APPAREL_PREWRITE_BACKUP_READY", "post_id": POST_ID,
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
        raise PublishError("Apparel backup manifest invalid")
    new = splice(old, doc["content"])
    if sha(new) != saved.get("after_sha256"):
        raise PublishError("Apparel prepared replacement differs from backup")
    # Fail closed on any intervening source edit, including modification time.
    current, modified = read_source()
    if current != old or modified != saved.get("modified_gmt"):
        raise PublishError("Apparel source changed after immutable backup")
    if new == old:
        verify_public(URL, TITLE, old)
        print(json.dumps({"state": "unchanged_public_verified", "post_id": POST_ID,
                          "slug": SLUG, "url": URL, "public_site_modified": False,
                          "post_attempts": 0}))
        return
    try:
        answer = wp_request(normalized_base(), "posts/" + str(POST_ID), payload={"content": new})
        if answer.get("id") != POST_ID or answer.get("status") != "publish":
            raise PublishError("Unexpected apparel write response identity")
    except (PublishError, OSError, ValueError, KeyError) as exc:
        # Exactly one POST; diagnose by GET, never blindly retry.
        print(json.dumps({"state": "APPAREL_WRITE_DIAGNOSTIC", "post_id": POST_ID,
                          "classification": classify_wp_write_failure(exc), "post_attempts": 1}))
    try:
        actual, _ = read_source()
    except (PublishError, OSError, ValueError, KeyError):
        print(json.dumps({"state": "APPAREL_REFRESH_UNCERTAIN", "post_id": POST_ID, "post_attempts": 1}))
        raise PublishError("Authenticated apparel readback unavailable; do not retry")
    if actual != new or editorial_links(actual) != editorial_links(new):
        state = "APPAREL_REFRESH_UNCHANGED" if actual == old else "APPAREL_REFRESH_UNCERTAIN"
        print(json.dumps({"state": state, "post_id": POST_ID, "post_attempts": 1}))
        raise PublishError("Apparel source did not match intended content; no retry")
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
        print("XFIT_APPAREL_REFRESH_BLOCKED: " + type(exc).__name__)
        raise SystemExit(2)
