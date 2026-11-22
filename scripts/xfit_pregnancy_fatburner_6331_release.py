"""Single existing WP #6331 pregnancy/lactation risk correction.

Never create a commercial page; same URL/title/media. Exact source and
public preflight -> complete raw rollback uploaded before one content-only
POST -> authenticated and independent public verification. Unknown POST
outcomes never cause automatic retry.
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

POST_ID=6331
SLUG="spalovace-tuku-v-tehotenstvi-a-pri-kojeni-co-je-bezpecne-a-ucinne"
URL="https://xfit.cz/"+SLUG+"/"
SOURCE=Path("content/revisions/pregnancy-breastfeeding-fatburner-6331-evidence.html")
BACKUP=Path("reports/backups/xfit-pregnancy-fatburner-6331-original.json")
FIELDS="id,slug,status,link,title,content,modified_gmt,featured_media"
MAX_BYTES=350_000
SOURCE_LINKS=(
    "https://www.nice.org.uk/guidance/NG247/chapter/recommendations",
    "https://www.rcog.org.uk/for-the-public/browse-our-patient-information/healthy-eating-and-vitamin-supplements-in-pregnancy/",
    "https://www.nhs.uk/baby/breastfeeding-and-bottle-feeding/breastfeeding-and-lifestyle/medicines/",
    "https://www.nhs.uk/baby/breastfeeding-and-bottle-feeding/breastfeeding-and-lifestyle/diet/",
    "https://ods.od.nih.gov/factsheets/WeightLoss-HealthProfessional/",
)
NEW_MARKERS=(
    "krátká odpověď:",
    "proč se během těhotenství nedoporučuje samostatná redukční kúra",
    "a co přípravky na hubnutí při kojení",
    "co dělat, pokud jste už spalovač užila",
    "jaká pomoc dává větší smysl než nákup",
    "nezávislé zdroje a hranice článku",
    "nekoupit nic",
)
OLD_PROMO="5nm2022"


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def visible(s):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", s)).split()).casefold()


def exact_url(value):
    try:
        p=urlsplit(value)
        return (p.scheme=="https" and p.netloc in ("xfit.cz","www.xfit.cz")
                and p.path.rstrip("/")=="/"+SLUG
                and not (p.query or p.fragment or p.username or p.password)
                and p.port is None)
    except (ValueError,TypeError):
        return False


def canonical_self(page):
    links=canonical_links(page)
    return len(links)==1 and exact_url(links[0])


def revised(raw):
    if (not isinstance(raw,str) or not 6200 <= len(raw.encode("utf-8")) <= 30000
            or len(re.findall(r"<h2\b",raw,re.I))!=6
            or re.search(r"<\s*(?:html|head|body|script|iframe|form|link)\b",raw,re.I)
            or re.search(r"\bon(?:load|error|click|submit)\s*=",raw,re.I)
            or OLD_PROMO in raw.casefold()
            or canonical_links(raw)):
        return False
    p=visible(raw)
    return (all(marker in p for marker in NEW_MARKERS)
            and all(raw.count('href="'+link+'"')==1 for link in SOURCE_LINKS)
            and "namaximum.cz" not in raw.casefold()
            and "chytapust" not in raw.casefold()
            and "us-supplements.to" not in raw.casefold())


def reviewed():
    raw=SOURCE.read_text(encoding="utf-8")
    if not revised(raw):
        raise PublishError("Pregnancy safety revision source or links drift")
    report=check_document({"content":raw})
    if report["word_count"]<750 or report["h2_count"]<6:
        raise PublishError("Insufficient independent prenatal safety editorial")
    return raw


def identity(post):
    if (not isinstance(post,dict) or type(post.get("id")) is not int
            or post["id"]!=POST_ID or post.get("slug")!=SLUG
            or post.get("status")!="publish" or post.get("link")!=URL
            or not exact_url(post.get("link"))):
        raise PublishError("Wrong published pregnancy article")
    title=(post.get("title") or {}).get("raw")
    body=(post.get("content") or {}).get("raw")
    modified=post.get("modified_gmt")
    media=post.get("featured_media")
    if (not isinstance(title,str)
            or not all(x in title.casefold() for x in ("spalova","těhoten","kojen"))
            or not isinstance(body,str) or not 2500<=len(body.encode("utf-8"))<=MAX_BYTES
            or not isinstance(modified,str)
            or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d",modified)
            or type(media) is not int):
        raise PublishError("Missing exact current pregnancy post source/metadata")
    return body,title,modified,media


def classify(post):
    body,title,modified,media=identity(post)
    if revised(body):
        mode="already_applied"
    elif (OLD_PROMO in body.casefold()
          and "těhoten" in visible(body)
          and "kojen" in visible(body)
          and "spalova" in visible(body)):
        mode="update"
    else:
        raise PublishError("Unexpected source: old promo/safety topic changed")
    return {"mode":mode,"raw":body,"title":title,
            "modified":modified,"media":media}


def remote():
    return wp_request(normalized_base(),
                      f"posts/{POST_ID}?context=edit&_fields={FIELDS}")


def public_page():
    req=Request(URL,headers={"User-Agent":"XFITPregnancy6331Safety/1.0",
                             "Cache-Control":"no-cache","Pragma":"no-cache"},
                method="GET")
    with urlopen(req,timeout=25) as response:
        if response.status!=200 or not exact_url(response.geturl()):
            raise PublishError("Unsafe redirect or missing pregnancy public URL")
        result=response.read(2_000_001)
        if len(result)>2_000_000:
            raise PublishError("Oversized public pregnancy page")
    return result.decode("utf-8",errors="replace")


def public_before(page):
    txt=visible(page)
    return (canonical_self(page) and "spalova" in txt
            and "těhoten" in txt and "kojen" in txt)


def public_after(page):
    txt=visible(page)
    return (canonical_self(page) and
            all(x in txt for x in ("krátká odpověď","nekupujte žádný spalovač",
                                   "nezávislé zdroje a hranice článku")))


def snapshot():
    after=reviewed()
    state=classify(remote())
    if state["mode"]=="update" and not public_before(public_page()):
        raise PublishError("Public pregnancy article source unverified")
    if BACKUP.exists():
        raise PublishError("Immutable pregnancy original snapshot already exists")
    BACKUP.parent.mkdir(parents=True,exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema":1,"post_id":POST_ID,"slug":SLUG,"url":URL,
        "mode":state["mode"],"original_raw":state["raw"],
        "original_title":state["title"],"original_media":state["media"],
        "original_modified_gmt":state["modified"],
        "original_sha256":sha(state["raw"]),"revised_sha256":sha(after),
        "remote_writes":0,
    },ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"state":"PREGNANCY_6331_BACKUP_READY",
                      "post_id":POST_ID,"needs_write":state["mode"]=="update",
                      "remote_writes":0}))


def deploy():
    if not BACKUP.exists():
        raise PublishError("Missing uploaded original pregnancy WP content")
    revised_body=reviewed()
    backup=json.loads(BACKUP.read_text(encoding="utf-8"))
    state=classify(remote())
    if (backup.get("schema")!=1 or backup.get("post_id")!=POST_ID
            or backup.get("slug")!=SLUG or backup.get("url")!=URL
            or backup.get("mode")!=state["mode"]
            or backup.get("original_raw")!=state["raw"]
            or backup.get("original_sha256")!=sha(state["raw"])
            or backup.get("original_title")!=state["title"]
            or backup.get("original_media")!=state["media"]
            or backup.get("original_modified_gmt")!=state["modified"]
            or backup.get("revised_sha256")!=sha(revised_body)
            or backup.get("remote_writes")!=0):
        raise PublishError("Concurrent pregnancy page edit since backup")
    if state["mode"]=="already_applied":
        verify_public(URL,state["title"],revised_body)
        if not public_after(public_page()):
            raise PublishError("Published pregnancy no-buy content not visible")
        print(json.dumps({"state":"ALREADY_VERIFIED_NO_WRITE",
                          "post_id":POST_ID,"post_attempts":0,"posts_changed":0}))
        return
    if not public_before(public_page()):
        raise PublishError("Pregnancy public page changed before write")
    uncertain=False
    try:
        resp=wp_request(normalized_base(),f"posts/{POST_ID}",
                        payload={"content":revised_body})
        uncertain=(not isinstance(resp,dict)
                   or resp.get("id")!=POST_ID
                   or resp.get("status")!="publish")
    except (PublishError,OSError,ValueError,TypeError):
        uncertain=True
    try:
        current=classify(remote())
    except (PublishError,OSError,ValueError,TypeError) as exc:
        print(json.dumps({"state":"UNKNOWN_NO_RETRY",
                          "post_id":POST_ID,"post_attempts":1}))
        raise PublishError("Pregnancy postwrite identity unknown; no retry") from exc
    if (current["mode"]!="already_applied"
            or article_visible(current["raw"])[0]!=article_visible(revised_body)[0]
            or editorial_links(current["raw"])!=editorial_links(revised_body)
            or current["title"]!=state["title"]
            or current["media"]!=state["media"]):
        raise PublishError("Pregnancy authenticated readback mismatch; no retry")
    verify_public(URL,state["title"],revised_body)
    for n in range(3):
        try:
            if public_after(public_page()):
                print(json.dumps({
                    "state":"PUBLIC_PREGNANCY_SAFETY_VERIFIED",
                    "post_id":POST_ID,"url":URL,
                    "post_attempts":1,"posts_changed":1,
                    "expired_coupon_removed":True,
                    "new_posts":0,"redirects":0,"deletes":0,
                    "write_response_uncertain":uncertain,
                    "public_site_modified":True
                }))
                return
        except (OSError,ValueError,PublishError):
            pass
        if n<2:time.sleep(3)
    raise PublishError("Pregnancy public proof unavailable; no WP retry")


if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("snapshot","deploy"):
            raise PublishError("Usage: snapshot|deploy")
        (snapshot if sys.argv[1]=="snapshot" else deploy)()
    except (PublishError,OSError,ValueError,TypeError,KeyError) as exc:
        print("XFIT_PREGNANCY_6331_RELEASE_ERROR: "+type(exc).__name__,
              file=sys.stderr)
        raise SystemExit(2)
