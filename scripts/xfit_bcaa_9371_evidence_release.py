"""One-source-locked evidence-led rescue of legacy BCAA WP #9371.

Legacy has three nested HTML documents, an in-body bogus example.com
canonical and unclear old marketing. Snapshot full authenticated raw source
and metadata BEFORE one possible content-only POST. Verify independent public
canonical, exact article body and mobile via workflow. Never retry a POST
on uncertain response.
"""
import hashlib
import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.wp_publish import (PublishError, normalized_base, wp_request,
                                verify_public, article_visible, editorial_links)
from scripts.xfit_canonical_preflight import canonical_links
from scripts.xfit_editorial_gate import check_document

POST_ID = 9371
SLUG = "jak-spravne-pouzivat-bcaa-pro-lepsi-regeneraci-a-svalovy-rust"
URL = "https://xfit.cz/" + SLUG + "/"
SOURCE = Path("content/revisions/bcaa-9371-evidence-20261122.html")
BACKUP = Path("reports/backups/xfit-bcaa-9371-original.json")
FIELDS = "id,slug,status,link,title,content,modified_gmt,featured_media"
MAX_BYTES = 350_000
NEW_MARKERS = (
    "rychlá odpověď:",
    "co jsou bcaa a v čem se liší od kompletního proteinu",
    "pomohou bcaa s regenerací a svalovou bolestí",
    "bcaa, eaa nebo protein: jak se rozhodnout",
    "kontrolní seznam",
    "odborné zdroje a rozsah tvrzení",
)
# Required links only, no invented products, prices or merchant claims.
SOURCES = (
    "https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC5477153/",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC12674588/",
)
GUIDES = (
    "https://xfit.cz/xfit-os-protein-guide/",
    "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",
    "https://xfit.cz/xfit-os-jak-vybrat-rostlinny-protein/",
)
DOCTYPE_RE = re.compile(r"<!\s*doctype\s+html\b", re.I)
BLOCK_TAG_RE = re.compile(r"<\s*(?:html|head|body|script|iframe|form|link)\b", re.I)


def sha(data):
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def plain(data):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", data)).split()).casefold()


def site_url(url):
    try:
        p=urlsplit(url)
        return (p.scheme=="https" and p.netloc in ("xfit.cz", "www.xfit.cz")
                and p.path.rstrip("/") == "/" + SLUG
                and not (p.query or p.fragment or p.username or p.password)
                and p.port is None)
    except (TypeError,ValueError):
        return False


def legacy(raw):
    if (not isinstance(raw,str) or len(raw.encode("utf-8")) < 5000
            or len(raw.encode("utf-8")) > MAX_BYTES):
        return False
    links=canonical_links(raw)
    if len(links)!=1 or len(DOCTYPE_RE.findall(raw))!=3:
        return False
    target=urlsplit(links[0])
    return (target.scheme=="https" and target.hostname in ("example.com","www.example.com")
            and target.port is None and not target.username and not target.password
            and "bcaa" in plain(raw) and "regener" in plain(raw))


def new_body(raw):
    if (not isinstance(raw,str) or len(raw.encode("utf-8")) < 7000
            or len(raw.encode("utf-8")) > 35000
            or len(re.findall(r"<h2\b",raw,re.I)) != 7
            or BLOCK_TAG_RE.search(raw)
            or re.search(r"\bon(?:click|load|error|submit)\s*=",raw,re.I)
            or "5nm2022" in raw.casefold()
            or "example.com" in raw.casefold()
            or canonical_links(raw)):
        return False
    p=plain(raw)
    return (all(m in p for m in NEW_MARKERS)
            and all(raw.count('href="'+u+'"')==1 for u in SOURCES+GUIDES)
            and not any(host in raw.casefold() for host in
                        ("namaximum.cz","us-supplements.to")))


def reviewed():
    raw=SOURCE.read_text(encoding="utf-8")
    if not new_body(raw):
        raise PublishError("Reviewed BCAA revision signature / links drifted")
    report=check_document({"content":raw})
    if report["word_count"] < 780 or report["h2_count"] < 7:
        raise PublishError("Insufficient BCAA editorial depth")
    return raw


def identity(post):
    if (not isinstance(post,dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("slug") != SLUG
            or post.get("status") != "publish" or post.get("link") != URL
            or not site_url(post.get("link"))):
        raise PublishError("Unexpected BCAA article identity or canonical URL")
    raw=(post.get("content") or {}).get("raw")
    title=(post.get("title") or {}).get("raw")
    modified=post.get("modified_gmt")
    media=post.get("featured_media")
    if (not isinstance(raw,str) or not 1000 <= len(raw.encode("utf-8")) <= MAX_BYTES
            or not isinstance(title,str)
            or not all(x in title.casefold() for x in ("bcaa","regener","sval"))
            or not isinstance(modified,str)
            or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d",modified)
            or type(media) is not int):
        raise PublishError("Missing current full authenticated BCAA source metadata")
    return raw,title,modified,media


def classify(post):
    raw,title,modified,media=identity(post)
    if new_body(raw):
        mode="already_applied"
    elif legacy(raw):
        mode="update"
    else:
        raise PublishError("Legacy BCAA source signature changed; zero WP writes")
    return {"mode":mode,"raw":raw,"title":title,"modified":modified,"media":media}


def remote():
    return wp_request(normalized_base(),f"posts/{POST_ID}?context=edit&_fields={FIELDS}")


def public_page():
    req=Request(URL,headers={"User-Agent":"XFITBCAA9371Review/1.0",
                             "Cache-Control":"no-cache","Pragma":"no-cache"},
                method="GET")
    with urlopen(req,timeout=25) as response:
        if response.status!=200 or not site_url(response.geturl()):
            raise PublishError("BCAA public URL redirected or not 200")
        data=response.read(2_000_001)
        if len(data)>2_000_000:
            raise PublishError("Oversized public article")
    return data.decode("utf-8",errors="replace")


def canonical_state(page):
    found=canonical_links(page)
    return {
        "total":len(found),
        "self":sum(site_url(u) for u in found),
        "example":sum(urlsplit(u).hostname in ("example.com","www.example.com")
                      for u in found),
    }


def old_public(page):
    return canonical_state(page)=={"total":2,"self":1,"example":1}


def new_public(page):
    return (canonical_state(page)=={"total":1,"self":1,"example":0}
            and not DOCTYPE_RE.search(page[page.find("<body"):].casefold())
            and "BCAA" in page)


def snapshot():
    after=reviewed()
    state=classify(remote())
    if state["mode"]=="update":
        page=public_page()
        if not old_public(page):
            raise PublishError("Public source no longer shows exact duplicate canonical")
    if BACKUP.exists():
        raise PublishError("Immutable BCAA rollback file already exists")
    BACKUP.parent.mkdir(parents=True,exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema":1,"post_id":POST_ID,"slug":SLUG,"url":URL,
        "mode":state["mode"],"original_raw":state["raw"],
        "original_title":state["title"],"original_media":state["media"],
        "original_modified_gmt":state["modified"],
        "original_sha256":sha(state["raw"]),
        "revised_sha256":sha(after),"remote_writes":0,
    },ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"state":"BCAA_9371_ROLLBACK_READY",
                      "post_id":POST_ID,"needs_write":state["mode"]=="update",
                      "remote_writes":0}))


def deploy():
    if not BACKUP.exists():
        raise PublishError("Missing uploaded full original BCAA rollback")
    after=reviewed()
    backup=json.loads(BACKUP.read_text(encoding="utf-8"))
    state=classify(remote())
    if (backup.get("schema")!=1 or backup.get("post_id")!=POST_ID
            or backup.get("slug")!=SLUG or backup.get("url")!=URL
            or backup.get("mode")!=state["mode"]
            or backup.get("original_raw")!=state["raw"]
            or backup.get("original_sha256")!=sha(state["raw"])
            or backup.get("original_title")!=state["title"]
            or backup.get("original_modified_gmt")!=state["modified"]
            or backup.get("original_media")!=state["media"]
            or backup.get("revised_sha256")!=sha(after)
            or backup.get("remote_writes")!=0):
        raise PublishError("Concurrent BCAA source drift since rollback")
    if state["mode"]=="already_applied":
        verify_public(URL,state["title"],after)
        if not new_public(public_page()):
            raise PublishError("Already-applied BCAA canonical unverified")
        print(json.dumps({"state":"ALREADY_VERIFIED_NO_WRITE",
                          "post_id":POST_ID,"post_attempts":0,"posts_changed":0}))
        return
    if not old_public(public_page()):
        raise PublishError("Prewrite public canonical no longer matches")
    uncertain=False
    try:
        resp=wp_request(normalized_base(),f"posts/{POST_ID}",
                        payload={"content":after})
        uncertain=(not isinstance(resp,dict)
                   or resp.get("id")!=POST_ID or resp.get("status")!="publish")
    except (PublishError,OSError,ValueError,TypeError):
        uncertain=True
    try:
        result=classify(remote())
    except (PublishError,OSError,ValueError,TypeError) as exc:
        print(json.dumps({"state":"UNKNOWN_NO_RETRY","post_id":POST_ID,
                          "post_attempts":1}))
        raise PublishError("Cannot authenticated-readback BCAA; no retry") from exc
    a,_=article_visible(result["raw"])
    b,_=article_visible(after)
    if (result["mode"]!="already_applied" or a!=b
            or editorial_links(result["raw"])!=editorial_links(after)
            or result["title"]!=state["title"]
            or result["media"]!=state["media"]):
        raise PublishError("BCAA postwrite raw/links metadata mismatch; no retry")
    verify_public(URL,state["title"],after)
    for n in range(3):
        try:
            if new_public(public_page()):
                print(json.dumps({
                    "state":"PUBLIC_CANONICAL_AND_CONTENT_VERIFIED",
                    "post_id":POST_ID,"url":URL,"post_attempts":1,
                    "posts_changed":1,"nested_documents_removed":3,
                    "wrong_canonicals_removed":1,"public_canonicals":1,
                    "new_posts":0,"redirects":0,"deletes":0,
                    "write_response_uncertain":uncertain,
                    "public_site_modified":True,
                }))
                return
        except (PublishError,OSError,ValueError):
            pass
        if n<2:time.sleep(3)
    raise PublishError("BCAA public canonical unreadable/stale; never retry POST")


if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("snapshot","deploy"):
            raise PublishError("Usage: snapshot|deploy")
        (snapshot if sys.argv[1]=="snapshot" else deploy)()
    except (PublishError,OSError,ValueError,TypeError,KeyError) as exc:
        print("XFIT_BCAA_9371_RELEASE_ERROR: "+type(exc).__name__,file=sys.stderr)
        raise SystemExit(2)
