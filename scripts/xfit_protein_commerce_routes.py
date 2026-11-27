"""Two independently source-bound protein decision routes, never a new article."""
from dataclasses import dataclass
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
from scripts.xfit_protein_early_choices_release import panel, TARGETS
from scripts.xfit_beginner_four_lane_hub import PLANT_URL, plant_source, PLANT_TITLE
from scripts.xfit_whey_guide import SLUG as WHEY_SLUG
from scripts.xfit_affiliate_public_audit import read_public_page, read_wp_post
from scripts.wp_publish import PublishError, normalized_base, wp_request, verify_public, editorial_links, MARKER
from scripts.xfit_editorial_gate import check_document
from scripts.xfit_beginner_hub_choice_onepost import sha

WHEY_URL = "https://xfit.cz/" + WHEY_SLUG + "/"
V2_MARK = 'data-xfit-choice="protein-guide-v2"'
PRICE_MARK = 'data-xfit-choice="protein-price-offers-v1"'
PRICE_HEADING = "<h2>1. Proč nestačí porovnat cenu za kilogram prášku</h2>"
PRICE_OWNER = "xfit-ai-protein-price-real-portion-v1"


@dataclass(frozen=True)
class Scope:
    key: str
    post_id: int
    slug: str
    title_term: str
    marker: str
    targets: tuple[str, ...]

    @property
    def url(self):
        return "https://xfit.cz/" + self.slug + "/"

    @property
    def backup(self):
        return Path("reports/backups/xfit-" + self.key + "-commerce-routes.json")


SCOPES = {
    "protein-guide": Scope("protein-guide", 25451, "xfit-os-protein-guide",
        "jak vybrat protein", V2_MARK, TARGETS + (PLANT_URL,)),
    "protein-price": Scope("protein-price", 25541, "xfit-os-cena-proteinu-podle-etikety",
        "jak porovnat cenu proteinu", PRICE_MARK, (PLANT_URL,)),
}


def offer_link(url, text):
    return ('<li style="margin:0 0 10px;padding:0;"><a href="' + url +
            '" style="display:block;min-height:44px;box-sizing:border-box;padding:12px 14px;'
            'border:1px solid #b6cdd0;border-radius:8px;background:#f3f8f8;color:#164f54;'
            'font-weight:700;text-decoration:underline;overflow-wrap:anywhere;">' +
            text + '</a></li>')


def guide_panel():
    old = panel()
    new = old.replace('data-xfit-choice="protein-guide-v1"', V2_MARK, 1)
    new = new.replace("</ul>", offer_link(PLANT_URL, "4. Porovnat nabídky rostlinných proteinů")
                      + "</ul>", 1)
    new = new.replace("Poslední možnost vede na srovnání produktů s označenými ",
                      "Poslední dvě možnosti vedou na srovnání produktů s označenými ", 1)
    return new


PRICE_PANEL = (
    '<nav ' + PRICE_MARK + ' aria-label="Skutečné katalogové nabídky proteinů" '
    'style="border:1px solid #dce5e8;border-radius:12px;padding:14px;margin:18px 0;">'
    '<p><strong>Máte údaje z etikety a hledáte rostlinné proteiny?</strong> '
    'Pokud vám stačí běžné potraviny, prášek nemusíte kupovat. Vedle stávajícího syrovátkového srovnání můžete využít i rostlinný výběr:</p>'
    '<ul style="list-style:none;padding:0;margin:0;">'
    + offer_link(PLANT_URL, "Rostlinné proteiny – ceny a balení")
    + '</ul><p><small>Aktuální přehled jednoho prodejce obsahuje označené partnerské odkazy. '
    'Uvádí cenu za prášek, ne za skutečné bílkoviny. Ověřte etiketu přesné varianty, alergeny, '
    'hmotnost, dopravu a konečnou cenu v košíku. Pokud údaj chybí, nic neodhadujte.</small></p></nav>'
)


class NavLinks(HTMLParser):
    def __init__(self, marker):
        super().__init__(convert_charrefs=True)
        self.value = marker.split('"')[1]
        self.depth = 0
        self.navs = 0
        self.links = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "nav":
            if self.depth:
                self.depth += 1
            elif values.get("data-xfit-choice") == self.value:
                self.depth = 1
                self.navs += 1
        if tag == "a" and self.depth:
            self.links.append(values.get("href"))

    def handle_endtag(self, tag):
        if tag == "nav" and self.depth:
            self.depth -= 1


def proof(cfg, raw):
    if not isinstance(raw, str) or raw.count(cfg.marker) != 1:
        return False
    p = NavLinks(cfg.marker)
    p.feed(raw)
    return (p.navs == 1 and not p.depth and tuple(p.links) == cfg.targets
            and (cfg.key != "protein-price" or WHEY_URL in editorial_links(raw)))


def revise(cfg, raw):
    if not isinstance(raw, str) or not 1500 <= len(raw.encode("utf-8")) <= 450000:
        raise PublishError("Source length outside bounds")
    if cfg.marker in raw:
        if not proof(cfg, raw):
            raise PublishError("Existing route block is inconsistent")
        return raw
    old_links = editorial_links(raw)
    if cfg.key == "protein-guide":
        old = panel()
        if raw.count(old) != 1 or not raw.startswith(MARKER) or PLANT_URL in old_links:
            raise PublishError("Exact reviewed protein panel not present or target already linked")
        updated = raw.replace(old, guide_panel(), 1)
        if updated.replace(guide_panel(), old, 1) != raw:
            raise PublishError("Nonlocal protein guide change")
        additions = {PLANT_URL}
    else:
        if (raw.count(PRICE_HEADING) != 1 or raw.count(PRICE_OWNER) != 1
                or WHEY_URL not in old_links or PLANT_URL in old_links):
            raise PublishError("Expected reviewed pricing content or unique target unavailable")
        updated = raw.replace(PRICE_HEADING, PRICE_PANEL + "\n" + PRICE_HEADING, 1)
        if updated.replace(PRICE_PANEL + "\n", "", 1) != raw:
            raise PublishError("Nonlocal price guide change")
        additions = {PLANT_URL}
    if (not proof(cfg, updated)
            or set(editorial_links(updated)) != set(old_links) | additions
            or any("namaximum.cz" in url for url in editorial_links(updated))):
        raise PublishError("Unexpected routes or outbound mutation")
    check_document({"content": updated}, commercial=False)
    return updated


def read(cfg):
    post = wp_request(normalized_base(), "posts/" + str(cfg.post_id)
        + "?context=edit&_fields=id,slug,status,link,title,content,excerpt,categories,sticky,modified_gmt")
    raw = (post.get("content") or {}).get("raw")
    title = (post.get("title") or {}).get("raw")
    if (type(post.get("id")) is not int or post["id"] != cfg.post_id
            or post.get("slug") != cfg.slug or post.get("link") != cfg.url
            or post.get("status") != "publish" or not isinstance(title, str)
            or cfg.title_term not in title.casefold()
            or not isinstance(raw, str) or not isinstance(post.get("modified_gmt"), str)
            or not post["modified_gmt"]):
        raise PublishError("Pinned protein source identity changed")
    return post


def destinations():
    raw, _ = plant_source()
    verify_public(PLANT_URL, PLANT_TITLE, raw)
    post = read_wp_post(WHEY_SLUG)
    if post.get("id") != 25456 or post.get("link") != WHEY_URL or post.get("status") != "publish":
        raise PublishError("Whey destination identity changed")
    from scripts.xfit_affiliate_public_audit import Cards
    cards = Cards()
    cards.feed(read_public_page(WHEY_SLUG))
    if not 2 <= len(cards.cards) <= 6:
        raise PublishError("Whey live offers unavailable")


def snapshot(cfg):
    destinations()
    original = read(cfg)
    raw = original["content"]["raw"]
    updated = revise(cfg, raw)
    if cfg.backup.exists():
        raise PublishError("Refusing to overwrite original")
    cfg.backup.parent.mkdir(parents=True, exist_ok=True)
    cfg.backup.write_text(json.dumps({"schema": 1, "post_id": cfg.post_id, "before": original,
        "before_sha": sha(raw), "after_sha": sha(updated), "wordpress_writes": 0},
        ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "PROTEIN_ROUTES_BACKUP_READY", "post_id": cfg.post_id,
        "wordpress_writes": 0, "change_required": updated != raw}))


def apply(cfg):
    saved = json.loads(cfg.backup.read_text(encoding="utf-8"))
    before = read(cfg)
    raw = before["content"]["raw"]
    updated = revise(cfg, raw)
    if (saved.get("schema") != 1 or saved.get("post_id") != cfg.post_id
            or saved.get("wordpress_writes") != 0 or saved.get("before") != before
            or saved.get("before_sha") != sha(raw) or saved.get("after_sha") != sha(updated)):
        raise PublishError("Original source drifted after backup")
    if raw != updated:
        try:
            wp_request(normalized_base(), "posts/" + str(cfg.post_id), payload={"content": updated})
        except (PublishError, OSError, ValueError, TypeError):
            pass
        current = read(cfg)
        if (current["content"]["raw"] != updated
                or {k:v for k,v in current.items() if k not in {"content", "modified_gmt"}}
                != {k:v for k,v in before.items() if k not in {"content", "modified_gmt"}}):
            raise PublishError("Exact source and metadata not verified; no retry")
    verify_public(cfg.url, before["title"]["raw"], updated)
    if not proof(cfg, read_public_page(cfg.slug)):
        raise PublishError("Public exact protein routes unavailable")
    print(json.dumps({"state": "PUBLIC_PROTEIN_ROUTES_VERIFIED", "post_id": cfg.post_id,
        "url": cfg.url, "choices": len(cfg.targets), "post_attempts": int(raw != updated),
        "posts_changed": int(raw != updated), "new_posts": 0, "public_site_modified": raw != updated}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3 or sys.argv[1] not in SCOPES or sys.argv[2] not in {"snapshot", "apply"}:
            raise PublishError("Unsupported scope")
        (snapshot if sys.argv[2] == "snapshot" else apply)(SCOPES[sys.argv[1]])
    except (PublishError, ValueError, OSError, TypeError, KeyError) as exc:
        print("XFIT_PROTEIN_ROUTES_BLOCKED: " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)
