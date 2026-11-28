"""Reviewed legacy fitness fabric article: replace repetitive advice, preserve original media."""
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
from scripts.xfit_coupon_cleanup import QUARANTINE_IDS, stripped
from scripts.xfit_coupon_attempt_ledger import load as ledger_load, reserve as ledger_reserve
from scripts.xfit_public_coupon_watch import probe
from scripts.xfit_editorial_gate import check_document
from scripts.xfit_apparel_refresh import read_source, URL as TARGET, TITLE as TARGET_TITLE

SLUG = "vyber-spravneho-materialu-pro-damske-fitness-obleceni-rady-od-expertu"
URL = "https://xfit.cz/" + SLUG + "/"
TITLE = "Výběr správného materiálu pro dámské fitness oblečení – rady od expertů"
MARKER = 'id="xfit-fabric-guide-v1"'
ANCHOR = TARGET
BODY = Path("content/revisions/legacy-fitness-fabric-guide.html")
BACKUP = Path("reports/backups/xfit-legacy-fabric-original.json")
FIELDS = "id,slug,status,link,title,content,excerpt,categories,tags,sticky,featured_media,modified_gmt"
ANCHORS = ("Funkční materiály", "Materiál pro trička a topy",
           "Materiál pro legíny a kalhoty", "Oeko-Tex Standard 100",
           "Jak se pečovat o dámské fitness oblečení")
OLD_HOSTS = {"shape.com","cs.wikipedia.org"}
IMAGE_PLACEHOLDER = "<!-- XFIT_REVIEWED_ORIGINAL_IMAGE -->"
REVIEWED_PATH = re.compile(r"^/wp-content/uploads/2023/04/(?:samuel-girven-4Bp8v9A0zKw-unsplash|damske-fitness-leginy-black-muscle-aggressive-53757|damska-mikina-crop-small-red-muscleaggressive-54235)(?:-[0-9]+x[0-9]+)?\.jpg$")
KNOWN_VIDEO = "https://www.youtube.com/watch?v=aupTj6t-FfI"

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

def media_url(url):
    # Preserve only site-local WordPress image assets, not arbitrary URLs.
    p=urlsplit(url)
    if not local_image(url) or not re.fullmatch(r"/wp-content/uploads/[0-9]{4}/[0-9]{2}/[A-Za-z0-9_%.-]+\.(?:jpg|jpeg|png|webp|gif)",p.path,re.I) or ".." in p.path:
        raise PublishError("Unrecognized original media path")
    return urlunsplit(("https",p.netloc,p.path,"",""))


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
    if any(normalize_visible(anchor) not in visible for anchor in ANCHORS):
        raise PublishError("Reviewed old article anchors missing or unexpected coupon")
    cleaned,coupons=stripped(raw)
    if coupons not in (0,3) or "5nm2022" in cleaned.casefold():
        raise PublishError("Unexpected obsolete coupon inventory")
    # Only the publicly reviewed YouTube video may be replaced with a plain link.
    frames=re.findall(r'<iframe\b[^>]*\bsrc\s*=\s*["\x27]([^"\x27]+)["\x27][^>]*>',cleaned,re.I)
    if any(urlsplit(u).hostname not in ("www.youtube.com","youtube.com","www.youtube-nocookie.com") or urlsplit(u).path!="/embed/aupTj6t-FfI" for u in frames):
        raise PublishError("Unreviewed video embed")
    if len(re.findall(r"<iframe\b",cleaned,re.I))!=len(frames) or len(frames)>1 or re.search(r"<\s*(?:video|audio|script|form|object|embed)\b|\[(?:gallery)\b",cleaned,re.I):
        raise PublishError("Unreviewed embedded media")
    video_present=bool(frames) or "aupTj6t-FfI" in cleaned
    if not video_present:
        raise PublishError("Reviewed video missing")
    for match in re.findall(r"\[embed\](.*?)\[/embed\]",cleaned,re.I|re.S):
        if "aupTj6t-FfI" not in match or len(match)>200:
            raise PublishError("Unreviewed shortcode video")

    old=[]
    linked_media=[]
    for href in editorial_links(cleaned):
        if href in ("#",""):
            continue
        p=urlsplit(href)
        if p.hostname in ("www.youtube.com","youtube.com","www.youtube-nocookie.com") and (p.path=="/embed/aupTj6t-FfI" or p.path=="/watch" and p.query=="v=aupTj6t-FfI"):
            continue
        if p.scheme not in ("http","https") or p.username or p.password or p.port:
            raise PublishError("Unreviewed legacy link")
        if local_image(href):
            linked_media.append(media_url(href))
            continue
        old.append((p.hostname or "").removeprefix("www."))
    if len(old)!=2 or set(old)!=OLD_HOSTS:
        raise PublishError("Reviewed legacy link hosts differ")
    # Retain ALL local original image destinations, including legacy linked
    # full-size images not visible in the text extractor. Never infer that a
    # different filename is a duplicate. Visible images retain their order.
    if not isinstance(rendered,str):
        raise PublishError("Missing authenticated rendered article")
    inventory=[]
    visible_images=[]
    for source in (raw,rendered):
        parser=Images()
        parser.feed(source)
        if len(parser.images)>12:
            raise PublishError("Unexpectedly large original image inventory")
        for image in parser.images:
            urls=[media_url(image[k]) for k in ("src","data-src","data-lazy-src") if image.get(k)]
            if not urls:
                raise PublishError("Original image has no source")
            for key in ("srcset","data-srcset","data-lazy-srcset"):
                for entry in image.get(key,"").split(","):
                    if entry.strip():
                        urls.append(media_url(entry.strip().split()[0]))
            for u in urls:
                if u not in inventory:
                    inventory.append(u)
            if source==rendered:
                primary=urls[0]
                if primary not in visible_images:
                    visible_images.append(primary)
    for u in linked_media:
        if u not in inventory:
            inventory.append(u)
    expected_families=("samuel-girven-4Bp8v9A0zKw-unsplash","damske-fitness-leginy-black-muscle-aggressive-53757","damska-mikina-crop-small-red-muscleaggressive-54235")
    if len(inventory)>40 or not all(any(REVIEWED_PATH.fullmatch(urlsplit(u).path) and name in urlsplit(u).path for u in inventory) for name in expected_families):
        raise PublishError("Reviewed public photo absent or original inventory too large")
    if not visible_images:
        # Legacy malformed markup may expose only the linked photo.
        visible_images=[next(u for u in inventory if REVIEWED_PATH.fullmatch(urlsplit(u).path))]
    parts=[]
    for u in visible_images:
        alt="Ilustrační fotografie fitness oblečení při tréninku" if REVIEWED_PATH.fullmatch(urlsplit(u).path) else "Původní ilustrační fotografie k článku"
        parts.append('<p><img src="'+html.escape(u,quote=True)+'" alt="'+alt+'" loading="lazy" style="max-width:100%;height:auto;" /></p>')
    # Preserve every extra original media destination as an accessible link,
    # including resized derivatives. No need to show identical photos twice.
    extras=[u for u in inventory if u not in visible_images]
    if extras:
        parts.append('<details><summary>Původní obrazové přílohy článku</summary><ul>'+''.join(
            '<li><a href="'+html.escape(u,quote=True)+'">Obrazová příloha '+str(i+1)+'</a></li>'
            for i,u in enumerate(extras))+'</ul></details>')
    pic="\n".join(parts)+'<p><small>Původní ilustrační video: <a href="'+KNOWN_VIDEO+'">Maria Moda – Female Fitness Motivation 2023</a>. Video neslouží jako důkaz vlastností materiálů.</small></p>'
    body=BODY.read_text(encoding="utf-8").strip()
    if body.count(IMAGE_PLACEHOLDER)!=1 or body.count(MARKER)!=1:
        raise PublishError("Reviewed new editorial source unavailable")
    body=body.replace(IMAGE_PLACEHOLDER,pic)
    proof=check_document({"content":body},commercial=False)
    if proof["word_count"]<800 or proof["image_count"]!=len(visible_images) or editorial_links(body).count(ANCHOR)!=1:
        raise PublishError("Reviewed guide incomplete")
    preserved=set(editorial_links(body)) | set(visible_images)
    if not set(inventory)<=preserved:
        raise PublishError("Original media destination not retained")
    return body,proof["word_count"],coupons

def snapshot():
    target,_=read_source()
    verify_public(TARGET,TARGET_TITLE,target)
    row=read()
    raw=row["content"]["raw"]
    verify_public(URL,TITLE,row["content"].get("rendered") or raw)
    new,words,coupons=revised(raw,row["content"].get("rendered"))
    ledger=ledger_load()
    if coupons and row["id"] in ledger.ids:
        raise PublishError("Coupon ID already reserved; no repeat")
    if BACKUP.exists():
        raise PublishError("Refusing to overwrite prewrite backup")
    BACKUP.parent.mkdir(parents=True,exist_ok=True)
    BACKUP.write_text(json.dumps({"schema":1,"before":row,"before_sha":sha(raw),
        "after_sha":sha(new),"coupon_count":coupons,"ledger_fingerprint":ledger.fingerprint,"ledger_updated_at":ledger.updated_at,"wordpress_writes":0},ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"state":"FABRIC_GUIDE_BACKUP_READY","post_id":row["id"],"words":words,"coupon_count":coupons,"wordpress_writes":0}))

def apply():
    backup=json.loads(BACKUP.read_text(encoding="utf-8"))
    row=read()
    old=row["content"]["raw"]
    new,words,coupons=revised(old,row["content"].get("rendered"))
    if (backup.get("schema")!=1 or backup.get("wordpress_writes")!=0 or backup.get("before")!=row
            or backup.get("before_sha")!=sha(old) or backup.get("after_sha")!=sha(new) or backup.get("coupon_count")!=coupons):
        raise PublishError("Source drift after immutable backup")
    if coupons:
        ledger=ledger_load()
        if ledger.fingerprint!=backup["ledger_fingerprint"] or ledger.updated_at!=backup["ledger_updated_at"]:
            raise PublishError("Coupon ledger changed")
        ledger_reserve(ledger,[row["id"]])
    try:
        wp_request(normalized_base(),"posts/"+str(row["id"]),payload={"content":new})
    except (PublishError,ValueError,OSError,TypeError):
        pass
    after=read()
    if after["content"]["raw"]!=new or stable_metadata(after)!=stable_metadata(row):
        raise PublishError("Exact source and metadata not verified; no retry")
    verify_public(URL,TITLE,after["content"].get("rendered") or new)
    result=probe(row["id"],SLUG)
    if result.get("state")!="PUBLIC_NO_COUPON_OBSERVED" or result.get("visible_mentions")!=0:
        raise PublishError("Public absence of old coupon not verified")
    print(json.dumps({"state":"PUBLIC_LEGACY_FABRIC_GUIDE_VERIFIED","post_id":row["id"],
        "url":URL,"words":words,"posts_changed":1,"post_attempts":1,
        "public_site_modified":True,"new_posts":0,"original_media_retained":True,"old_links_removed":2,"shortcodes_removed":coupons}))

if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("snapshot","apply"):
            raise PublishError("Unknown scope")
        (snapshot if sys.argv[1]=="snapshot" else apply)()
    except (PublishError,ValueError,OSError,KeyError,TypeError) as exc:
        print("XFIT_LEGACY_FABRIC_GUIDE_BLOCKED: "+(str(exc) if isinstance(exc,PublishError) else type(exc).__name__))
        raise SystemExit(2)
