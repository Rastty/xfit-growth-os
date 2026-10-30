#!/usr/bin/env python3
"""Read-only xfit duplicate-post source comparison with bounded WP retries.

Per-pair failures are reported without discarding evidence from healthy pairs.
This script never edits WordPress, creates redirects, or hides mismatches.
"""
import html
import json
import re
import time
from pathlib import Path
from scripts.wp_publish import normalized_base, wp_request, PublishError

PAIRS=[(5662,5661),(888,677),(13068,13003),(12370,12294)]
OUT=Path("reports/backups/xfit-duplicates-candidate-audit.json")
def text_body(p):
    source=(p.get("content") or {}).get("raw","")
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]*>"," ",source))).strip()
def grams(text):
    words=re.findall(r"\w+",text.casefold(),re.U)
    return set(zip(words,words[1:],words[2:],words[3:]))
def overlap(a,b):
    a4=grams(a);b4=grams(b)
    return round(len(a4&b4)/len(a4|b4),3) if a4 or b4 else 0
def one(post_id):
    path=f"posts/{post_id}?context=edit&_fields=id,slug,status,content,title,link"
    p=wp_request(normalized_base(),path)
    if p.get("id")!=post_id or p.get("status")!="publish":
        raise PublishError("Expected published post with pinned ID")
    return p
def inspect(a,b):
    source=one(a);target=one(b)
    source_slug=source["slug"];target_slug=target["slug"]
    source_title=(source.get("title") or {}).get("raw","").strip()
    target_title=(target.get("title") or {}).get("raw","").strip()
    if source_slug!=target_slug+"-2":
        raise PublishError("Slugs are not precise '-2' pair")
    if source_title.casefold()!=target_title.casefold():
        raise PublishError("Titles differ")
    source_text=text_body(source);target_text=text_body(target)
    ratio=overlap(source_text,target_text)
    return {
        "source_id":a,"target_id":b,"source_slug":source_slug,"target_slug":target_slug,
        "title":source_title,"source_chars":len(source_text),"target_chars":len(target_text),
        "text_overlap_4gram":ratio,"source_full":source,"target_full":target,
        "safe_candidate_for_301":ratio>=0.75 and len(source_text)>=350 and len(target_text)>=350,
        "reason":"read_only_candidate; analytics and links still require verification"
    }
def main():
    results=[];failures=[]
    for source_id,target_id in PAIRS:
        try:
            results.append(inspect(source_id,target_id))
        except (PublishError,OSError,ValueError,KeyError,TypeError) as ex:
            failures.append({"source_id":source_id,"target_id":target_id,
                             "error_type":type(ex).__name__,
                             "explanation":"WP unavailable or exact identity failed; no redirect allowed"})
        time.sleep(0.6)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({
        "mode":"read_only","verified_pairs":results,"failed_pairs":failures,
        "writes":0,"requires_analytics_before_301":True
    },ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"state":"duplicate_preflight_complete",
        "pairs":[{k:p[k] for k in ("source_id","target_id","source_slug","target_slug",
              "source_chars","target_chars","text_overlap_4gram","safe_candidate_for_301")}
              for p in results],
        "failed_pairs":failures,"remote_writes":0},ensure_ascii=False))
    if failures or not results:
        raise PublishError("One or more duplicate candidates unverified; no release permitted")
if __name__=="__main__":
    try:main()
    except PublishError as e:
        print("XFIT_DUPLICATE_AUDIT_INCOMPLETE: "+str(e))
        raise SystemExit(2)
