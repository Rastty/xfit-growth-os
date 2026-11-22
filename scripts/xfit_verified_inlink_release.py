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
    before_heading: str | None = None
    before_first_h2: bool = False

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

_PRICE_BUYER_10854 = Handoff(
    key="creatine_buyer_10854",
    post_id=10854,
    slug="navod-jak-vybrat-nejlevnejsi-a-zaroven-ucinny-kreatin-pro-fitness",
    title_term="kreatin",
    target=_PRICE_URL,
    marker="xfit-creatine-buyer-10854-20261115",
    sentence="Co porovnat před nákupem kreatinu",
    paragraph=(
        '<p data-xfit-handoff="xfit-creatine-buyer-10854-20261115">'
        '<strong>Co porovnat před nákupem kreatinu?</strong> '
        'Vedle marketingových slibů je užitečné ověřit složení na etiketě, '
        'velikost balení, cenu za 100 g prášku a částku včetně dopravy. '
        '<a href="' + _PRICE_URL + '">Poradce pro výběr kreatinu monohydrátu</a> '
        'porovnává konkrétní katalogové nabídky podle ceny a gramáže. '
        'Nejde o srovnání všech obchodů ani o záruku účinku výrobku; '
        'ceny a dostupnost ověřte u prodejce. Pokud doplněk nepotřebujete, '
        'není důvod ho kupovat – tento odkaz není doporučení k nákupu.</p>'
    ),
)

_PRICE_BUYER_10738 = Handoff(
    key="creatine_buyer_10738",
    post_id=10738,
    slug="4-jak-nakoupit-nejlevnejsi-kreatin-pro-optimalni-vykon-ve-fitness",
    title_term="kreatin",
    target=_PRICE_URL,
    marker="xfit-creatine-buyer-10738-20261115",
    sentence="Nejlevnější balení nemusí být nejvýhodnější na gramáž",
    paragraph=(
        '<p data-xfit-handoff="xfit-creatine-buyer-10738-20261115">'
        '<strong>Nejlevnější balení nemusí být nejvýhodnější na gramáž.</strong> '
        'Malé balení může znamenat nižší útratu dnes, ale vyšší cenu '
        'za 100 g prášku. V '
        '<a href="' + _PRICE_URL + '">srovnání cen kreatinu</a> '
        'proto najdete obě možnosti vedle sebe na konkrétních nabídkách '
        'kreatinu monohydrátu. Připočítejte dopravu a před nákupem '
        'si zkontrolujte složení i dostupnost přímo v obchodě. '
        'Výběr není zárukou nejnižší ceny na trhu a '
        'tento odkaz není doporučení doplněk koupit.</p>'
    ),
)

_WHEY_TRAINING_7363 = Handoff(
    key="whey_training_7363",
    post_id=7363,
    slug="proteiny-na-svaly-a-jejich-ucinnost-pri-cviceni",
    title_term="proteiny",
    target="https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",
    marker="xfit-whey-training-7363-20261115",
    sentence="Když chcete vybrat syrovátkový protein podle etikety",
    paragraph=(
        '<p data-xfit-handoff="xfit-whey-training-7363-20261115">'
        '<strong>Když chcete vybrat syrovátkový protein podle etikety:</strong> '
        'nejprve zvažte, kolik bílkovin získáte běžnou stravou. '
        'Pokud se rozhodnete pro doplněk, sledujte obsah bílkovin na 100 g, '
        'hmotnost balení, cenu za 100 g prášku a celkovou útratu. '
        '<a href="https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/">'
        'Praktické srovnání syrovátkových proteinů</a> ukazuje '
        'konkrétní katalogové nabídky; gramáž prášku nezaměňuje '
        'za gramáž čistých bílkovin. Cenu a složení ověřte na etiketě '
        'a v obchodě. Ani tento odkaz není doporučení doplněk koupit.</p>'
    ),
)
_CREATINE_SELECTION_9772 = Handoff(
    key="creatine_selection_9772",
    post_id=9772,
    slug="nejlepsi-kreatin-monohydrat-jak-vybrat-a-efektivne-vyuzit-pro-posileni-svalu-fitness-tajemstvi",
    title_term="kreatin",
    target=_PRICE_URL,
    marker="xfit-creatine-selection-9772-20261115",
    sentence="Jak srovnat konkrétní balení kreatinu monohydrátu",
    paragraph=(
        '<p data-xfit-handoff="xfit-creatine-selection-9772-20261115">'
        '<strong>Jak srovnat konkrétní balení kreatinu monohydrátu?</strong> '
        'Při výběru čtěte složení na etiketě a porovnávejte cenu '
        'za 100 g prášku, velikost balení i dopravu. '
        '<a href="' + _PRICE_URL + '">Praktický poradce pro porovnání kreatinu</a> '
        'pracuje s vybranými katalogovými nabídkami a rozlišuje cenu '
        'balení od ceny za gramáž. Nepokrývá celý trh a nezaručuje '
        'účinek ani nejnižší cenu. Dostupnost a údaje o výrobku '
        'vždy ověřte přímo u prodejce; tento odkaz není doporučení '
        'doplněk koupit.</p>'
    ),
)
_WHEY_SNACKS_7195 = Handoff(
    key="whey_snacks_7195",
    post_id=7195,
    slug="jaky-typ-proteinu-si-vybrat-pro-pripravu-proteinovych-snacku-a-napoju",
    title_term="protein",
    target="https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",
    marker="xfit-whey-snacks-7195-20261115",
    sentence="Co sledovat při výběru syrovátkového proteinu do nápojů",
    paragraph=(
        '<p data-xfit-handoff="xfit-whey-snacks-7195-20261115">'
        '<strong>Co sledovat při výběru syrovátkového proteinu do nápojů?</strong> '
        'Před rozhodnutím zkontrolujte na etiketě obsah bílkovin '
        'na 100 g, alergeny, složení a doporučení výrobce k použití. '
        '<a href="https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/">'
        'Srovnání konkrétních syrovátkových proteinů</a> ukazuje '
        'hmotnost balení a katalogové ceny; nejde o test chuti, '
        'rozpustnosti ani vhodnosti do každého receptu. '
        'Cenu a dostupnost si ověřte v obchodě. '
        'Bílkoviny lze získat i běžnou stravou; '
        'tento odkaz není doporučení doplněk koupit.</p>'
    ),
)
_LACTOSE_INLINK_25451 = Handoff(
    key="protein_lactose_25451",
    post_id=25451,
    slug="xfit-os-protein-guide",
    title_term="protein",
    target="https://xfit.cz/xfit-os-protein-bez-laktozy/",
    marker="xfit-protein-lactose-25451-20261121",
    sentence="Když řešíte protein a laktózu, nepleťte si intoleranci s alergií",
    before_heading="<h3>Hydrolyzát</h3>",
    paragraph=(
        '<p data-xfit-handoff="xfit-protein-lactose-25451-20261121">'
        '<strong>Když řešíte protein a laktózu, nepleťte si intoleranci s alergií.</strong> '
        'Syrovátkový izolát sám o sobě nezaručuje nulový obsah laktózy '
        'a při alergii na mléčnou bílkovinu není bezpečnou náhradou. '
        'Před porovnáváním produktů proto doporučujeme '
        '<a href="https://xfit.cz/xfit-os-protein-bez-laktozy/">'
        'průvodce výběrem proteinu při intoleranci laktózy a mléčné alergii</a>. '
        'Vysvětluje rozdíl mezi oběma situacemi a co ověřit na konkrétní '
        'etiketě; pokud bílkoviny pokryjete jídlem, prášek nepotřebujete. '
        'tento odkaz není doporučení k nákupu.</p>'
    ),
)

_PLANT_INLINK_25451 = Handoff(
    key="protein_plant_25451",
    post_id=25451,
    slug="xfit-os-protein-guide",
    title_term="protein",
    target="https://xfit.cz/xfit-os-jak-vybrat-rostlinny-protein/",
    marker="xfit-protein-plant-25451-20261122",
    sentence="Sójový, hrachový, rýžový, nebo rostlinná směs",
    # End of an already source-verified dedicated plant-protein section.
    # Never insert above the entire protein guide or into unrelated advice.
    before_heading="<h2>3. Jak poznat skutečně výhodnou cenu</h2>",
    paragraph=(
        '<p data-xfit-handoff="xfit-protein-plant-25451-20261122">'
        '<strong>Sójový, hrachový, rýžový, nebo rostlinná směs?</strong> '
        'Rozdílné druhy prášku mají různé složení a marketingový název '
        'sám o sobě nestačí. Praktický '
        '<a href="https://xfit.cz/xfit-os-jak-vybrat-rostlinny-protein/">'
        'návod k výběru rostlinného proteinu podle etikety a ceny</a> '
        'ukazuje, jak ověřit deklarované bílkoviny na 100 g, seznam '
        'složek, alergeny a cenu za stejné množství skutečných bílkovin. '
        'Rostlinný původ automaticky nezaručuje nepřítomnost alergenů '
        'ani kvalitu konkrétního výrobku. Pokud máte dost bílkovin '
        'z běžného jídla, nemusíte žádný prášek kupovat. '
        'tento odkaz není doporučení k nákupu.</p>'
    ),
)


_BEGINNER_PLANT_25458 = Handoff(
    key="beginner_plant_25458",
    post_id=25458,
    slug="xfit-os-doplnky-pro-zacatecniky",
    title_term="doplňky",
    target="https://xfit.cz/xfit-os-jak-vybrat-rostlinny-protein/",
    marker="xfit-beginner-plant-choice-25458-20261122",
    sentence="Hledáte rostlinný protein místo syrovátky",
    # Immediately after the already published decision strip, not at article end.
    before_heading='<h2 id="zacatecnik-rozhodnuti">',
    paragraph=(
        '<p data-xfit-handoff="xfit-beginner-plant-choice-25458-20261122">'
        '<strong>Hledáte rostlinný protein místo syrovátky?</strong> '
        'První volba „Hledám protein“ vede na srovnání syrovátkových výrobků. '
        'Pokud se stravujete vegansky nebo je pro vás mléčná bílkovina nevhodná, '
        '<a href="https://xfit.cz/xfit-os-jak-vybrat-rostlinny-protein/">'
        'podívejte se na výběr rostlinného proteinu podle etikety, alergenů '
        'a ceny za skutečné bílkoviny</a>. Rostlinný původ sám o sobě '
        'nezaručuje nepřítomnost alergenů. Pokud potřebné bílkoviny získáte '
        'běžným jídlem, prášek nepotřebujete; tento odkaz není doporučení '
        'doplněk koupit.</p>'
    ),
)


_CREATINE_PROTEIN_VEGAN_25504 = Handoff(
    key="creatine_protein_vegan_25504",
    post_id=25504,
    slug="xfit-os-kreatin-nebo-protein",
    title_term="kreatin",
    target="https://xfit.cz/xfit-os-jak-vybrat-rostlinny-protein/",
    marker="xfit-creatine-protein-vegan-25504-20261122",
    sentence="Rostlinný protein místo syrovátky",
    # Unique reviewed end of the existing vegan decision <details> block.
    # Insert an entire paragraph BEFORE its closing </details> and only there,
    # preserving all other first-screen choice routes and source markup.
    before_heading=(
        '</details>\n\n'
        '<details><summary><strong>Mám nemocné ledviny'
    ),
    paragraph=(
        '<p data-xfit-handoff="xfit-creatine-protein-vegan-25504-20261122">'
        '<strong>Rostlinný protein místo syrovátky?</strong> '
        'Jestli vám běžné potraviny na doplnění bílkovin nestačí a '
        'vyhýbáte se mléčné bílkovině, projděte si '
        '<a href="https://xfit.cz/xfit-os-jak-vybrat-rostlinny-protein/">'
        'průvodce výběrem rostlinného proteinu podle etikety, alergenů '
        'a ceny</a>. Rostlinný původ není zárukou absence všech alergenů; '
        'složení konkrétního výrobku vždy ověřte. Pokud vám běžné jídlo '
        'stačí, prášek nepotřebujete a tento odkaz není doporučení '
        'doplněk koupit.</p>'
    ),
)


# Reviewed 11,789-article archive on 2026-11-22 found a strong, old,
# exact-title buyer-intent source with no link in its article body to the
# already-live decision guide. 1 existing article, no new post/product.
_CREATINE_PROTEIN_JOINT_4763 = Handoff(
    key="creatine_protein_joint_4763",
    post_id=4763,
    slug="je-vhodne-uzivat-kreatin-a-protein-spolecne-pri-cviceni",
    title_term="kreatin",
    target="https://xfit.cz/xfit-os-kreatin-nebo-protein/",
    marker="xfit-joint-creatine-protein-chooser-20261122",
    sentence="Potřebujete kreatin, protein, oba, nebo ani jeden",
    paragraph=(
        '<p data-xfit-handoff="xfit-joint-creatine-protein-chooser-20261122">'
        '<strong>Potřebujete kreatin, protein, oba, nebo ani jeden?</strong> '
        'Nejdřív rozlište běžný příjem bílkovin, silový trénink a '
        'cíl při opakovaném krátkém intenzivním výkonu. '
        'Proteinový prášek není nutný, když máte dostatek bílkovin ze stravy; '
        'kreatin nenahrazuje pravidelný trénink. '
        '<a href="https://xfit.cz/xfit-os-kreatin-nebo-protein/">'
        'Projít krátký rozhodovací rozcestník podle situace a cíle</a>. '
        'Můžete v něm zvolit i nekoupit nic; tento odkaz není doporučení '
        'doplněk koupit.</p>'
    ),
    before_first_h2=True,
)


ALLOWLIST = {
    _CREATINE_PROTEIN_JOINT_4763.key: _CREATINE_PROTEIN_JOINT_4763,
    _CREATINE_PROTEIN_VEGAN_25504.key: _CREATINE_PROTEIN_VEGAN_25504,
    _BEGINNER_PLANT_25458.key: _BEGINNER_PLANT_25458,
    _LACTOSE_INLINK_25451.key: _LACTOSE_INLINK_25451,
    _PLANT_INLINK_25451.key: _PLANT_INLINK_25451,
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
    ),
    _PRICE_BUYER_10854.key: _PRICE_BUYER_10854,
    _PRICE_BUYER_10738.key: _PRICE_BUYER_10738,
    _WHEY_TRAINING_7363.key: _WHEY_TRAINING_7363,
    _CREATINE_SELECTION_9772.key: _CREATINE_SELECTION_9772,
    _WHEY_SNACKS_7195.key: _WHEY_SNACKS_7195,
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
    if cfg.before_heading is not None and cfg.before_first_h2:
        raise PublishError("Only one reviewed insertion mode may be selected")
    if cfg.before_heading is not None:
        # Contextual handoff must appear beside its reviewed topic, not at
        # the end of a long guide. Exact single-heading match only.
        if raw.count(cfg.before_heading) != 1:
            raise PublishError("Reviewed topical insertion heading drifted")
        updated = raw.replace(cfg.before_heading,
                              cfg.paragraph + "\n" + cfg.before_heading, 1)
    elif cfg.before_first_h2:
        # Reader-facing decision route near the beginning, not after years of
        # historical promotional blocks. Require a true H2 inside a bounded
        # initial source span and sufficient topic evidence before inserting.
        # Do not infer a unique heading from a source that changed structure.
        intro = raw[:10000]
        headings = list(re.finditer(r"<h2(?:\s+[^>]*)?>", intro, re.I))
        if not headings or not re.search(r"kreatin|creatin", intro, re.I) or not re.search(
                r"protein", intro, re.I):
            raise PublishError("Reviewed early topic/H2 insertion anchor unavailable")
        first_h2 = headings[0].start()
        updated = raw[:first_h2] + cfg.paragraph + "\n" + raw[first_h2:]
    else:
        updated = raw + "\n" + cfg.paragraph
    a,b=Inspector(),Inspector()
    a.feed(raw)
    b.feed(updated)
    if (a.headers!=b.headers or a.images!=b.images
            or b.links.count((cfg.target,"")) != 1
            or [link for link in b.links if link != (cfg.target,"")] != a.links):
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
