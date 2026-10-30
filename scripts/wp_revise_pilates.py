#!/usr/bin/env python3
"""Guarded one-time WordPress in-place content revision, with mandatory backup.

Run from repo root:
  python -m scripts.wp_revise_pilates snapshot
  python -m scripts.wp_revise_pilates deploy

Only updates WP post 3660 after snapshot/unchanged-content validation.
No deletes, no new posts, no permalink changes.
"""
import hashlib
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from scripts.wp_publish import PublishError, normalized_base, wp_request

ARTICLE_ID = 3660
SLUG = "jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates"
BACKUP = Path("reports/backups/pilates-before-revision-3660.json")
TARGET = Path("content/revisions/pilates-difference.json")
SIGNATURE = "Jak vybrat lekci podle zkušeností a cíle"


def read_post():
    base = normalized_base()
    return wp_request(base, "posts/" + str(ARTICLE_ID) +
         "?context=edit&_fields=id,slug,status,title,excerpt,content,link")


def original_body(post):
    c = post.get("content") or {}
    return c.get("raw") or ""


def checksum(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def assert_target(post):
    if post.get("id") != ARTICLE_ID or post.get("slug") != SLUG or post.get("status") != "publish":
        raise PublishError("Expected published canonical article 3660 is not present")


def snapshot():
    post = read_post()
    assert_target(post)
    body = original_body(post)
    if len(body) < 4000:
        raise PublishError("Existing article body unexpectedly short; cancelling")
    if body.lower().count("jaký je rozdíl mezi klasickým pilates a power pilates") < 3:
        raise PublishError("Expected duplicated original content not detected")
    if "Pilates.cz" not in body:
        raise PublishError("External attribution marker changed; manual review required")
    if BACKUP.exists():
        raise PublishError("Backup file already exists; refusing overwrite")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "post": post, "original_raw_sha256": checksum(body),
        "scope": "one existing article; before any write"}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(json.dumps({"stage": "backup_created", "post_id": ARTICLE_ID,
                      "content_sha256": checksum(body), "raw_chars": len(body),
                      "no_remote_writes": True}))


def verified_public(url, key_phrase):
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or p.hostname not in ("xfit.cz", "www.xfit.cz") or p.path.rstrip("/") != "/" + SLUG:
        raise PublishError("Unexpected public article URL; refusing verification")
    req = urllib.request.Request(url, headers={"User-Agent": "XfitGrowthOS/0.2", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            page = response.read(2_000_000).decode("utf-8", errors="replace")
    except (OSError, ValueError) as ex:
        raise PublishError("Public article fetch failed: " + type(ex).__name__) from ex
    normalized = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page))).lower()
    if key_phrase.lower() not in normalized:
        raise PublishError("Public article still missing updated text; cache or deployment verification failed")


def deploy():
    if not BACKUP.exists():
        raise PublishError("Mandatory pre-update backup is missing")
    snap = json.loads(BACKUP.read_text(encoding="utf-8"))
    old = snap.get("post") or {}
    assert_target(old)
    cur = read_post()
    assert_target(cur)
    if checksum(original_body(cur)) != snap.get("original_raw_sha256"):
        raise PublishError("Article changed after backup; cancelling write")
    if checksum(original_body(old)) != snap.get("original_raw_sha256"):
        raise PublishError("Backup checksum mismatch")
    doc = json.loads(TARGET.read_text(encoding="utf-8"))
    if doc.get("wp_post_id") != ARTICLE_ID or doc.get("slug") != SLUG:
        raise PublishError("Target revision does not match protected post")
    content = doc.get("content") or ""
    if len(content) < 4000 or SIGNATURE not in content:
        raise PublishError("Revised article is incomplete")
    if re.search(r"<\s*(?:script|iframe|form)\b|on\w+\s*=", content, re.I):
        raise PublishError("Unsafe dynamic HTML in revision")
    if "Pilates.cz" in content:
        raise PublishError("External copyright marker still in revised article")
    base=normalized_base()
    saved=wp_request(base, "posts/" + str(ARTICLE_ID), payload={
        "content": content, "excerpt": doc.get("excerpt", "")})
    if saved.get("id") != ARTICLE_ID or saved.get("slug") != SLUG or saved.get("status") != "publish":
        raise PublishError("WP content update response did not match protected article")
    check=read_post()
    assert_target(check)
    if SIGNATURE not in original_body(check) or "Pilates.cz" in original_body(check):
        raise PublishError("WP read-back does not contain new article")
    print(json.dumps({"stage": "wp_write_verified", "post_id": ARTICLE_ID, "url": check.get("link")}, ensure_ascii=False))
    verified_public(check["link"], SIGNATURE)
    print(json.dumps({"stage": "live_verified", "post_id": ARTICLE_ID, "url": check.get("link")}, ensure_ascii=False))


if __name__=="__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "deploy"):
            raise PublishError("usage: python -m scripts.wp_revise_pilates snapshot|deploy")
        if sys.argv[1] == "snapshot":
            snapshot()
        else:
            deploy()
    except (PublishError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print("XFIT_REVISION_ERROR: " + str(exc), file=sys.stderr)
        sys.exit(2)
