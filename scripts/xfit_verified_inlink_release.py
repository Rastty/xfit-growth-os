"""Reusable, fail-closed, *allowlisted onepost* editorial inlink release.

A caller can choose only predefined pinned article IDs and reviewed exact
paragraphs. No arbitrary URL, HTML, bulk edit or retry of an ambiguous POST.
Always preserve the entire existing WP source, retain a prewrite artifact,
check authenticated readback and independently confirm the live public link.
"""
from dataclasses import dataclass
from html.parser import HTMLParser
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import time
import urllib.parse
import urllib.request

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts.xfit_editorial_gate import Inspector


@dataclass(frozen=True)
class Handoff:
    key: str
    post_id: int
    slug: str
    title_term: str
    target: str
    marker: str
    sentence: str
    paragraph: str

    @property
    def url(self):
        return "https://xfit.cz/" + self.slug + "/"

    @property
    def backup(self):
        return Path("reports/backups/xfit-reviewed-inlink-" + self.key + ".json")


_SAFETY_SLUG = (
    "kreatin-monohydrat-a-jeho-bezpecnostni-rizika-pri-uzivani-"
    "jak-se-chranit-pred-nezadoucimi-ucinky"
)
_SAFETY_URL = "https://xfit.cz/kreatin-a-jeho-vliv-na-ledviny-a-jatra/"
_SAFETY_MARKER = "xfit-creatine-safety-evidence-20261109"
_SAFETY_SENTENCE = "Co opravdu víme o kreatinu a ledvinách"
_SAFETY_PARAGRAPH = (
    '<p data-xfit-handoff="' + _SAFETY_MARKER + '">'
    '<strong>' + _SAFETY_SENTENCE + '?</strong> '
    'Pokud řešíte výsledky krevních testů, dlouhodobé onemocnění '
    'nebo nejistotu kolem užívání kreatinu, začněte ověřenými informacemi. '
    '<a href="' + _SAFETY_URL + '">Přečtěte si přehled studií o kreatinu, '
    'kreatininu, ledvinách a játrech</a>. '
    'Vyšší kreatinin nemusí sám o sobě dokazovat poškození ledvin, '
    'ale abnormální nález je nutné odborně posoudit. '
    'Konkrétní zdravotní omezení a výsledky testů řešte s lékařem. '
    'Kreatin není nutnou součástí tréninku a tento odkaz není doporučení '
    'doplněk koupit.</p>'
)
_PRICE_SLUG = "kde-koupit-nejlevnejsi-kreatin-pro-fitness"
_PRICE_URL = "https://xfit.cz/xfit-os-kreatin-poradce/"
_PRICE_MARKER = "xfit-creatine-price-guide-20261109"
_PRICE_SENTENCE = "Jak porovnat cenu kreatinu bez zbytečného přeplácení"
_PRICE_PARAGRAPH = (
    '<p data-xfit-handoff="' + _PRICE_MARKER + '">'
    '<strong>' + _PRICE_SENTENCE + '?</strong> '
    'Při hledání nejlevnějšího kreatinu zvažte nejen cenu balení, '
    'ale také gramáž, cenu za 100 g prášku a konečnou cenu '
    'včetně dopravy. Přehledná '
    '<a href="' + _PRICE_URL + '">pomůcka k porovnání balení '
    'kreatinu monohydrátu</a> ukazuje rozdíl mezi nejnižší '
    'jednorázovou útratou a nejnižší cenou za 100 g prášku '
    'na konkrétních katalogových nabídkách. Nejde o srovnání '
    'všech obchodů a čistotu jednotlivých produktů je potřeba '
    'ověřit na etiketě. Pokud kreatin nepotřebujete, nekupujte jej; '
    'tento odkaz není doporučení k nákupu ani příslib '
    'nejnižší ceny na celém trhu.</p>'
)
ALLOWLIST = {
    "creatine_price_10835": Handoff(
        key="creatine_price_10835",
        post_id=10835,
        slug=_PRICE_SLUG,
        title_term="kreatin",
        target=_PRICE_URL,
        marker=_PRICE_MARKER,
        sentence=_PRICE_SENTENCE,
        paragraph=_PRICE_PARAGRAPH,
    ),
    "creatine_safety_2139": Handoff(
        key="creatine_safety_2139",
        post_id=2139,
        slug=_SAFETY_SLUG,
        title_term="kreatin",
        target=_SAFETY_URL,
        marker=_SAFETY_MARKER,
        sentence=_SAFETY_SENTENCE,
        paragraph=_SAFETY_PARAGRAPH,
    )
}
MAX_BYTES = 400_000


def digest(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class Hrefs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls=set()

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            u = dict(attrs).get("href")
            if isinstance(u, str):
                self.urls.add(html.unescape(u))


def real_links(body):
    p=Hrefs()
    p.feed(body)
    return p.urls


def remote(cfg):
    return wp_request(
        normalized_base(),
        "posts/" + str(cfg.post_id) +
        "?context=edit&_fields=id,slug,status,title,link,content,modified_gmt"
    )


def prepare(cfg, post):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != cfg.post_id or post.get("slug") != cfg.slug
            or post.get("status") != "publish"):
        raise PublishError("Pinned legacy identity/status mismatch")
    url=urllib.parse.urlsplit(post.get("link") or "")
    if (url.scheme != "https" or url.hostname not in ("xfit.cz","www.xfit.cz")
            or url.username or url.password or url.port or url.query
            or url.fragment or url.path.rstrip("/") != "/" + cfg.slug):
        raise PublishError("Pinned legacy permalink has drifted")
    title=(post.get("title") or {}).get("raw") or ""
    title=html.unescape(re.sub(r"<[^>]*>", " ", title)).casefold()
    if cfg.title_term not in title:
        raise PublishError("Legacy article title/intent drifted")
    raw=(post.get("content") or {}).get("raw")
    modified=post.get("modified_gmt")
    if (not isinstance(raw,str) or len(raw)<1500
            or len(raw.encode("utf-8"))>MAX_BYTES
            or not isinstance(modified,str) or not modified):
        raise PublishError("Legacy source unavailable or out of safety bounds")
    old_links=real_links(raw)
    if cfg.target in old_links:
        if cfg.marker in raw and raw.count(cfg.marker)!=1:
            raise PublishError("Repeated link-release marker")
        return {"mode":"already_linked","before":raw,"after":raw,
                "hash":digest(raw),"modified":modified}
    if cfg.marker in raw:
        raise PublishError("Partial link release; exact anchor missing")
    if (cfg.paragraph.count(cfg.target)!=1 or cfg.paragraph.count(cfg.marker)!=1
            or "<script" in cfg.paragraph.casefold()
            or "<iframe" in cfg.paragraph.casefold()
            or "onclick=" in cfg.paragraph.casefold()):
        raise PublishError("Unreviewed or unsafe inlink paragraph")
    updated=raw+"\n"+cfg.paragraph
    a,b=Inspector(),Inspector()
    a.feed(raw)
    b.feed(updated)
    if (a.headers!=b.headers or a.images!=b.images
            or b.links!=a.links+[(cfg.target,"")]):
        raise PublishError("Legacy article non-target elements changed")
    if real_links(updated)!=(old_links | {cfg.target}):
        raise PublishError("New link set does not match reviewed source")
    return {"mode":"update","before":raw,"after":updated,
            "hash":digest(raw),"modified":modified}


def snapshot(cfg):
    state=prepare(cfg, remote(cfg))
    cfg.backup.parent.mkdir(parents=True,exist_ok=True)
    if cfg.backup.exists():
        raise PublishError("Prewrite backup path already exists")
    cfg.backup.write_text(json.dumps({
        "schema":1,"post_id":cfg.post_id,"slug":cfg.slug,
        "target":cfg.target,"proposal_sha":digest(cfg.paragraph),
        "mode":state["mode"],"before_sha":state["hash"],
        "after_sha":digest(state["after"]),"modified":state["modified"],
        "original_raw":state["before"],"remote_writes":0,
    },ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"state":"VERIFIED_INLINK_BACKUP_READY",
                      "post_id":cfg.post_id,
                      "write_needed":state["mode"]=="update",
                      "remote_writes":0}))


def public_verified(cfg, *, reader=None):
    def accepted(body):
        if not isinstance(body,str) or cfg.target not in real_links(body):
            return False
        visible=" ".join(html.unescape(re.sub(r"<[^>]*>"," ",body)).split())
        return (cfg.sentence in visible
                and "tento odkaz není doporučení" in visible)
    if reader is not None:
        return accepted(reader(cfg.url))
    for attempt in range(3):
        req=urllib.request.Request(cfg.url,headers={
            "User-Agent":"XFITVerifiedInlinkReadback/1.0",
            "Cache-Control":"no-cache","Pragma":"no-cache"})
        try:
            with urllib.request.urlopen(req,timeout=25) as response:
                final=urllib.parse.urlsplit(response.geturl())
                if (response.status!=200 or final.scheme!="https"
                        or final.hostname not in ("xfit.cz","www.xfit.cz")
                        or final.username or final.password or final.port
                        or final.query or final.fragment
                        or final.path.rstrip("/")!="/"+cfg.slug):
                    raise PublishError("Public URL identity changed")
                data=response.read(2_000_001)
                if len(data)>2_000_000:
                    raise PublishError("Public readback exceeded byte limit")
                if accepted(data.decode("utf-8",errors="replace")):
                    return True
        except (OSError,ValueError):
            if attempt==2:
                raise PublishError("Public source unavailable")
        if attempt<2:
            time.sleep(3)
    return False


def apply(cfg):
    if not cfg.backup.exists():
        raise PublishError("Missing mandatory prewrite backup")
    state=prepare(cfg,remote(cfg))
    backup=json.loads(cfg.backup.read_text(encoding="utf-8"))
    if (backup.get("schema")!=1
            or backup.get("post_id")!=cfg.post_id
            or backup.get("slug")!=cfg.slug
            or backup.get("target")!=cfg.target
            or backup.get("proposal_sha")!=digest(cfg.paragraph)
            or backup.get("remote_writes")!=0
            or backup.get("mode")!=state["mode"]
            or backup.get("before_sha")!=state["hash"]
            or backup.get("original_raw")!=state["before"]
            or backup.get("modified")!=state["modified"]
            or backup.get("after_sha")!=digest(state["after"])):
        raise PublishError("Live legacy body modified since source backup")
    if state["mode"]=="already_linked":
        if not public_verified(cfg):
            raise PublishError("Already-linked source not publicly confirmed")
        print(json.dumps({"state":"ALREADY_LINKED_NO_WRITE",
                          "post_id":cfg.post_id,"url":cfg.url,
                          "post_attempts":0,"public_site_modified":False}))
        return

    # One POST only. If transport times out it may already be committed.
    uncertain=False
    try:
        response=wp_request(normalized_base(),"posts/"+str(cfg.post_id),
                            payload={"content":state["after"]})
        if (not isinstance(response,dict) or response.get("id")!=cfg.post_id
                or response.get("status")!="publish"):
            uncertain=True
    except (PublishError,OSError,ValueError,TypeError):
        uncertain=True
    try:
        post=remote(cfg)
        if (post.get("id")!=cfg.post_id or post.get("slug")!=cfg.slug
                or post.get("status")!="publish"):
            raise PublishError("Post-write identity drift")
        raw=(post.get("content") or {}).get("raw")
        result_sha=digest(raw) if isinstance(raw,str) else None
    except (PublishError,OSError,ValueError,TypeError,AttributeError):
        print(json.dumps({"state":"BLOCKED_MANUAL_REVIEW",
                          "post_id":cfg.post_id,"readback_unknown":True,
                          "write_response_uncertain":uncertain}))
        raise PublishError("No safe post-write retry")
    if result_sha!=digest(state["after"]):
        print(json.dumps({"state":"UNRESOLVED_OR_DRIFTED",
                          "post_id":cfg.post_id,"post_attempts":1,
                          "content_unchanged":result_sha==state["hash"]}))
        raise PublishError("Exact authenticated content not confirmed")
    if not public_verified(cfg):
        print(json.dumps({"state":"API_VERIFIED_PUBLIC_STALE",
                          "post_id":cfg.post_id,"post_attempts":1}))
        raise PublishError("Public revised article not confirmed")
    print(json.dumps({"state":"PUBLIC_VERIFIED","post_id":cfg.post_id,
                      "url":cfg.url,"post_attempts":1,
                      "posts_changed":1,"new_posts":0,
                      "public_site_modified":True}))


def main():
    if len(sys.argv)!=3 or sys.argv[1] not in ALLOWLIST or sys.argv[2] not in (
            "snapshot","apply"):
        raise PublishError("Usage: <preapproved-key> snapshot|apply")
    cfg=ALLOWLIST[sys.argv[1]]
    (snapshot if sys.argv[2]=="snapshot" else apply)(cfg)


if __name__=="__main__":
    try:
        main()
    except (PublishError,OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
        print("XFIT_VERIFIED_INLINK_RELEASE_ERROR: "+type(exc).__name__,
              file=sys.stderr)
        raise SystemExit(2)
