"""One reviewed legacy functional training article, source-bound native release."""
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urljoin
from scripts.wp_publish import normalized_base, wp_request, PublishError, verify_public, normalize_visible, article_visible, editorial_links
from scripts.xfit_legacy_mat_release import stable_metadata
from scripts.xfit_legacy_fitness_fabric_guide import Images, media_url, local_image
from scripts.xfit_coupon_cleanup import QUARANTINE_IDS
from scripts.xfit_editorial_gate import check_document
from scripts.xfit_equipment_refresh import read_source, URL as TARGET, TITLE as TARGET_TITLE

SLUG = "co-je-to-funkcni-trenink"
URL = "https://xfit.cz/" + SLUG + "/"
TITLE = "Co je to funkční trénink?"
MARKER = 'id="xfit-functional-training-v1"'
BODY = Path("content/revisions/legacy-functional-training.html")
BACKUP = Path("reports/backups/xfit-legacy-functional-training-original.json")
FIELDS = "id,slug,status,link,title,content,excerpt,categories,tags,sticky,featured_media,modified_gmt"
ANCHORS = ("Funkční trénink nabízí", "Funkční kruhový trénink", "kooperaci nervového a svalového systému", "kratší tréninková jednotka", "volnokladkových pomůckách")
OLD_LINKS = {("hammerstrength.cz","/funkcni-kruhovy-trenink"), ("hammerstrength.cz","/"), ("fittyn.cz","/neni-cinka-jako-cinka-slyseli-jste-o-kettlebell")}
VIDEO = "sUa1KynaPgU"
PLACEHOLDER = "<!-- XFIT_ORIGINAL_MEDIA -->"

def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def read():
    rows = wp_request(normalized_base(), "posts?" + urlencode({"slug":SLUG,"context":"edit","status":"publish","per_page":2,"_fields":FIELDS}))
    if not isinstance(rows,list) or len(rows)!=1:
        raise PublishError("Expected one exact published source")
    row=rows[0]
    if (type(row.get("id")) is not int or row["id"] in QUARANTINE_IDS or row.get("slug")!=SLUG
            or row.get("link")!=URL or row.get("status")!="publish"
            or normalize_visible(row.get("title",{}).get("raw",""))!=normalize_visible(TITLE)
            or not isinstance(row.get("modified_gmt"),str)):
        raise PublishError("Legacy source identity drift or quarantine")
    stable_metadata(row)
    return row

def revised(row):
    raw=row["content"]["raw"]
    rendered=row["content"]["rendered"]
    if not isinstance(raw,str) or not isinstance(rendered,str) or not 700<=len(raw.encode())<=400000:
        raise PublishError("Unexpected source size")
    if MARKER in raw:
        raise PublishError("Already revised; no repeat")
    visible,_=article_visible(raw)
    if any(normalize_visible(a) not in visible for a in ANCHORS):
        raise PublishError("Publicly reviewed old anchors missing")
    if "5nm2022" in raw.casefold() or re.search(r"<\s*(?:video|audio|script|form|object|embed)\b|\[(?:gallery|su_button)\b",raw,re.I):
        raise PublishError("Unreviewed coupon or embedded media")
    frames=re.findall(r'<iframe\b[^>]*\bsrc\s*=\s*["\x27]([^"\x27]+)["\x27][^>]*>',raw,re.I)
    if len(frames)!=len(re.findall(r"<iframe\b",raw,re.I)) or len(frames)>1 or any(urlsplit(u).hostname not in ("www.youtube.com","youtube.com","www.youtube-nocookie.com") or urlsplit(u).path!="/embed/"+VIDEO for u in frames):
        raise PublishError("Unreviewed embedded media")
    if VIDEO not in raw and VIDEO not in rendered:
        raise PublishError("Reviewed original video missing")
    for match in re.findall(r"\[embed\](.*?)\[/embed\]",raw,re.I|re.S):
        if VIDEO not in match or len(match)>200:raise PublishError("Unreviewed video shortcode")
    inventory=[]
    main=[]
    removed=[]
    for href in editorial_links(raw):
        if href in ("","#"):continue
        dest=urljoin(URL,href)
        p=urlsplit(dest)
        if local_image(dest):
            u=media_url(dest)
            if u not in inventory:inventory.append(u)
        elif (p.hostname or "").removeprefix("www.") in ("youtube.com","youtu.be","youtube-nocookie.com") and VIDEO in (p.path+"?"+p.query):
            continue
        elif ((p.hostname or "").removeprefix("www."),p.path.rstrip("/") or "/") in OLD_LINKS and p.scheme in ("http","https") and not p.username and not p.password and not p.port:
            removed.append(((p.hostname or "").removeprefix("www."),p.path or "/"))
        else:
            raise PublishError("Unreviewed legacy link")
    if len(removed)!=3 or set(removed)!=OLD_LINKS:
        raise PublishError("Reviewed promotional link inventory differs")
    for source in (raw,rendered):
        parser=Images();parser.feed(source)
        if len(parser.images)>12:raise PublishError("Too many original images")
        for img in parser.images:
            urls=[media_url(img[k]) for k in ("src","data-src","data-lazy-src") if img.get(k)]
            if not urls:raise PublishError("Missing original image source")
            for key in ("srcset","data-srcset","data-lazy-srcset"):
                for entry in img.get(key,"").split(","):
                    if entry.strip():urls.append(media_url(entry.strip().split()[0]))
            for u in urls:
                if u not in inventory:inventory.append(u)
            if source==rendered and urls[0] not in main:main.append(urls[0])
    if len(inventory)>40:raise PublishError("Too many original media destinations")
    if inventory and not main:main=[inventory[0]]
    parts=['<p><img src="'+html.escape(u,quote=True)+'" alt="Původní ilustrační fotografie k funkčnímu tréninku" loading="lazy" style="max-width:100%;height:auto;" /></p>' for u in main]
    extras=[u for u in inventory if u not in main]
    if extras:parts.append('<details><summary>Původní obrazové přílohy</summary><ul>'+''.join('<li><a href="'+html.escape(u,quote=True)+'">Obrazová příloha '+str(i+1)+'</a></li>' for i,u in enumerate(extras))+'</ul></details>')
    parts.append('<p><small>Původní ilustrační video: <a href="https://www.youtube.com/watch?v='+VIDEO+'">Hammer Strength – funkční trénink Praha</a>. Video není důkaz účinnosti konkrétní metody.</small></p>')
    body=BODY.read_text(encoding="utf-8").strip()
    if body.count(MARKER)!=1 or body.count(PLACEHOLDER)!=1:raise PublishError("Reviewed revision missing")
    body=body.replace(PLACEHOLDER,"\n".join(parts))
    proof=check_document({"content":body},commercial=False)
    if proof["word_count"]<1200 or editorial_links(body).count(TARGET)!=1 or not set(inventory)<=set(editorial_links(body))|set(main):
        raise PublishError("Editorial or media preservation guard failed")
    return body,proof["word_count"],len(removed)

def snapshot():
    gear,_=read_source()
    verify_public(TARGET,TARGET_TITLE,gear)
    row=read()
    verify_public(URL,TITLE,row["content"]["rendered"])
    new,words,removed=revised(row)
    if BACKUP.exists():raise PublishError("Never overwrite backup")
    BACKUP.parent.mkdir(parents=True,exist_ok=True)
    BACKUP.write_text(json.dumps({"schema":1,"before":row,"before_sha":sha(row["content"]["raw"]),"after_sha":sha(new),"wordpress_writes":0},ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"state":"FUNCTIONAL_TRAINING_BACKUP_READY","post_id":row["id"],"words":words,"reviewed_links_removed":removed,"wordpress_writes":0}))

def apply():
    saved=json.loads(BACKUP.read_text(encoding="utf-8"))
    before=read()
    new,words,removed=revised(before)
    if saved.get("schema")!=1 or saved.get("wordpress_writes")!=0 or saved.get("before")!=before or saved.get("before_sha")!=sha(before["content"]["raw"]) or saved.get("after_sha")!=sha(new):
        raise PublishError("Source changed after backup")
    try:
        wp_request(normalized_base(),"posts/"+str(before["id"]),payload={"content":new})
    except (PublishError,OSError,ValueError,TypeError):
        pass
    after=read()
    if after["content"]["raw"]!=new or stable_metadata(after)!=stable_metadata(before):
        raise PublishError("Exact source and metadata not verified; no retry")
    verify_public(URL,TITLE,after["content"]["rendered"])
    print(json.dumps({"state":"PUBLIC_FUNCTIONAL_TRAINING_WORKOUT_REVISION_VERIFIED","post_id":before["id"],"url":URL,"words":words,"reviewed_links_removed":removed,"post_attempts":1,"posts_changed":1,"new_posts":0,"public_site_modified":True}))

if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("snapshot","apply"):raise PublishError("Unknown scope")
        (snapshot if sys.argv[1]=="snapshot" else apply)()
    except (PublishError,ValueError,OSError,KeyError,TypeError) as exc:
        print("XFIT_FUNCTIONAL_TRAINING_BLOCKED: "+(str(exc) if isinstance(exc,PublishError) else type(exc).__name__))
        raise SystemExit(2)
