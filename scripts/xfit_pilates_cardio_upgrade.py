#!/usr/bin/env python3
"""One original Pilates/cardio post SEO rewrite; fail-closed source backup.

Do not duplicate URL, rewrite any other post, delete, redirect or alter
featured media/author/categories. A WP REST source readback and public HTML
verification are mandatory. If public verification fails, restore original.
"""
import hashlib, json, re, sys
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen
from scripts.wp_publish import PublishError,normalized_base,wp_request,plain
from scripts.xfit_editorial_gate import check_document

SLUG="pilates-vs-kardio-co-je-lepsi-pro-hubnuti"
REVISION=Path("content/revisions/pilates-kardio-hubnuti.json")
BACKUP=Path("reports/backups/xfit-pilates-cardio-original.json")
SIGNATURE="Rozhodovací pomocník: co vám dává smysl dnes?"
def sha(s):return hashlib.sha256(s.encode("utf-8")).hexdigest()
def src(p):return (p.get("content") or {}).get("raw") or ""
def get_post(id=None):
    base=normalized_base()
    if id is None:
        q=urlencode({"slug":SLUG,"context":"edit","status":"any","per_page":5,
           "_fields":"id,slug,status,title,excerpt,content,link,modified,featured_media"})
        rows=wp_request(base,"posts?"+q)
        matched=[x for x in rows if x.get("slug")==SLUG]
        if len(matched)!=1:raise PublishError("No unique canonical original article")
        return matched[0]
    return wp_request(base,"posts/"+str(id)+"?context=edit&_fields=id,slug,status,title,excerpt,content,link,modified,featured_media")
def validate(p):
    if p.get("slug")!=SLUG or p.get("status")!="publish" or not isinstance(p.get("id"),int):
        raise PublishError("Post identity/status drift")
    u=urlsplit(p.get("link",""))
    if u.scheme!="https" or u.hostname not in ("xfit.cz","www.xfit.cz") or u.path.rstrip("/")!="/"+SLUG:
        raise PublishError("Canonical URL changed unexpectedly")
    return p
def editorial():
    d=json.loads(REVISION.read_text(encoding="utf-8"))
    if d.get("slug")!=SLUG or len(d.get("content",""))<8000 or SIGNATURE not in d["content"]:
        raise PublishError("Revision content/slug mismatch")
    check=check_document(d)
    if check["word_count"]<1100 or check["h2_count"]<6:
        raise PublishError("Pilates/cardio article needs substantial fact-based guide")
    if "https://www.ncbi.nlm.nih.gov/books/NBK566046/" not in d["content"] or "https://pmc.ncbi.nlm.nih.gov/articles/PMC13611139/" not in d["content"]:
        raise PublishError("Both health guideline and Pilates study evidence required")
    return d
def snapshot():
    d=editorial(); p=validate(get_post())
    if len(src(p))<400:raise PublishError("Source too short to safely identify")
    if sha(src(p))==sha(d["content"]):raise PublishError("Article already identical; no rewrite necessary")
    BACKUP.parent.mkdir(parents=True,exist_ok=True)
    if BACKUP.exists():raise PublishError("Backup already exists")
    BACKUP.write_text(json.dumps({"article":p,"sha256":sha(src(p)),
       "revision_sha256":sha(d["content"]),"action":"one in-place editorial rewrite"},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"stage":"pilates_cardio_backup_verified",
       "post_id":p["id"],"old_chars":len(src(p)),
       "old_sha256":sha(src(p)),"no_wp_writes":True}))
def check_live(p,d):
    link=p["link"]; u=urlsplit(link)
    if u.hostname not in ("www.xfit.cz","xfit.cz") or u.path.rstrip("/")!="/"+SLUG:
        raise PublishError("Public URL mismatch")
    req=Request(link,headers={"User-Agent":"XfitGrowthOS-PilatesEditor/1.0","Cache-Control":"no-cache"})
    with urlopen(req,timeout=28) as response:
        if response.status!=200:raise PublishError("Non 200 public article")
        body=response.read(2500000).decode("utf-8","replace")
    text=plain(body)
    if plain(d["title"]) not in text or plain(SIGNATURE) not in text:
        raise PublishError("New article missing from public render")
def revert(original):
    result=wp_request(normalized_base(),"posts/"+str(original["id"]),payload={
       "content":src(original),
       "title":(original.get("title") or {}).get("raw",""),
       "excerpt":(original.get("excerpt") or {}).get("raw","")})
    confirm=validate(get_post(original["id"]))
    if result.get("id")!=original["id"] or sha(src(confirm))!=sha(src(original)):
        raise PublishError("REST rollback did not recover original article")
    print(json.dumps({"stage":"pilates_cardio_rollback_verified","id":original["id"]}))
def deploy():
    if not BACKUP.exists():raise PublishError("Missing mandatory source backup")
    b=json.loads(BACKUP.read_text(encoding="utf-8"))
    original=validate(b.get("article") or {})
    d=editorial()
    if sha(src(original))!=b.get("sha256") or sha(d["content"])!=b.get("revision_sha256"):
        raise PublishError("Source/target revision hashes changed")
    current=validate(get_post(original["id"]))
    if sha(src(current))!=b["sha256"]:
        raise PublishError("Current live post drifted after backup")
    result=wp_request(normalized_base(),"posts/"+str(original["id"]),payload={
       "title":d["title"],"excerpt":d["excerpt"],"content":d["content"]})
    if result.get("id")!=original["id"] or result.get("status")!="publish":
        raise PublishError("WP write response doesn't match article")
    try:
        actual=validate(get_post(original["id"]))
        if sha(src(actual))!=sha(d["content"]):
            raise PublishError("Content readback doesn't match")
        check_live(actual,d)
    except (OSError,ValueError,PublishError) as exc:
        try:revert(original)
        except Exception as rollback_error:
            raise PublishError("Failed live check AND rollback: "+type(rollback_error).__name__) from exc
        raise PublishError("Failed live check, original restored: "+type(exc).__name__) from exc
    print(json.dumps({"stage":"live_verified","post_id":original["id"],
       "url":actual["link"],"preserved_permalink":True,
       "old_sha256":b["sha256"],"new_sha256":sha(d["content"])},ensure_ascii=False))
if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("snapshot","deploy"):raise PublishError("usage snapshot|deploy")
        (snapshot if sys.argv[1]=="snapshot" else deploy)()
    except (PublishError,KeyError,OSError,ValueError) as e:
        print("XFIT_PILATES_CARDIO_ERROR: "+str(e),file=sys.stderr)
        sys.exit(2)
