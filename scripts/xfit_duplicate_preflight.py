#!/usr/bin/env python3
"""Read-only protected duplicate-post candidate source evidence."""
import hashlib,html,json,re
from pathlib import Path
from scripts.wp_publish import normalized_base,wp_request,PublishError
PAIRS=[(5662,5661),(888,677),(13068,13003),(12370,12294)]
def text_body(p):
    s=(p.get("content") or {}).get("raw","")
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]*>"," ",s))).strip()
def grams(text):
    w=re.findall(r"\w+",text.casefold(),re.U)
    return set(zip(w,w[1:],w[2:],w[3:]))
def overlap(a,b):
    x=grams(a);y=grams(b)
    return round(len(x&y)/len(x|y),3) if x|y else 0
def one(id):
    p=wp_request(normalized_base(),"posts/"+str(id)+"?context=edit&_fields=id,slug,status,content,title,link")
    if p.get("id")!=id or p.get("status")!="publish":
        raise PublishError("Unpublished or changed source/target")
    return p
def main():
    report=[]
    for oldid,newid in PAIRS:
        old=one(oldid);new=one(newid)
        if old["slug"]!=new["slug"]+"-2":
            raise PublishError("Source and canonical slugs are not exact '-2' duplication")
        oldtitle=(old.get("title") or {}).get("raw","")
        newtitle=(new.get("title") or {}).get("raw","")
        if oldtitle.strip().casefold()!=newtitle.strip().casefold():
            raise PublishError("Source and canonical titles diverge")
        b1=text_body(old);b2=text_body(new)
        report.append({"source_id":oldid,"target_id":newid,
           "source_slug":old["slug"],"target_slug":new["slug"],
           "title":oldtitle,
           "source_chars":len(b1),"target_chars":len(b2),
           "text_overlap_4gram":overlap(b1,b2),
           "source_readable_head":b1[:550],"target_readable_head":b2[:550],
           "source_full":old,"target_full":new})
    Path("reports/backups").mkdir(parents=True,exist_ok=True)
    Path("reports/backups/xfit-duplicates-candidate-audit.json").write_text(
       json.dumps({"verified_pairs":report,"mode":"read_only","no_wp_changes":True},
       ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"state":"duplicate_evidence_ready","pairs":[
        {k:r[k] for k in ("source_id","target_id","source_slug","title",
                          "source_chars","target_chars","text_overlap_4gram")}
        for r in report],"remote_writes":0},ensure_ascii=False))
if __name__=="__main__":main()
