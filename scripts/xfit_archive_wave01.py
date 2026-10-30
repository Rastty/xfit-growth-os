#!/usr/bin/env python3
"""Xfit 90-day evidence-based zero-traffic off-topic archive wave.

Only statuses change publish -> draft (reversible). Never delete DB rows,
modify URLs, change SEO redirects or change post content.
Requires preflight backup artifact before any write.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

from scripts.wp_publish import PublishError, normalized_base, wp_request

CONFIG=Path("config/xfit-offtopic-wave01.json")
BACKUP=Path("reports/backups/xfit-offtopic-wave01-backup.json")
EXPECTED_NEW_STATUS="draft"
MAX_BATCH=40

def load():
    cfg=json.loads(CONFIG.read_text(encoding="utf-8"))
    items=cfg.get("candidates",[])
    if cfg.get("new_status")!=EXPECTED_NEW_STATUS or not 1<=len(items)<=MAX_BATCH:
        raise PublishError("Wave config contains unsupported action or target count")
    ids=[x.get("id") for x in items]
    if len(ids)!=len(set(ids)) or not all(type(i) is int and i>0 for i in ids):
        raise PublishError("Duplicate or invalid WordPress IDs")
    return cfg

def post_id(base,id):
    path="posts/"+str(id)+"?context=edit&_fields=id,slug,status,title,content,link,modified"
    for attempt in range(5):
        try:
            result=wp_request(base,path)
            # Prevent overwhelming WEDOS WordPress REST endpoint.
            time.sleep(0.45)
            return result
        except PublishError as exc:
            msg=str(exc)
            transient=("REST request failed (URLError)" in msg or
                       "REST request failed (TimeoutError)" in msg or
                       "HTTP 429" in msg or "HTTP 502" in msg or "HTTP 503" in msg or "HTTP 504" in msg)
            if not transient or attempt==4:
                raise
            time.sleep(min(2**attempt,8))
    raise PublishError("WP read unavailable after retries")

def content_sha(post):
    raw=(post.get("content") or {}).get("raw","")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def assert_expected(post,item,allow_draft=False):
    if post.get("id")!=item["id"] or post.get("slug")!=item["slug"]:
        raise PublishError("ID/slug drift: refusing mutation")
    if post.get("status") not in (("publish","draft") if allow_draft else ("publish",)):
        raise PublishError("Unexpected publication state")
    if "elektrokol" not in item["slug"]:
        raise PublishError("Not an unambiguous off-topic electric bicycle URL")
    if not post.get("link","").startswith("https://xfit.cz/"):
        raise PublishError("Unexpected permalink host")

def snapshot(cfg):
    base=normalized_base()
    entries=[]
    for item in cfg["candidates"]:
        p=post_id(base,item["id"])
        assert_expected(p,item)
        entries.append({
            "id":p["id"],"slug":p["slug"],"status":p["status"],
            "title":(p.get("title") or {}).get("raw",""),
            "modified":p.get("modified"),
            "content_sha256":content_sha(p),
            "link":p.get("link"),
            # Full content is deliberately stored locally in artifact for rollback.
            "content_raw":(p.get("content") or {}).get("raw","")
        })
    BACKUP.parent.mkdir(parents=True,exist_ok=True)
    if BACKUP.exists():
        raise PublishError("Rollback backup already exists; refusing overwrite")
    BACKUP.write_text(json.dumps({
        "wave_id":cfg["wave_id"],
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "action":"publish_to_draft_only",
        "posts":entries,
        "all_posts_preflighted":True},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"state":"backup_ready","count":len(entries),
                      "no_remote_writes":True},ensure_ascii=False))

def perform(cfg, mode):
    base=normalized_base()
    snap=json.loads(BACKUP.read_text(encoding="utf-8"))
    rows=snap.get("posts",[])
    if snap.get("wave_id")!=cfg["wave_id"] or len(rows)!=len(cfg["candidates"]):
        raise PublishError("Incorrect or incomplete mandatory rollback backup")
    by_id={x["id"]:x for x in rows}
    if len(by_id)!=len(rows):
        raise PublishError("Invalid backup")
    for item in cfg["candidates"]:
        p=post_id(base,item["id"])
        assert_expected(p,item,allow_draft=(mode=="restore"))
        old=by_id.get(p["id"],{})
        if old.get("slug")!=p["slug"]:
            raise PublishError("Backup does not match current article")
        if content_sha(p)!=old.get("content_sha256"):
            raise PublishError("Article changed after backup: abort")
    changed=[]
    goal="publish" if mode=="restore" else "draft"
    try:
        for item in cfg["candidates"]:
            existing=post_id(base,item["id"])
            if existing.get("status")==goal:continue
            # No content, slug or link changes. WordPress keeps versions intact.
            response=wp_request(base,"posts/"+str(item["id"]),payload={"status":goal})
            if response.get("id")!=item["id"] or response.get("status")!=goal:
                raise PublishError("Status update did not return expected post")
            check=post_id(base,item["id"])
            if check.get("status")!=goal or check.get("slug")!=item["slug"]:
                raise PublishError("Authenticated readback mismatch")
            changed.append(item["id"])
    except Exception as exc:
        if mode=="apply":
            # Roll back posts changed by this attempt, never cover up failure.
            rollback_failed=[]
            for id in reversed(changed):
                try:
                    wp_request(base,"posts/"+str(id),payload={"status":"publish"})
                except Exception:
                    rollback_failed.append(id)
            print(json.dumps({"state":"apply_failed","changed_count":len(changed),
                  "rollback_failures":rollback_failed},ensure_ascii=False),file=sys.stderr)
        raise PublishError("Incomplete status operation: "+type(exc).__name__) from None
    print(json.dumps({"state":"wave_"+mode+"_verified",
         "count":len(rows),"changed_count":len(changed),"target_status":goal,
         "no_destructive_deletes":True},ensure_ascii=False))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=["snapshot","apply","restore"])
    args=ap.parse_args()
    cfg=load()
    if args.mode=="snapshot":snapshot(cfg)
    else:perform(cfg,args.mode)

if __name__=="__main__":
    try:main()
    except (PublishError,OSError,ValueError,KeyError,TypeError) as exc:
        print("XFIT_ARCHIVE_ERROR: "+str(exc),file=sys.stderr)
        sys.exit(2)
