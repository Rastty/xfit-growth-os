#!/usr/bin/env python3
"""Full PUBLIC WordPress archive inventory for Xfit cleanup decisions.

Read-only. Bulk deletion, redirects and noindex are intentionally separate
from discovery. Output is a reproducible report with concrete action candidates.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
import re
import sys
from pathlib import Path
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE="https://xfit.cz/wp-json/wp/v2/posts"
TAG=re.compile(r"<[^>]*>")
SPACE=re.compile(r"\s+")
LINKS=re.compile(r'<a\b[^>]*\bhref=["\x27]([^"\x27]+)',re.I)
TITLE_NOISE=re.compile(r"\b(aktualizace|přehled|kompletní průvodce|průvodce)\b", re.I)
SPAM=re.compile(r"(casino|kasino|gambling|slots|betting|viagra|porn|poker|loan|levitra)",re.I)
OUT_OF_FOCUS=("elektrokolo","koloběžka","skútr","casino","kasino","sázková kancelář","online automaty","půjčky")
PRIMARY_TOPIC=("fitness","cvičení","trénink","sval","protein","kreatin","posilov","výživ","výživa","jídlo","hubnutí","pilates","jóga","sport","regenerac","zdrav","vitam","pohyb")
FIELDS="id,modified,link,slug,title,content,excerpt,categories,date"
MAX_PAGE=250
MAX_SIZE=100

def clean(text):
    return SPACE.sub(" ",html.unescape(TAG.sub(" ",text or ""))).strip()

def fetch(page,size):
    url=BASE+"?"+urlencode({"page":page,"per_page":size,"_fields":FIELDS})
    req=Request(url,headers={"User-Agent":"XfitGrowthOS-ArchiveInventory/1.0"})
    for attempt in range(3):
        try:
            with urlopen(req,timeout=35) as response:
                return json.load(response),int(response.headers.get("X-WP-TotalPages","0"))
        except HTTPError as e:
            if e.code==400 and page>1: return [],0
            if e.code not in (429,500,502,503,504) or attempt==2:raise
        except (URLError,TimeoutError):
            if attempt==2:raise
        time.sleep(1.5*(attempt+1))
    raise RuntimeError("WP API gave no response")

def classify(post):
    title=clean((post.get("title") or {}).get("rendered") or "")
    body_html=(post.get("content") or {}).get("rendered") or ""
    body=clean(body_html)
    lower=(title+" "+(post.get("slug") or "")).casefold()
    external=Counter()
    for link in LINKS.findall(body_html):
        p=urlsplit(html.unescape(link))
        if p.scheme in ("http","https") and p.hostname and p.hostname.lower() not in ("xfit.cz","www.xfit.cz"):
            external[p.hostname.lower()]+=1
    return {
      "id":post.get("id"),"slug":post.get("slug") or "",
      "url":post.get("link") or "", "title":title,
      "modified":post.get("modified"),"body_chars":len(body),
      "paragraphs":len(re.findall(r"<p\b",body_html,re.I)),
      "headings":len(re.findall(r"<h[1-6]\b",body_html,re.I)),
      "internal_link_count":sum(1 for href in LINKS.findall(body_html) if "xfit.cz/" in href),
      "external_hosts":dict(external.most_common(10)),
      "body_hash":hashlib.sha256(SPACE.sub(" ",body.lower()).encode("utf-8")).hexdigest() if body else "",
      "title_normalized":TITLE_NOISE.sub("",title).lower().strip(),
      "suspect_thin":len(body)<350,
      "suspect_offtopic":any(x in lower for x in OUT_OF_FOCUS)
                and not any(x in lower for x in PRIMARY_TOPIC),
      "suspect_spam":bool(SPAM.search(lower)) or any(SPAM.search(host) for host in external)
    }

def inventory(posts):
    # WP REST page-based pagination can repeat a post when the archive receives
    # new entries mid-scan. A post must never create a "duplicate article"
    # finding against itself (observed on prior audit for post 5300).
    seen={}
    repeated_ids=[]
    for post in posts:
        id=post.get("id")
        if not isinstance(id,int) or id<=0:
            continue
        if id in seen:
            repeated_ids.append(id)
            continue
        seen[id]=post
    rows=[classify(p) for p in seen.values()]
    titles=defaultdict(list)
    bodies=defaultdict(list)
    for p in rows:
        if p["title_normalized"]:titles[p["title_normalized"]].append(p)
        if p["body_hash"]:bodies[p["body_hash"]].append(p)
    duplicates=[
        {"normalized_title":title,"posts":[{"id":p["id"],"url":p["url"],"body_chars":p["body_chars"]} for p in group]}
        for title,group in titles.items() if len(group)>1
    ]
    identical=[
        {"posts":[{"id":p["id"],"url":p["url"],"title":p["title"]} for p in group]}
        for group in bodies.values() if len(group)>1
    ]
    flagged=sorted(
      (p for p in rows if p["suspect_thin"] or p["suspect_offtopic"] or p["suspect_spam"]),
      key=lambda p:(not p["suspect_spam"],not p["suspect_thin"],not p["suspect_offtopic"],p["body_chars"]))
    return {
      "scanned":len(rows),
      "raw_page_records":len(posts),
      "repeated_pagination_post_count":len(repeated_ids),
      "repeated_pagination_post_ids_sample":sorted(set(repeated_ids))[:30],
      "duplicate_title_groups":len(duplicates),
      "exact_body_duplicate_groups":len(identical),
      "thin_count":sum(p["suspect_thin"] for p in rows),
      "suspected_out_of_focus_count":sum(p["suspect_offtopic"] for p in rows),
      "suspected_spam_count":sum(p["suspect_spam"] for p in rows),
      "duplicate_titles":duplicates[:250],
      "exact_body_duplicates":identical[:250],
      "flagged_candidates": flagged[:500],
      "warning":"CANDIDATES ONLY: prior to trash/noindex/redirect examine 90-day GA4 landing sessions, GSC clicks/impressions, existing internal links and user intent; store rollback backup. No site mutations from this job."
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pages",type=int,default=100)
    ap.add_argument("--size",type=int,default=100)
    ap.add_argument("--output",default="reports/xfit-archive-full-audit.json")
    args=ap.parse_args()
    if not 1<=args.pages<=MAX_PAGE or not 1<=args.size<=MAX_SIZE:
        ap.error("Invalid page or size parameter")
    rows=[]; failed=None; declared_total=None; pages_fetched=0; saw_short_page=False
    for page in range(1,args.pages+1):
        try:
            batch,count=fetch(page,args.size)
        except (HTTPError,URLError,TimeoutError,ValueError) as exc:
            failed={"page":page,"error_type":type(exc).__name__}
            break
        pages_fetched += 1
        rows.extend(batch)
        if count:declared_total=count
        if len(batch)<args.size:
            saw_short_page=True
            break
        if count and page>=count:break
    report=inventory(rows)
    report.update({
       "generated_at_utc":datetime.now(timezone.utc).isoformat(),
       "scope":"public WordPress posts, sequential REST pagination",
       "max_requested_pages":args.pages,
       "declared_total_pages":declared_total,
       "interrupted_at":failed,
       "pages_fetched":pages_fetched,
       "complete":failed is None and (
           saw_short_page or
           (declared_total is not None and declared_total>0 and pages_fetched>=declared_total)
       ),
       "pagination_warning":"Page-based WordPress enumeration is not an atomic snapshot. Changes during scan can shift records; repeated IDs are deduplicated and a complete page count does not prove zero missed IDs.",
       "mutated_wordpress":False
    })
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("scanned","repeated_pagination_post_count","complete","duplicate_title_groups","exact_body_duplicate_groups","thin_count","suspected_out_of_focus_count","suspected_spam_count","declared_total_pages","interrupted_at","mutated_wordpress")},ensure_ascii=False))
    return 2 if not rows or failed else 0

if __name__=="__main__":
    sys.exit(main())
