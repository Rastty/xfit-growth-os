#!/usr/bin/env python3
"""Bounded rollback-safe removal of obsolete 2022 su_button promos only."""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from scripts.wp_publish import PublishError,normalized_base,wp_request

MAX_COUNT=25
BACKUP=Path("reports/backups/xfit-expired-coupon-wave01.json")
PROMO=re.compile(r"\[su_button\b[^\]]{0,1200}\][^\[]*?5NM2022\[/su_button\]",re.I|re.S)
def sha(s):return hashlib.sha256(s.encode("utf-8")).hexdigest()
def stripped(raw):
    return PROMO.subn("",raw)
def get_post(id):
    return wp_request(normalized_base(),"posts/"+str(id)+"?context=edit&_fields=id,slug,status,content,link")
def validate(p,e=None):
    link=urlsplit(p.get("link") or "")
    if p.get("status")!="publish" or not isinstance(p.get("id"),int) or link.scheme!="https" or link.hostname not in ("xfit.cz","www.xfit.cz"):
        raise PublishError("Unexpected public post identity/host/status")
    if e and (p.get("id")!=e["id"] or p.get("slug")!=e["slug"]):
        raise PublishError("ID/slug changed")
    text=(p.get("content") or {}).get("raw") or ""
    if e and sha(text)!=e["before_sha256"]:
        raise PublishError("Original source hash changed")
    return text
def snapshot():
    query=urlencode({"search":"5NM2022","context":"edit","status":"publish",
                    "per_page":100,"_fields":"id,slug,status,content,link"})
    posts=wp_request(normalized_base(),"posts?"+query)
    if not isinstance(posts,list):raise PublishError("Unexpected WordPress search response")
    entries=[];ids=set()
    for p in posts:
        if p.get("id") in ids:continue
        ids.add(p.get("id"))
        source=validate(p)
        result,count=stripped(source)
        if count<1 or len(result)<500 or "5nm2022" in result.casefold():continue
        entries.append({"id":p["id"],"slug":p["slug"],"link":p["link"],
          "original_raw":source,"before_sha256":sha(source),"after_sha256":sha(result),
          "shortcodes_removed":count})
        if len(entries)>=MAX_COUNT:break
    BACKUP.parent.mkdir(parents=True,exist_ok=True)
    if BACKUP.exists():raise PublishError("Rollback backup already exists")
    BACKUP.write_text(json.dumps({"wave":"coupon01","entries":entries,
      "source":"authenticated preflight","remote_writes":0},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"state":"backup_ready","post_count":len(entries),
      "shortcodes_to_remove":sum(x["shortcodes_removed"] for x in entries),"no_remote_writes":True}))
def apply():
    if not BACKUP.exists():raise PublishError("Pre-write rollback backup missing")
    doc=json.loads(BACKUP.read_text(encoding="utf-8"))
    entries=doc["entries"]
    if doc.get("wave")!="coupon01" or len(entries)>MAX_COUNT or len({e["id"] for e in entries})!=len(entries):
        raise PublishError("Unexpected backup manifest")
    for e in entries:
        before=validate(get_post(e["id"]),e)
        after,count=stripped(before)
        if count!=e["shortcodes_removed"] or sha(after)!=e["after_sha256"]:
            raise PublishError("Preflight coupon replacement changed")
    changed=[]
    try:
        for e in entries:
            after,_=stripped(e["original_raw"])
            response=wp_request(normalized_base(),"posts/"+str(e["id"]),payload={"content":after})
            if response.get("id")!=e["id"] or response.get("status")!="publish":
                raise PublishError("Unexpected WP write status")
            check=get_post(e["id"])
            if check.get("slug")!=e["slug"] or sha((check.get("content") or {}).get("raw",""))!=e["after_sha256"]:
                raise PublishError("Post-update readback failed")
            changed.append(e)
    except Exception as error:
        rollback_failures=[]
        for e in reversed(changed):
            try:
                wp_request(normalized_base(),"posts/"+str(e["id"]),payload={"content":e["original_raw"]})
                if sha((get_post(e["id"]).get("content") or {}).get("raw",""))!=e["before_sha256"]:
                    rollback_failures.append(e["id"])
            except Exception:rollback_failures.append(e["id"])
        print(json.dumps({"state":"failed_rollback_attempted","changed":len(changed),
            "rollback_failures":rollback_failures}),file=sys.stderr)
        raise PublishError("Wave interrupted: "+type(error).__name__)
    print(json.dumps({"state":"coupon_wave_verified","posts_changed":len(changed),
      "shortcodes_removed":sum(e["shortcodes_removed"] for e in changed),
      "deletes":0,"redirects":0}))
if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("snapshot","apply"):raise PublishError("Select snapshot|apply")
        (snapshot if sys.argv[1]=="snapshot" else apply)()
    except (PublishError,ValueError,OSError,KeyError,TypeError) as e:
        print("XFIT_COUPON_ERROR: "+str(e),file=sys.stderr)
        sys.exit(2)
