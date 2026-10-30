#!/usr/bin/env python3
"""Inspect and snapshot a single existing creatine/kidney article read-only."""
import json
import hashlib
from pathlib import Path
from scripts.wp_publish import normalized_base, wp_request, PublishError

SLUG="kreatin-a-jeho-vliv-na-ledviny-a-jatra"
PATH=Path("reports/backups/xfit-creatine-kidney-original.json")

def capture():
    base=normalized_base()
    posts=wp_request(base,"posts?context=edit&slug="+SLUG+
        "&per_page=10&_fields=id,slug,status,title,excerpt,content,link,modified")
    matches=[p for p in posts if p.get("slug")==SLUG]
    if len(matches)!=1 or matches[0].get("status")!="publish":
        raise PublishError("Expected exactly one published article")
    p=matches[0]
    content=(p.get("content") or {}).get("raw") or ""
    if len(content)<700:
        raise PublishError("Original article too short or missing content")
    digest=hashlib.sha256(content.encode()).hexdigest()
    PATH.parent.mkdir(parents=True,exist_ok=True)
    if PATH.exists():
        raise PublishError("Backup already exists; cannot overwrite")
    PATH.write_text(json.dumps({"post":p,"sha256":digest,
        "source":"authenticated_wp_rest_no_write"},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"state":"original_captured","post_id":p["id"],"slug":p["slug"],
        "title":(p.get("title") or {}).get("raw"),"body_chars":len(content),
        "content_sha256":digest,"public_url":p["link"],"no_remote_writes":True},ensure_ascii=False))
if __name__=="__main__":capture()
