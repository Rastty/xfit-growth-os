"""One explicitly reviewed public legacy article, exact canonical slug and content anchors."""
import hashlib
import json
from pathlib import Path
import sys
import re
from urllib.parse import urlencode
from scripts.wp_publish import normalized_base, wp_request, PublishError, verify_public, article_visible, normalize_visible, editorial_links
from scripts.xfit_legacy_mat_release import stable_metadata
from scripts.xfit_coupon_cleanup import QUARANTINE_IDS
from scripts.xfit_editorial_gate import check_document
from scripts.xfit_nut_butter_refresh import read_source, URL as TARGET, TITLE as TARGET_TITLE

SLUG="ctyri-zaludne-zdroje-cukru"
URL="https://xfit.cz/"+SLUG+"/"
TITLE="Čtyři záludné zdroje cukru, kde byste je nečekali"
BACKUP=Path("reports/backups/xfit-sugar-label-original.json")
FIELDS="id,slug,status,link,title,content,excerpt,categories,tags,sticky,featured_media,modified_gmt"
BODY=Path("content/revisions/sugar-label-four-sources.html")

def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def expected():
    body=BODY.read_text(encoding="utf-8")
    check_document({"content":body},commercial=False)
    if editorial_links(body).count(TARGET)!=1:
        raise PublishError("Incorrect reviewed target")
    return body

def read():
    rows=wp_request(normalized_base(),"posts?"+urlencode({"slug":SLUG,"context":"edit","status":"publish","per_page":2,"_fields":FIELDS}))
    if not isinstance(rows,list) or len(rows)!=1:
        raise PublishError("Expected one exact published source")
    row=rows[0]
    if (type(row.get("id")) is not int or row["id"]<=0 or row["id"] in QUARANTINE_IDS or
        row.get("slug")!=SLUG or row.get("link")!=URL or row.get("status")!="publish" or
        normalize_visible(row.get("title",{}).get("raw",""))!=normalize_visible(TITLE) or
        not isinstance(row.get("modified_gmt"),str)):
        raise PublishError("Reviewed source identity drift")
    stable_metadata(row)
    return row

def reviewed(row,new):
    raw=row["content"]["raw"]
    if raw==new:
        return
    if not isinstance(raw,str) or not 1500<=len(raw.encode())<=400000 or row["modified_gmt"]>="2026-11-20":
        raise PublishError("Source changed since reviewed older article")
    text,_=article_visible(raw)
    anchors=("Vanilkový jogurt","Mandlové mléko","Ořechová másla","Rajčatová omáčka","Cukr pod jinými názvy",
             "Je již notoricky známé","13 procent","2015")
    if any(normalize_visible(a) not in text for a in anchors) or "5NM2022" in raw or "xfit-sugar-label-revision" in raw:
        raise PublishError("Publicly reviewed old content not matched")
    # Do not silently drop old inline media or navigation. This rewrite is
    # authorized only for the observed text-only article.
    if editorial_links(raw) or re.search(r"<\s*(?:img|iframe|video|audio|figure|script|form)\b|\[(?:gallery|caption|embed)\b",raw,re.I):
        raise PublishError("Original has unreviewed media or links")
    verify_public(URL,TITLE,row["content"].get("rendered") or raw)

def snapshot():
    raw,_=read_source()
    verify_public(TARGET,TARGET_TITLE,raw)
    row=read()
    new=expected()
    reviewed(row,new)
    if BACKUP.exists():
        raise PublishError("Backup already exists")
    BACKUP.parent.mkdir(parents=True,exist_ok=True)
    BACKUP.write_text(json.dumps({"schema":1,"before":row,"before_sha":sha(row["content"]["raw"]),"after_sha":sha(new),"wordpress_writes":0},ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"state":"SUGAR_LABEL_BACKUP_READY","post_id":row["id"],"change_required":row["content"]["raw"]!=new,"wordpress_writes":0}))

def apply():
    backup=json.loads(BACKUP.read_text(encoding="utf-8"))
    row=read()
    new=expected()
    old=row["content"]["raw"]
    if backup.get("schema")!=1 or backup.get("wordpress_writes")!=0 or backup.get("before")!=row or backup.get("before_sha")!=sha(old) or backup.get("after_sha")!=sha(new):
        raise PublishError("Source drift after immutable backup")
    reviewed(row,new)
    if old!=new:
        try:
            wp_request(normalized_base(),"posts/"+str(row["id"]),payload={"content":new})
        except (PublishError,ValueError,OSError,TypeError):
            pass
        after=read()
        if after["content"]["raw"]!=new or stable_metadata(after)!=stable_metadata(row):
            raise PublishError("Exact source/metadata readback not proven; never retry")
    verify_public(URL,TITLE,new)
    print(json.dumps({"state":"PUBLIC_SUGAR_LABEL_REVISION_VERIFIED","post_id":row["id"],"url":URL,"post_attempts":int(old!=new),"posts_changed":int(old!=new),"public_site_modified":old!=new,"new_posts":0}))

if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in {"snapshot","apply"}:
            raise PublishError("Unknown scope")
        (snapshot if sys.argv[1]=="snapshot" else apply)()
    except (PublishError,ValueError,OSError,KeyError,TypeError) as exc:
        print("SUGAR_LABEL_RELEASE_BLOCKED: "+type(exc).__name__)
        raise SystemExit(2)
