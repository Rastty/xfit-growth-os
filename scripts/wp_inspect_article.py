#!/usr/bin/env python3
"""Read-only audit of one existing public WordPress article. No mutations."""
import argparse
import json
import re
from scripts.wp_publish import normalized_base, wp_request

SAFE_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")

def inspect(slug):
    if not SAFE_SLUG.fullmatch(slug):
        raise ValueError("Unsafe slug")
    rows = wp_request(normalized_base(), 
        "posts?context=edit&slug=" + slug + "&per_page=10&_fields=id,slug,status,title,content,link")
    matches = [p for p in rows if p.get("slug")==slug]
    if len(matches)!=1:
        raise ValueError("Expected exactly one published article; found " + str(len(matches)))
    post=matches[0]
    raw=(post.get("content") or {}).get("raw","")
    title=(post.get("title") or {}).get("raw","")
    return {
        "id":post.get("id"),"slug":slug,"status":post.get("status"),
        "title":title,"url":post.get("link"),"raw_chars":len(raw),
        "heading_count":len(re.findall(r"<h[1-6]\b",raw,re.I)),
        "pilates_comparison_mentions":len(re.findall(r"jaký je rozdíl mezi klasickým pilates a power pilates",raw,re.I)),
        "contains_external_copyright_notice":"Pilates.cz" in raw,
        "diagnostic_only":True,"no_remote_writes":True
    }

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--slug",default="jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates")
    args=parser.parse_args()
    print(json.dumps(inspect(args.slug),ensure_ascii=False))
