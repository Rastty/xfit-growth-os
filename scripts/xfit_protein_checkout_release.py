"""One source-backed editorial copy replacement on existing XFIT protein guide.

Only reviewed JSON revision and WordPress post 25451. No new articles, no
plugins, no recurring write. Full raw WordPress HTML is backed up as an
artifact BEFORE a single possible write. Timeouts are reconciled, never
blindly retried. Source and public post are checked independently.
"""
import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from scripts.wp_publish import MARKER, PublishError, normalized_base, wp_request
from scripts.xfit_editorial_gate import Inspector, check_document

POST_ID = 25451
SLUG = "xfit-os-protein-guide"
URL = "https://xfit.cz/" + SLUG + "/"
REVISION = Path("content/revisions/editor-protein-checkout-cost.json")
SOURCE = Path("content/ready/xfit-os-protein-guide.json")
BACKUP = Path("reports/backups/xfit-protein-checkout-25451.json")
MAX_RAW_BYTES = 450000
PUBLIC_MARKERS = (
    "Když objednáváte jen jedno balení",
    "včetně dopravy a povinných poplatků",
    "nepřičítejte celou společnou dopravu každému balení",
    "nemusíte objednávat nic",
)


def digest(value):
    if isinstance(value, str):
        value=value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def reviewed_revision():
    rev=json.loads(REVISION.read_text(encoding="utf-8"))
    if (not isinstance(rev, dict)
            or rev.get("status")!="editorial_proposal_not_deployed"
            or rev.get("operation")!="replace_exact_once"
            or type(rev.get("wp_post_id")) is not int
            or rev["wp_post_id"]!=POST_ID or rev.get("slug")!=SLUG
            or rev.get("source_file")!=str(SOURCE)):
        raise PublishError("Unexpected reviewed proposal metadata")
    src_bytes=SOURCE.read_bytes()
    src=json.loads(src_bytes)
    before=rev.get("original")
    after=rev.get("replacement")
    if (digest(src_bytes)!=rev.get("source_file_sha256")
            or src.get("slug")!=SLUG or src.get("wp_post_id")!=POST_ID
            or not isinstance(src.get("content"),str)
            or digest(src["content"])!=rev.get("source_content_sha256")
            or not isinstance(before,str) or not isinstance(after,str)
            or not 100<len(before)<400 or not len(before)<len(after)<1200
            or before.count("<p>")!=1 or before.count("</p>")!=1
            or after.count("<p>")!=2 or after.count("</p>")!=2
            or not after.startswith(before+"\n<p>")
            or src["content"].count(before)!=1
            or all(x in src["content"] for x in PUBLIC_MARKERS)
            or any(x not in after for x in PUBLIC_MARKERS)
            or any(x in after.casefold() for x in (
                "<script", "<iframe", "<form", "<a ", "onclick=", "<img"))):
        raise PublishError("Source-bound replacement proposal failed checks")
    preview=dict(src)
    preview["content"]=src["content"].replace(before,after,1)
    check_document(preview)
    return rev


def read_post():
    return wp_request(normalized_base(), "posts/"+str(POST_ID)+
                      "?context=edit&_fields=id,slug,status,link,content,modified_gmt")


def prepare(post,rev):
    if (not isinstance(post,dict) or type(post.get("id")) is not int
            or post["id"]!=POST_ID or post.get("slug")!=SLUG
            or post.get("status")!="publish"):
        raise PublishError("Target WordPress post identity drift")
    url=urllib.parse.urlsplit(post.get("link") or "")
    if (url.scheme!="https" or url.hostname not in ("xfit.cz","www.xfit.cz")
            or url.port or url.username or url.password or url.query
            or url.fragment or url.path.rstrip("/")!="/"+SLUG):
        raise PublishError("Target WordPress permalink drift")
    raw=(post.get("content") or {}).get("raw")
    modified=post.get("modified_gmt")
    if (not isinstance(raw,str) or len(raw)<1000
            or len(raw.encode("utf-8"))>MAX_RAW_BYTES
            or MARKER not in raw or not isinstance(modified,str)
            or not modified):
        raise PublishError("Unexpected live owner-controlled source")
    old,new=rev["original"],rev["replacement"]
    if raw.count(new)==1 and raw.count(old)==1:
        return {"mode":"already_applied","before":raw,"after":raw,
                "modified":modified,"hash":digest(raw)}
    if raw.count(old)!=1 or raw.count(new)!=0:
        raise PublishError("Reviewed formula absent, repeated or conflicting")
    changed=raw.replace(old,new,1)
    if changed.replace(new,old,1)!=raw:
        raise PublishError("Replacement not precisely reversible")
    earlier,later=Inspector(),Inspector()
    earlier.feed(raw)
    later.feed(changed)
    if (earlier.headers!=later.headers or earlier.links!=later.links
            or earlier.images!=later.images):
        raise PublishError("Editorial revision changed unrelated links or headings")
    check_document({"content":changed})
    return {"mode":"update","before":raw,"after":changed,
            "modified":modified,"hash":digest(raw)}


def snapshot():
    rev=reviewed_revision()
    current=prepare(read_post(),rev)
    if BACKUP.exists():
        raise PublishError("Prewrite artifact already exists")
    BACKUP.parent.mkdir(parents=True,exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema":1,"post_id":POST_ID,"slug":SLUG,
        "revision_sha":digest(REVISION.read_bytes()),
        "original_raw":current["before"],
        "original_sha":current["hash"],
        "expected_sha":digest(current["after"]),
        "modified":current["modified"],"mode":current["mode"],
        "remote_writes":0,
    },ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"state":"PROTEIN_CHECKOUT_BACKUP_READY",
                      "post_id":POST_ID,"write_needed":current["mode"]=="update",
                      "remote_writes":0}))


def verify_public(*,reader=None):
    def matches(body):
        if not isinstance(body,str):
            return False
        visible=" ".join(html.unescape(re.sub(r"<[^>]*>"," ",body)).split())
        return all(s in visible for s in PUBLIC_MARKERS)
    if reader is not None:
        return matches(reader(URL))
    for attempt in range(3):
        req=urllib.request.Request(URL,headers={
            "User-Agent":"XFITProteinCheckoutReadback/1.0",
            "Cache-Control":"no-cache","Pragma":"no-cache"})
        try:
            with urllib.request.urlopen(req,timeout=25) as res:
                target=urllib.parse.urlsplit(res.geturl())
                if (res.status!=200 or target.scheme!="https"
                        or target.hostname not in ("xfit.cz","www.xfit.cz")
                        or target.port or target.username or target.password
                        or target.query or target.fragment
                        or target.path.rstrip("/")!="/"+SLUG):
                    raise PublishError("Public URL changed identity")
                body=res.read(2_000_001)
                if len(body)>2_000_000:
                    raise PublishError("Public readback exceeded bound")
                if matches(body.decode("utf-8",errors="replace")):
                    return True
        except (OSError,ValueError):
            if attempt==2:
                raise PublishError("Public source cannot be read")
        if attempt<2:
            time.sleep(3)
    return False


def apply():
    if not BACKUP.exists():
        raise PublishError("Missing mandatory full source backup")
    rev=reviewed_revision()
    recorded=json.loads(BACKUP.read_text(encoding="utf-8"))
    state=prepare(read_post(),rev)
    if (recorded.get("schema")!=1 or recorded.get("post_id")!=POST_ID
            or recorded.get("slug")!=SLUG
            or recorded.get("revision_sha")!=digest(REVISION.read_bytes())
            or recorded.get("remote_writes")!=0
            or recorded.get("original_raw")!=state["before"]
            or recorded.get("original_sha")!=state["hash"]
            or recorded.get("expected_sha")!=digest(state["after"])
            or recorded.get("modified")!=state["modified"]
            or recorded.get("mode")!=state["mode"]):
        raise PublishError("Source drifted since backup; refuse write")
    if state["mode"]=="already_applied":
        if not verify_public():
            raise PublishError("Existing revision not publicly verified")
        print(json.dumps({"state":"ALREADY_APPLIED_NO_WRITE",
                          "post_id":POST_ID,"url":URL,
                          "post_attempts":0,"public_site_modified":False}))
        return
    uncertain=False
    try:
        saved=wp_request(normalized_base(),"posts/"+str(POST_ID),
                         payload={"content":state["after"]})
        if (not isinstance(saved,dict) or saved.get("id")!=POST_ID
                or saved.get("status")!="publish"):
            uncertain=True
    except (PublishError,OSError,ValueError,KeyError,TypeError):
        uncertain=True
    # Reconcile after exactly one possible POST, even if HTTP returned error.
    try:
        p=read_post()
        if (p.get("id")!=POST_ID or p.get("slug")!=SLUG
                or p.get("status")!="publish"):
            raise PublishError("Unexpected response identity")
        raw=(p.get("content") or {}).get("raw")
        final_sha=digest(raw) if isinstance(raw,str) else None
    except (PublishError,OSError,ValueError,TypeError,AttributeError):
        print(json.dumps({"state":"BLOCKED_MANUAL_REVIEW",
                          "post_id":POST_ID,"readback_unknown":True,
                          "write_response_uncertain":uncertain}))
        raise PublishError("Post result uncertain; never retry blindly")
    if final_sha!=digest(state["after"]):
        print(json.dumps({"state":"UNRESOLVED_OR_DRIFTED","post_id":POST_ID,
                          "post_attempts":1,
                          "content_unchanged":final_sha==state["hash"]}))
        raise PublishError("Expected authenticated source not confirmed")
    if not verify_public():
        print(json.dumps({"state":"API_VERIFIED_PUBLIC_STALE",
                          "post_id":POST_ID,"post_attempts":1}))
        raise PublishError("Public revision not visible")
    print(json.dumps({"state":"PUBLIC_VERIFIED","post_id":POST_ID,
                      "url":URL,"posts_changed":1,"post_attempts":1,
                      "new_posts":0,"deletes":0,"redirects":0,
                      "public_site_modified":True}))


if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("snapshot","apply"):
            raise PublishError("Usage: snapshot|apply")
        (snapshot if sys.argv[1]=="snapshot" else apply)()
    except (PublishError,OSError,ValueError,TypeError,KeyError,AttributeError):
        print("XFIT_PROTEIN_CHECKOUT_RELEASE_ERROR",file=sys.stderr)
        raise SystemExit(2)
