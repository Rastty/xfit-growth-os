#!/usr/bin/env python3
"""Single high-value medical article revision, source-bound with rollback.

Preserves permalink, post ID, author/category/featured image and all unrelated
WordPress metadata. Does not use Xfit's generic xfit-os owned post publisher.
"""
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from scripts.wp_publish import normalized_base, wp_request, PublishError, plain
from scripts.xfit_editorial_gate import check_document

POST_ID = 6440
SLUG = "kreatin-a-jeho-vliv-na-ledviny-a-jatra"
EXPECTED_ORIGINAL_HASH = "4d50cf3e48ba8ec2b7f4c15312511c227ebfba790f7027fb45c7030de956a061"
CONTENT = Path("content/revisions/kreatin-ledviny-jatra-6440.json")
BACKUP = Path("reports/backups/creatine-kidney-6440-before.json")
SIGNATURE = "Rozhodující rozdíl:"
STALE_COUPON = "5NM2022"

def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def read_post():
    return wp_request(normalized_base(), "posts/"+str(POST_ID)+
        "?context=edit&_fields=id,slug,status,title,excerpt,content,link,featured_media,modified")

def raw(p):
    return (p.get("content") or {}).get("raw") or ""

def ensure_target(p):
    if (p.get("id") != POST_ID or p.get("slug") != SLUG or p.get("status") != "publish"):
        raise PublishError("Pinned legacy article no longer matches slug/status/id")
    url=p.get("link","")
    v=urlsplit(url)
    if v.scheme!="https" or v.hostname not in ("xfit.cz","www.xfit.cz") or v.path.rstrip("/")!="/"+SLUG:
        raise PublishError("Legacy article permalink changed; abort")

def read_revision():
    d=json.loads(CONTENT.read_text(encoding="utf-8"))
    if d.get("wp_post_id")!=POST_ID or d.get("slug")!=SLUG:
        raise PublishError("Wrong editorial revision target")
    if len(d.get("content",""))<8000 or SIGNATURE not in d["content"]:
        raise PublishError("Unfinished content revision")
    if STALE_COUPON in d["content"] or re.search(r"<\s*(?:script|iframe|form)\b|on\w+\s*=",d["content"],re.I):
        raise PublishError("Old coupon or unsafe active HTML")
    checks=check_document(d)
    if checks["word_count"] < 950 or checks["h2_count"] < 6:
        raise PublishError("Legacy medical content fails enhanced editorial threshold")
    if len(checks["source_hosts"])<2:
        raise PublishError("Insufficient independent source host diversity")
    return d

def snapshot():
    p=read_post()
    ensure_target(p)
    d=read_revision()
    current=raw(p)
    if sha(current)==sha(d["content"]):
        raise PublishError("Already revised — snapshot not necessary")
    if sha(current)!=EXPECTED_ORIGINAL_HASH:
        raise PublishError("Original live content changed since verified read-only capture")
    BACKUP.parent.mkdir(parents=True,exist_ok=True)
    if BACKUP.exists():
        raise PublishError("Backup already exists")
    BACKUP.write_text(json.dumps({
        "post":p, "sha256":sha(current), "target_sha256":sha(d["content"]),
        "purpose":"one existing medically relevant article; rollback original if needed",
        "public_writes":False},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"stage":"backup_created","id":POST_ID,"old_content_sha256":sha(current),
                      "new_content_sha256":sha(d["content"]),"public_writes":False}))

def public_check(url, title):
    v=urlsplit(url)
    if v.scheme!="https" or v.hostname not in ("xfit.cz","www.xfit.cz"):
        raise PublishError("Public verification rejected foreign site")
    req=Request(url,headers={"User-Agent":"XfitGrowthOS-LegacyRevision/1.0","Cache-Control":"no-cache"})
    with urlopen(req,timeout=30) as resp:
        if resp.status!=200:
            raise PublishError("Public article returned non-200")
        html=resp.read(2_000_000).decode("utf-8",errors="replace")
    cleaned=plain(html)
    if plain(title) not in cleaned or plain(SIGNATURE) not in cleaned:
        raise PublishError("Title or key scientific comparison missing from public article")
    if STALE_COUPON in html:
        raise PublishError("Stale 2022 promo still rendered on revised public article")

def rollback(original):
    result=wp_request(normalized_base(),"posts/"+str(POST_ID),payload={
        "title":(original.get("title") or {}).get("raw",""),
        "excerpt":(original.get("excerpt") or {}).get("raw",""),
        "content":raw(original)})
    if result.get("id")!=POST_ID:
        raise PublishError("Rollback write refused")
    confirm=read_post()
    if sha(raw(confirm))!=sha(raw(original)):
        raise PublishError("Rollback content mismatch")
    print(json.dumps({"stage":"rollback_verified","post_id":POST_ID}))

def deploy():
    if not BACKUP.exists():
        raise PublishError("Missing backed-up original source")
    snap=json.loads(BACKUP.read_text(encoding="utf-8"))
    old=snap.get("post") or {}
    ensure_target(old)
    d=read_revision()
    if sha(raw(old))!=snap.get("sha256") or sha(d["content"])!=snap.get("target_sha256"):
        raise PublishError("Source/target backup integrity failure")
    current=read_post()
    ensure_target(current)
    if sha(raw(current))!=EXPECTED_ORIGINAL_HASH:
        raise PublishError("Live content drift after snapshot; refusing overwrite")
    saved=wp_request(normalized_base(),"posts/"+str(POST_ID),payload={
        "title":d["title"],"excerpt":d["excerpt"],"content":d["content"]})
    if saved.get("id")!=POST_ID or saved.get("status")!="publish":
        raise PublishError("Unexpected WP write response")
    try:
        verify=read_post()
        ensure_target(verify)
        if sha(raw(verify))!=sha(d["content"]):
            raise PublishError("WordPress saved HTML differs from requested revision")
        public_check(verify["link"],d["title"])
    except (PublishError,OSError,ValueError) as exc:
        try:
            rollback(old)
        except Exception as rollback_error:
            raise PublishError("Live verification failed AND rollback failed: "+type(rollback_error).__name__) from exc
        raise PublishError("Live verification failed, original restored: "+type(exc).__name__) from exc
    print(json.dumps({"stage":"live_verified","post_id":POST_ID,"url":verify["link"],
                      "old_content_sha256":snap["sha256"],"new_content_sha256":sha(d["content"]),
                      "stale_coupon_removed":True},ensure_ascii=False))

if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("snapshot","deploy"):
            raise PublishError("Choose snapshot or deploy")
        (snapshot if sys.argv[1]=="snapshot" else deploy)()
    except (PublishError,OSError,ValueError,KeyError) as e:
        print("XFIT_LEGACY_REWRITE_ERROR: "+str(e),file=sys.stderr)
        sys.exit(2)
