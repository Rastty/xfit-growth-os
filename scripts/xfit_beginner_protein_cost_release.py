"""One exact content-block improvement on the existing beginner guide 25458.

The reviewable editorial proposal is source-hash bound, but the *live* article
contains later improvements. Edit only the matching block in live WP raw HTML;
never replace its full body from the stale ready file.
"""

import hashlib
import html
import json
from pathlib import Path
import re
import sys
import time
import urllib.parse
import urllib.request

from scripts.wp_publish import MARKER, PublishError, normalized_base, wp_request
from scripts.xfit_editorial_gate import Inspector, check_document


POST_ID = 25458
SLUG = "xfit-os-doplnky-pro-zacatecniky"
URL = f"https://xfit.cz/{SLUG}/"
REVISION = Path("content/revisions/editor-beginner-protein-cost.json")
SOURCE = Path("content/ready/xfit-os-doplnky-pro-zacatecniky.json")
BACKUP = Path("reports/backups/xfit-beginner-protein-cost-25458.json")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def review():
    data = json.loads(REVISION.read_text(encoding="utf-8"))
    src_bytes = SOURCE.read_bytes()
    source = json.loads(src_bytes)
    old, new = data.get("original"), data.get("replacement")
    if (data.get("status") != "editorial_proposal_not_deployed"
            or data.get("issue") != 4 or data.get("operation") != "replace_exact_once"
            or data.get("wp_post_id") != POST_ID or data.get("slug") != SLUG
            or data.get("source_file") != str(SOURCE)
            or data.get("source_file_sha256") != hashlib.sha256(src_bytes).hexdigest()
            or data.get("source_content_sha256") != sha(source["content"])
            or source.get("slug") != SLUG
            or not isinstance(old, str) or not isinstance(new, str)
            or "Ukázkový výpočet ceny proteinu" not in old
            or "Jak porovnat cenu proteinu podle skutečné etikety" not in new
            or source["content"].count(old) != 1
            or new.count("<details>") != 1 or new.count("</details>") != 1
            or new.count("<summary>") != 1 or new.count("</summary>") != 1
            or "675 g bílkovin" not in new or "protein nemusíte kupovat" not in new
            or "včetně dopravy a povinných poplatků" not in new
            or len(new.encode("utf-8")) > 3000
            or any(term in new.lower() for term in ("<script", "<iframe", "<img", "<a "))):
        raise PublishError("Unexpected or unreviewed beginner protein cost proposal")
    preview = dict(source)
    preview["content"] = source["content"].replace(old, new, 1)
    if not check_document(preview)["passed"]:
        raise PublishError("Editorial standard failed for reviewed source")
    return data


def post():
    return wp_request(normalized_base(), f"posts/{POST_ID}?context=edit&_fields="
                      "id,slug,status,title,content,excerpt,link,modified_gmt,featured_media")


def inspect(record, proposal):
    if (not isinstance(record, dict) or type(record.get("id")) is not int
            or record["id"] != POST_ID or record.get("slug") != SLUG
            or record.get("status") != "publish" or record.get("link") != URL):
        raise PublishError("Unexpected WordPress article identity")
    body = (record.get("content") or {}).get("raw")
    title = (record.get("title") or {}).get("raw")
    excerpt = (record.get("excerpt") or {}).get("raw")
    if (not isinstance(body, str) or not 2500 < len(body.encode("utf-8")) < 450000
            or MARKER not in body or not isinstance(title, str) or len(title) < 15
            or not isinstance(excerpt, str)):
        raise PublishError("Unexpected or unowned WordPress content")
    old, new = proposal["original"], proposal["replacement"]
    if body.count(new) == 1 and body.count(old) == 0:
        return {"state": "already_applied", "before": body, "after": body,
                "hash": sha(body), "title_sha": sha(title),
                "excerpt_sha": sha(excerpt), "modified": record.get("modified_gmt"),
                "featured_media": record.get("featured_media")}
    if body.count(old) != 1 or body.count(new) != 0:
        raise PublishError("Original passage absent, duplicated or concurrently changed")
    changed = body.replace(old, new, 1)
    if changed.replace(new, old, 1) != body:
        raise PublishError("Exact reversible change could not be proven")
    before, after = Inspector(), Inspector()
    before.feed(body)
    after.feed(changed)
    if (before.headers != after.headers or before.links != after.links
            or before.images != after.images):
        raise PublishError("Unexpected heading, link or image mutation")
    if not check_document({"content": changed})["passed"]:
        raise PublishError("Live-page editorial gate failed")
    return {"state": "ready", "before": body, "after": changed,
            "hash": sha(body), "title_sha": sha(title),
            "excerpt_sha": sha(excerpt), "modified": record.get("modified_gmt"),
            "featured_media": record.get("featured_media")}


def snapshot():
    proposal = review()
    current = inspect(post(), proposal)
    if BACKUP.exists():
        raise PublishError("Existing mandatory backup must never be overwritten")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "purpose": "beginner_25458_protein_cost_exact_block",
        "post_id": POST_ID, "slug": SLUG, "original_raw": current["before"],
        "original_sha": current["hash"], "expected_sha": sha(current["after"]),
        "title_sha": current["title_sha"], "excerpt_sha": current["excerpt_sha"],
        "featured_media": current["featured_media"], "modified": current["modified"],
        "state": current["state"], "revision_sha": sha(REVISION.read_text(encoding="utf-8")),
        "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "BEGINNER_PROTEIN_COST_BACKUP_READY",
                      "post_id": POST_ID, "write_needed": current["state"] == "ready",
                      "remote_writes": 0}))


def public_verified(*, reader=None, attempts=7):
    def matches(raw):
        visible = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw)).split())
        return (visible.count("Jak porovnat cenu proteinu podle skutečné etikety") == 1
                and visible.count("Čistě početní příklad: 900 g prášku") == 1
                and "protein nemusíte kupovat" in visible
                and "včetně dopravy a povinných poplatků" in visible
                and "Ukázkový výpočet ceny proteinu (modelová čísla" not in visible)
    if reader is not None:
        page = reader(URL)
        return isinstance(page, str) and matches(page)
    for attempt in range(attempts):
        req = urllib.request.Request(URL, headers={"User-Agent": "XfitBeginnerCostRelease/1.0",
                                                    "Cache-Control": "no-cache", "Pragma": "no-cache"})
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                final = urllib.parse.urlsplit(response.geturl())
                if (response.status != 200 or final.scheme != "https"
                        or final.hostname not in ("xfit.cz", "www.xfit.cz")
                        or final.path != f"/{SLUG}/" or final.query or final.fragment
                        or final.username or final.password or final.port):
                    raise PublishError("Unexpected public article URL")
                raw = response.read(2_500_001)
                if len(raw) > 2_500_000:
                    raise PublishError("Public HTML too large")
                if matches(raw.decode("utf-8", errors="replace")):
                    return True
        except (OSError, UnicodeError) as error:
            if attempt == attempts - 1:
                raise PublishError("Public HTML readback unavailable") from error
        if attempt < attempts - 1:
            time.sleep(4)
    return False


def apply():
    if not BACKUP.is_file():
        raise PublishError("Missing mandatory backup")
    proposal = review()
    manifest = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (manifest.get("schema") != 1
            or manifest.get("purpose") != "beginner_25458_protein_cost_exact_block"
            or manifest.get("post_id") != POST_ID or manifest.get("slug") != SLUG
            or manifest.get("remote_writes") != 0
            or manifest.get("revision_sha") != sha(REVISION.read_text(encoding="utf-8"))):
        raise PublishError("Invalid immutable backup manifest")
    before = inspect(post(), proposal)
    if (before["before"] != manifest.get("original_raw")
            or before["hash"] != manifest.get("original_sha")
            or sha(before["after"]) != manifest.get("expected_sha")
            or before["modified"] != manifest.get("modified")
            or before["title_sha"] != manifest.get("title_sha")
            or before["excerpt_sha"] != manifest.get("excerpt_sha")
            or before["featured_media"] != manifest.get("featured_media")
            or before["state"] != manifest.get("state")):
        raise PublishError("Concurrent WordPress change since snapshot")
    if before["state"] == "already_applied":
        if not public_verified():
            raise PublishError("Previously applied edit not publicly visible")
        print(json.dumps({"state": "ALREADY_APPLIED_NO_WRITE", "post_id": POST_ID,
                          "post_attempts": 0, "url": URL}))
        return
    try:
        response = wp_request(normalized_base(), f"posts/{POST_ID}",
                              payload={"content": before["after"]})
        if (not isinstance(response, dict) or response.get("id") != POST_ID
                or response.get("status") != "publish"):
            raise PublishError("Uncertain WordPress POST")
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        pass  # Exactly one POST; timeouts can still be successful remote writes.
    try:
        latest = inspect(post(), proposal)
    except (PublishError, OSError, ValueError, KeyError, TypeError) as error:
        raise PublishError("Uncertain post state; no automatic retry") from error
    if (latest["hash"] != sha(before["after"])
            or latest["state"] != "already_applied"
            or latest["title_sha"] != before["title_sha"]
            or latest["excerpt_sha"] != before["excerpt_sha"]
            or latest["featured_media"] != before["featured_media"]):
        raise PublishError("Changed article failed content-only readback")
    if not public_verified():
        print(json.dumps({"state": "WP_UPDATED_PUBLIC_PENDING", "post_id": POST_ID,
                          "post_attempts": 1}))
        raise PublishError("Public content still stale; read-only reconfirmation needed")
    print(json.dumps({"state": "PUBLIC_VERIFIED", "post_id": POST_ID,
                      "url": URL, "posts_changed": 1, "post_attempts": 1,
                      "old_demo_price_removed": True, "real_label_method_published": True,
                      "links_preserved": True, "new_posts": 0, "plugins": 0,
                      "redirects": 0, "deletes": 0}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Usage: snapshot|apply")
        {"snapshot": snapshot, "apply": apply}[sys.argv[1]]()
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        print("XFIT_BEGINNER_PROTEIN_COST_ERROR: release stopped", file=sys.stderr)
        sys.exit(2)
