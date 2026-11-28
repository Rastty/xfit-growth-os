"""One reviewed legacy arm training article, source-bound native release."""
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urljoin, parse_qs, unquote, quote, urlunsplit
from scripts.wp_publish import normalized_base, wp_request, PublishError, verify_public, normalize_visible, article_visible, editorial_links
from scripts.xfit_legacy_mat_release import stable_metadata
from scripts.xfit_legacy_fitness_fabric_guide import Images, media_url as strict_media_url, local_image
from scripts.xfit_coupon_cleanup import QUARANTINE_IDS, stripped
from scripts.xfit_coupon_attempt_ledger import load as ledger_load, reserve as ledger_reserve
from scripts.xfit_public_coupon_watch import probe
from scripts.xfit_editorial_gate import check_document
from scripts.xfit_equipment_refresh import read_source, URL as TARGET, TITLE as TARGET_TITLE

POST_ID = 9362
SLUG = "jak-ziskat-pevne-paze-cviky-a-strategie-pro-rozvoj-svalu-na-rukou"
URL = "https://xfit.cz/" + SLUG + "/"
TITLE = "Jak získat pevné paže: Cviky a strategie pro rozvoj svalů na rukou"
MARKER = 'id="xfit-arm-training-v1"'
BODY = Path("content/revisions/legacy-arm-training.html")
BACKUP = Path("reports/backups/xfit-legacy-arm-training-original.json")
FIELDS = "id,slug,status,link,title,content,excerpt,categories,tags,sticky,featured_media,modified_gmt"
ANCHORS = ("Podtlaky", "Bicepsové zdvihy", "Flapadla", "Flapjack", "Svaly na ruce")
PLACEHOLDER = "<!-- XFIT_ORIGINAL_MEDIA -->"
VIDEO = "https://www.youtube.com/watch?v=hY2fa6Q98-k"
CATEGORY = "https://xfit.cz/category/kulturistika-fitness/trenink/"
BANNER_PATH = "/wp-content/uploads/2023/03/Blue-and-Yellow-Modern-Best-Deal-Fashion-Sale-Email-Header.png"
REVIEWED_PHOTOS = {
    "/wp-content/uploads/2023/04/scott-webb-5IsdIqwwNP4-unsplash.jpg",
    "/wp-content/uploads/2023/04/alonso-reyes-0HlI76m4jxU-unsplash.jpg",
    "/wp-content/uploads/2023/04/gabin-vallet-J154nEkpzlQ-unsplash.jpg",
}

def media_url(value):
    # Old WordPress sources can contain relative or unescaped Czech filenames.
    # Canonicalize only safe same-site image paths, never accept other hosts,
    # queries, fragments, credentials, ports, nested paths or traversal.
    dest = urljoin(URL, value)
    try:
        return strict_media_url(dest)
    except PublishError:
        p = urlsplit(dest)
        decoded = unquote(p.path)
        match = re.fullmatch(r"/wp-content/uploads/[0-9]{4}/[0-9]{2}/([^/]+)", decoded)
        if (local_image(dest) and match and ".." not in decoded
                and re.fullmatch(r"[\w .()-]+\.(?:jpg|jpeg|png|webp|gif)", match.group(1), re.I)
                and not match.group(1).startswith(".")):
            return urlunsplit(("https", p.hostname, quote(decoded, safe="/-._"), "", ""))
        # Bounded diagnostic, no queries, credentials or arbitrary raw HTML.
        safe_host = p.hostname if p.hostname in ("xfit.cz","www.xfit.cz") else "external-or-inline"
        safe_path = p.path[:220] if safe_host != "external-or-inline" and p.path.startswith("/wp-content/uploads/") else "(not a local upload)"
        print(json.dumps({"state":"ARM_MEDIA_REVIEW_REQUIRED","host":safe_host,"path":safe_path},ensure_ascii=False))
        raise PublishError("Unrecognized original media path")


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def read():
    rows = wp_request(normalized_base(), "posts?" + urlencode({"slug":SLUG,"context":"edit","status":"publish","per_page":2,"_fields":FIELDS}))
    if not isinstance(rows,list) or len(rows)!=1:
        raise PublishError("Expected one exact published source")
    row=rows[0]
    if (type(row.get("id")) is not int or row["id"]!=POST_ID or row["id"] in QUARANTINE_IDS or row.get("slug")!=SLUG
            or row.get("link")!=URL or row.get("status")!="publish"
            or normalize_visible(row.get("title",{}).get("raw",""))!=normalize_visible(TITLE)
            or not isinstance(row.get("modified_gmt"),str)):
        raise PublishError("Legacy source identity drift or quarantine")
    stable_metadata(row)
    return row

def revised(row):
    raw=row["content"]["raw"]
    rendered=row["content"]["rendered"]
    if not isinstance(raw,str) or not isinstance(rendered,str) or not 1000<=len(raw.encode())<=400000:
        raise PublishError("Unexpected source size")
    if MARKER in raw:
        raise PublishError("Already revised; no repeat")
    visible,_=article_visible(raw)
    if any(normalize_visible(a) not in visible for a in ANCHORS):
        raise PublishError("Publicly reviewed old anchors missing")
    # Exact GET-only review #490 identified one unrelated keto CTA, one
    # specific historical YouTube iframe, and the original category link.
    # No obsolete 5NM2022 coupon was present; any later occurrence blocks.
    raw,coupons=stripped(raw)
    if coupons or "5nm2022" in raw.casefold():
        raise PublishError("Unexpected obsolete coupon")
    buttons=list(re.finditer(r"\[su_button\b[^\]]{0,1200}\](.*?)\[/su_button\]",raw,re.I|re.S))
    if len(buttons)!=1 or len(re.findall(r"\[/?su_button\b",raw,re.I))!=2:
        raise PublishError("Reviewed keto button count differs")
    button=buttons[0]
    if "top keto dieta v akci" not in normalize_visible(button.group(0)):
        raise PublishError("Reviewed keto button label differs")
    # Require the known local keto destination, not any other CTA.
    keto_links=[urlsplit(urljoin(URL,u)) for u in editorial_links(raw)]
    if sum(p.hostname=="xfit.cz" and p.path.rstrip("/")=="/ketomix" and not p.query and not p.fragment for p in keto_links)!=1:
        raise PublishError("Reviewed keto destination differs")
    frames=list(re.finditer(r'<iframe\b[^>]*\bsrc\s*=\s*["\x27]([^"\x27]+)["\x27][^>]*>\s*</iframe\s*>',raw,re.I|re.S))
    if len(frames)!=1 or len(re.findall(r"<iframe\b",raw,re.I))!=1:
        raise PublishError("Reviewed video count differs")
    video=urlsplit(frames[0].group(1))
    if (video.scheme not in ("http","https") or video.hostname!="www.youtube.com" or video.path!="/embed/hY2fa6Q98-k"
            or video.username or video.password or video.port):
        raise PublishError("Reviewed video destination differs")
    if re.search(r"<\s*(?:video|audio|script|form|object|embed)\b|\[(?:gallery|embed)\b",raw,re.I):
        raise PublishError("Unreviewed embedded media")
    inventory=[]
    main=[]
    removed=[]
    kept_category=0
    if editorial_links(raw).count("#")!=6 or "" in editorial_links(raw):
        raise PublishError("Reviewed placeholder count differs")
    for href in editorial_links(raw):
        if href=="#":continue
        dest=urljoin(URL,href)
        p=urlsplit(dest)
        if local_image(dest):
            u=media_url(dest)
            if u not in inventory:inventory.append(u)
        elif (p.hostname=="xfit.cz" and p.path.rstrip("/")=="/ketomix" and not p.query and not p.fragment and not p.username and not p.password and not p.port):
            removed.append(("xfit.cz","/ketomix"))
        elif (p.hostname=="xfit.cz" and p.path.rstrip("/")=="/category/kulturistika-fitness/trenink" and not p.query and not p.fragment and not p.username and not p.password and not p.port):
            kept_category+=1
        else:
            raise PublishError("Unreviewed legacy link")
    if removed!=[("xfit.cz","/ketomix")] or kept_category!=1:
        raise PublishError("Reviewed old citation inventory differs")
    for source in (raw,rendered):
        parser=Images();parser.feed(source)
        if len(parser.images)>12:raise PublishError("Too many original images")
        banners=0
        for img in parser.images:
            src=urlsplit(urljoin(URL,img.get("src","")))
            if (src.scheme in ("https","http") and src.hostname=="dokonala-zena.cz"
                    and src.path==BANNER_PATH and not src.query and not src.fragment
                    and not src.username and not src.password and not src.port
                    and not any(img.get(k) for k in ("data-src","data-lazy-src","srcset","data-srcset","data-lazy-srcset"))):
                banners+=1
                continue
            urls=[media_url(img[k]) for k in ("src","data-src","data-lazy-src") if img.get(k)]
            if not urls:raise PublishError("Missing original image source")
            for key in ("srcset","data-srcset","data-lazy-srcset"):
                for entry in img.get(key,"").split(","):
                    if entry.strip():urls.append(media_url(entry.strip().split()[0]))
            for u in urls:
                if u not in inventory:inventory.append(u)
            if source==rendered and urls[0] not in main:main.append(urls[0])
        if banners!=1:
            raise PublishError("Reviewed external promotional banner count differs")
    if len(inventory)>40 or not REVIEWED_PHOTOS<={urlsplit(u).path for u in inventory}:
        raise PublishError("Reviewed local media missing or inventory too large")
    if inventory and not main:main=[inventory[0]]
    parts=['<p><img src="'+html.escape(u,quote=True)+'" alt="Původní ilustrační fotografie k posilování paží" loading="lazy" style="max-width:100%;height:auto;" /></p>' for u in main]
    extras=[u for u in inventory if u not in main]
    if extras:parts.append('<details><summary>Původní obrazové přílohy</summary><ul>'+''.join('<li><a href="'+html.escape(u,quote=True)+'">Obrazová příloha '+str(i+1)+'</a></li>' for i,u in enumerate(extras))+'</ul></details>')
    parts.append('<p><small>Původní ilustrační video: <a href="'+VIDEO+'">The Muscles Song</a>. Historický odkaz, nikoli instruktáž cviků. Další články: <a href="'+CATEGORY+'">kategorie trénink</a>.</small></p>')
    body=BODY.read_text(encoding="utf-8").strip()
    if body.count(MARKER)!=1 or body.count(PLACEHOLDER)!=1:raise PublishError("Reviewed revision missing")
    body=body.replace(PLACEHOLDER,"\n".join(parts))
    proof=check_document({"content":body},commercial=False)
    if proof["word_count"]<1450 or editorial_links(body).count(TARGET)!=1 or editorial_links(body).count(VIDEO)!=1 or editorial_links(body).count(CATEGORY)!=1 or not set(inventory)<=set(editorial_links(body))|set(main):
        raise PublishError("Editorial or media preservation guard failed")
    return body,proof["word_count"],len(removed),coupons

def snapshot():
    gear,_=read_source()
    verify_public(TARGET,TARGET_TITLE,gear)
    row=read()
    verify_public(URL,TITLE,row["content"]["rendered"])
    new,words,removed,coupons=revised(row)
    ledger=ledger_load() if coupons else None
    if ledger and row["id"] in ledger.ids:
        raise PublishError("Coupon ID already reserved; no repeat")
    if BACKUP.exists():raise PublishError("Never overwrite backup")
    BACKUP.parent.mkdir(parents=True,exist_ok=True)
    BACKUP.write_text(json.dumps({"schema":1,"before":row,"before_sha":sha(row["content"]["raw"]),"after_sha":sha(new),"coupon_count":coupons,"ledger_fingerprint":ledger.fingerprint if ledger else None,"ledger_updated_at":ledger.updated_at if ledger else None,"wordpress_writes":0},ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"state":"ARM_TRAINING_BACKUP_READY","post_id":row["id"],"words":words,"reviewed_links_removed":removed,"shortcodes_removed":coupons,"wordpress_writes":0}))

def apply():
    saved=json.loads(BACKUP.read_text(encoding="utf-8"))
    before=read()
    new,words,removed,coupons=revised(before)
    if saved.get("schema")!=1 or saved.get("wordpress_writes")!=0 or saved.get("before")!=before or saved.get("before_sha")!=sha(before["content"]["raw"]) or saved.get("after_sha")!=sha(new) or saved.get("coupon_count")!=coupons:
        raise PublishError("Source changed after backup")
    if coupons:
        ledger=ledger_load()
        if ledger.fingerprint!=saved["ledger_fingerprint"] or ledger.updated_at!=saved["ledger_updated_at"]:
            raise PublishError("Coupon attempt ledger changed")
        ledger_reserve(ledger,[before["id"]])
    try:
        wp_request(normalized_base(),"posts/"+str(before["id"]),payload={"content":new})
    except (PublishError,OSError,ValueError,TypeError):
        pass
    after=read()
    if after["content"]["raw"]!=new or stable_metadata(after)!=stable_metadata(before):
        raise PublishError("Exact source and metadata not verified; no retry")
    verify_public(URL,TITLE,after["content"]["rendered"])
    if coupons:
        result=probe(before["id"],SLUG)
        if result.get("state")!="PUBLIC_NO_COUPON_OBSERVED" or result.get("visible_mentions")!=0:
            raise PublishError("Public absence of old coupon not verified")
    print(json.dumps({"state":"PUBLIC_ARM_TRAINING_REVISION_VERIFIED","post_id":before["id"],"url":URL,"words":words,"reviewed_links_removed":removed,"shortcodes_removed":coupons,"post_attempts":1,"posts_changed":1,"new_posts":0,"public_site_modified":True}))

if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("snapshot","apply"):raise PublishError("Unknown scope")
        (snapshot if sys.argv[1]=="snapshot" else apply)()
    except (PublishError,ValueError,OSError,KeyError,TypeError) as exc:
        print("XFIT_ARM_TRAINING_BLOCKED: "+(str(exc) if isinstance(exc,PublishError) else type(exc).__name__))
        raise SystemExit(2)
