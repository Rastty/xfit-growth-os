"""Reviewed legacy bra article: rewrite inaccurate advice, retain the original local image."""
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit, urlunsplit
from scripts.wp_publish import normalized_base, wp_request, PublishError, verify_public, normalize_visible, article_visible, editorial_links
from scripts.xfit_legacy_mat_release import stable_metadata
from scripts.xfit_coupon_cleanup import QUARANTINE_IDS
from scripts.xfit_editorial_gate import check_document
from scripts.xfit_apparel_refresh import read_source, URL as TARGET, TITLE as TARGET_TITLE

SLUG = "jak-na-vyber-podprsenky"
URL = "https://xfit.cz/" + SLUG + "/"
TITLE = "Jak na výběr podprsenky"
MARKER = 'id="xfit-bra-fit-guide-v1"'
ANCHOR = TARGET + "#xfit-apparel-bra"
BODY = Path("content/revisions/legacy-bra-fit-guide.html")
BACKUP = Path("reports/backups/xfit-legacy-bra-original.json")
FIELDS = "id,slug,status,link,title,content,excerpt,categories,tags,sticky,featured_media,modified_gmt"
ANCHORS = ("Dámy, umíte si vybrat tu pravou podprsenku", "krejčovský metr",
           "pěti až deseti centimetrů", "v nejširším místě",
           "bolesti krční páteře", "push-up podprsenka")
OLD_HOSTS = {"tabulkavelikosti.cz","vybiramepodprsenky.blogspot.cz",
             "wonderbra.co.uk","lascana-shop.cz","victoriassecret.com"}
IMAGE_PLACEHOLDER = "<!-- XFIT_REVIEWED_ORIGINAL_IMAGE -->"
REVIEWED_IMAGE = "https://xfit.cz/wp-content/uploads/2016/08/1111111111.jpg"
REVIEWED_PATH = re.compile(r"^/wp-content/uploads/2016/08/1111111111(?:-[0-9]+x[0-9]+)?\.jpg$")

class Images(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images = []
    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.images.append(dict(attrs))

def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def local_image(url):
    p = urlsplit(url)
    return (p.scheme in ("https","http") and p.hostname in ("xfit.cz","www.xfit.cz")
            and not p.username and not p.password and not p.port
            and not p.query and not p.fragment and p.path.startswith("/wp-content/uploads/"))

def read():
    rows = wp_request(normalized_base(), "posts?" + urlencode({
        "slug":SLUG,"context":"edit","status":"publish","per_page":2,"_fields":FIELDS}))
    if not isinstance(rows,list) or len(rows)!=1:
        raise PublishError("Expected one exact published legacy article")
    row=rows[0]
    if (type(row.get("id")) is not int or row["id"] in QUARANTINE_IDS
            or row.get("slug")!=SLUG or row.get("link")!=URL or row.get("status")!="publish"
            or normalize_visible(row.get("title",{}).get("raw",""))!=normalize_visible(TITLE)
            or not isinstance(row.get("modified_gmt"),str)):
        raise PublishError("Legacy source identity drift or quarantine")
    stable_metadata(row)
    return row

def revised(raw, rendered):
    if not isinstance(raw,str) or not 1500<=len(raw.encode())<=400000 or MARKER in raw:
        raise PublishError("Unexpected legacy source or already revised")
    visible,_=article_visible(raw)
    if any(normalize_visible(anchor) not in visible for anchor in ANCHORS) or "5nm2022" in raw.casefold():
        raise PublishError("Reviewed old article anchors missing or unexpected coupon")
    if re.search(r"<\s*(?:iframe|video|audio|script|form|object|embed)\b|\[(?:gallery|embed)\b",raw,re.I):
        raise PublishError("Unreviewed embedded media")
    old=[]
    for href in editorial_links(raw):
        p=urlsplit(href)
        if p.scheme not in ("http","https") or p.username or p.password or p.port:
            raise PublishError("Unreviewed legacy link")
        if local_image(href):
            if not REVIEWED_PATH.fullmatch(p.path):
                raise PublishError("Unreviewed linked local image")
            continue
        old.append((p.hostname or "").removeprefix("www."))
    if len(old)!=5 or set(old)!=OLD_HOSTS:
        raise PublishError("Reviewed legacy link hosts differ")
    # The reviewed public image is the authoritative unique photograph.
    # WP legacy shortcodes or duplicate responsive markup can alter raw tag
    # counts; permit only that same local file or its resized WP derivative.
    if not isinstance(rendered,str):
        raise PublishError("Missing authenticated rendered article")
    parsers=[]
    for source in (raw,rendered):
        parser=Images()
        parser.feed(source)
        parsers.append(parser)
    if not parsers[1].images or len(parsers[0].images)>6 or len(parsers[1].images)>6:
        raise PublishError("Unexpected original image inventory: raw="+str(len(parsers[0].images))+", rendered="+str(len(parsers[1].images)))
    for parser in parsers:
        for image in parser.images:
            urls=[image.get(k) for k in ("src","data-src","data-lazy-src") if image.get(k)]
            if not urls or any(not local_image(u) or not REVIEWED_PATH.fullmatch(urlsplit(u).path) for u in urls):
                raise PublishError("Unreviewed original image in raw or rendered source")
            for key in ("srcset","data-srcset","data-lazy-srcset"):
                for entry in image.get(key,"").split(","):
                    if entry.strip():
                        u=entry.strip().split()[0]
                        if not local_image(u) or not REVIEWED_PATH.fullmatch(urlsplit(u).path):
                            raise PublishError("Unreviewed responsive image source")
    pic='<p><img src="'+REVIEWED_IMAGE+'" alt="Ilustrační fotografie klasické podprsenky" loading="lazy" style="max-width:100%;height:auto;" /></p>'
    body=BODY.read_text(encoding="utf-8").strip()
    if body.count(IMAGE_PLACEHOLDER)!=1 or body.count(MARKER)!=1:
        raise PublishError("Reviewed new editorial source unavailable")
    body=body.replace(IMAGE_PLACEHOLDER,pic)
    proof=check_document({"content":body},commercial=False)
    if proof["word_count"]<800 or proof["image_count"]!=1 or editorial_links(body).count(ANCHOR)!=1:
        raise PublishError("Reviewed guide incomplete")
    return body,proof["word_count"]

def snapshot():
    target,_=read_source()
    verify_public(TARGET,TARGET_TITLE,target)
    if 'id="xfit-apparel-bra"' not in target:
        raise PublishError("Sports bra catalog group unavailable")
    row=read()
    raw=row["content"]["raw"]
    verify_public(URL,TITLE,row["content"].get("rendered") or raw)
    new,words=revised(raw,row["content"].get("rendered"))
    if BACKUP.exists():
        raise PublishError("Refusing to overwrite prewrite backup")
    BACKUP.parent.mkdir(parents=True,exist_ok=True)
    BACKUP.write_text(json.dumps({"schema":1,"before":row,"before_sha":sha(raw),
        "after_sha":sha(new),"wordpress_writes":0},ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"state":"BRA_GUIDE_BACKUP_READY","post_id":row["id"],"words":words,"wordpress_writes":0}))

def apply():
    backup=json.loads(BACKUP.read_text(encoding="utf-8"))
    row=read()
    old=row["content"]["raw"]
    new,words=revised(old,row["content"].get("rendered"))
    if (backup.get("schema")!=1 or backup.get("wordpress_writes")!=0 or backup.get("before")!=row
            or backup.get("before_sha")!=sha(old) or backup.get("after_sha")!=sha(new)):
        raise PublishError("Source drift after immutable backup")
    try:
        wp_request(normalized_base(),"posts/"+str(row["id"]),payload={"content":new})
    except (PublishError,ValueError,OSError,TypeError):
        pass
    after=read()
    if after["content"]["raw"]!=new or stable_metadata(after)!=stable_metadata(row):
        raise PublishError("Exact source and metadata not verified; no retry")
    verify_public(URL,TITLE,after["content"].get("rendered") or new)
    print(json.dumps({"state":"PUBLIC_LEGACY_BRA_GUIDE_VERIFIED","post_id":row["id"],
        "url":URL,"words":words,"posts_changed":1,"post_attempts":1,
        "public_site_modified":True,"new_posts":0,"original_image_retained":True,"old_links_removed":5}))

if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("snapshot","apply"):
            raise PublishError("Unknown scope")
        (snapshot if sys.argv[1]=="snapshot" else apply)()
    except (PublishError,ValueError,OSError,KeyError,TypeError) as exc:
        print("XFIT_LEGACY_BRA_GUIDE_BLOCKED: "+(str(exc) if isinstance(exc,PublishError) else type(exc).__name__))
        raise SystemExit(2)
