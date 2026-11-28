"""Catalog-bound fitness equipment offers; distinct purposes, no inferred specifications."""
import argparse
import html
import json
import os
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit, urlencode
from scripts.xfit_select import folded, MAX_FULL_CATALOG_SCAN
from scripts.xfit_feed_ingest import catalog_identity_matches_url
from scripts.xfit_creatine_guide import build_tracked_url, safe_image
from scripts.xfit_catalog_retrieval import verified_catalog_fetch_time, catalog_retrieval_notice
from scripts.xfit_budget_choices import money
from scripts.xfit_availability import delivery_state, delivery_note
from scripts.xfit_editorial_gate import check_document
from scripts.wp_publish import (
    MARKER, PublishError, normalized_base, wp_request, validate_document,
    publish, verify_public, editorial_links, article_visible,
)

SLUG = "xfit-os-vybaveni-na-domaci-cviceni-nabidky"
URL = "https://xfit.cz/" + SLUG + "/"
CATALOG = Path("reports/private-greenmedical-catalog.json")
PREPARED = Path("reports/private-equipment-comparison.json")
GROUPS = {
    "mat": ("Podložky na cvičení", "xfit-os-vyber-podlozky-na-cviceni",
            "Ověřte délku, šířku, tloušťku a povrch. Ne každá podložka se hodí pro dynamický pohyb nebo odkládání závaží."),
    "band": ("Odporové gumy", "xfit-os-vyber-odporove-gumy",
             "Ověřte tvar, délku, rozsah odporu při uvedeném natažení a způsob uchycení. Barva není jednotnou stupnicí mezi výrobci."),
    "ball": ("Gymnastické míče (fitball)", None,
             "Vybírejte rozměr podle zamýšleného pohybu, návodu a skutečných rozměrů. Zkontrolujte deklarované zatížení, nafukování, protiskluznost a dostatek volného prostoru. Nestabilní míč není nutný pro začátečníka."),
    "massage": ("Masážní válce a míčky v sadě", None,
                "Sada má smysl jen pokud využijete její součásti. Ověřte přesný obsah, rozměry, materiál a pokyny pro používání. Nepoužívejte bolestivý tlak ani pomůcku jako náhradu zdravotní péče."),
    "glove": ("Fitness rukavice", None,
              "Rukavice mohou změnit pocit úchopu a kontakt dlaně s náčiním. Změřte ruku podle tabulky výrobce, ověřte švy, zapínání a prodyšnost. Silnější polstrování nemusí vyhovovat každému úchopu."),
    "belt": ("Posilovací opasky", None,
             "Opasek není povinný ani náhradou techniky a přiměřené zátěže. Ověřte obvod v místě nošení podle výrobce, šířku, tuhost, zapínání a rozsah nastavení. Nevybírejte jen podle velikosti kalhot."),
    "strap": ("Trhačky na posilování", None,
              "Trhačky mohou pomoci, když úchop omezuje zamýšlený tah. Porovnejte klasický pásek a typ figure 8 podle návodu, rozměrů a možnosti bezpečně uvolnit úchop. Nejsou potřeba pro každý cvik."),
}
REQUIRED_GROUPS = ("mat", "band")
OPTIONAL_GROUPS = ("ball", "massage", "glove", "belt", "strap")
OPTIONAL_LABELS = {"ball": "Gymnastický míč", "massage": "Masážní sada",
                   "glove": "Fitness rukavice", "belt": "Posilovací opasek", "strap": "Trhačky"}
GROUP_LIMITS = {"ball": 1, "massage": 1, "glove": 2, "belt": 2, "strap": 2}
MAX_CARDS = 3 * len(REQUIRED_GROUPS) + sum(GROUP_LIMITS.values())
PRICE_LIMIT = Decimal("2000")


def equipment_kind(row):
    title = folded(row.get("title") or "")
    category = folded(row.get("category") or "")
    # Dedicated merchant category; a category alone never establishes the product type.
    category_key = " ".join(re.findall(r"[a-z0-9]+", category))
    if category_key in ("pasky trhacky rukavice bandaze", "pasy trhacky rukavice bandaze",
                         "pasky trhacky rukavice a bandaze"):
        if re.search(r"\b(?:nahradn\w*|replacement|repair|pouzdro|obal|detsk\w*|kids|junior)\b", title):
            return None
        matches = []
        if re.search(r"\b(?:fitness rukavic\w*|rukavic\w* (?:na|pro) (?:cvicen\w*|posilovan\w*))\b", title):
            matches.append("glove")
        if re.search(r"\b(?:fitness opasek|fitness opask\w*|powerliftersk\w* opasek|posilovac\w* opasek|vzp[eě]racsk\w* opasek)\b", title):
            matches.append("belt")
        if re.search(r"\btrhack\w*\b", title):
            matches.append("strap")
        return matches[0] if len(matches) == 1 else None
    if not any(term in category for term in ("pomucky pro cviceni", "treninkove prislusenstvi",
                    "podlozk", "expand", "posilovaci gum", "odporove gum", "fitness pomucky",
                    "pomocky na cvicenie", "treningove prislusenstvo")):
        return None
    # Exact optional types from the reviewed merchant category. Do not treat
    # a fitball as a resistance band, or a massage set as a yoga mat.
    if re.search(r"\b(?:nahradn\w*|replacement|repair|drzak\w*|pouzdro|obal|obaly|pump\w*|ventil\w*|kniha|trhac\w*|bandaz\w*|bandage|stahovac\w*|opasek|protein\w*)\b", title):
        return None
    if "pomucky pro cviceni" in category or "pomocky na cvicenie" in category:
        ball = bool(re.search(r"\bfitball\s+[0-9]{2,3}\s*cm\b", title))
        massage = bool(re.search(r"\bmasazni sada muscle ball and roller set\b", title))
        if ball and not massage and not re.search(r"\b(?:mat|band|podlozk\w*|gum\w*)\b", title):
            return "ball"
        if massage and not ball and not re.search(r"\b(?:mat|band|podlozk\w*|gum\w*)\b", title):
            return "massage"
    if re.search(r"\b(?:masaz\w*|massage|roller|podlozk\w* pod|ochrann\w* podlozk\w*|"
                 r"nahradn\w*|replacement|repair|drzak\w*|pouzdro|obal|obaly|"
                 r"kniha|trhac\w*|bandaz\w*|bandage|stahovac\w*|opasek|protein\w*)\b", title):
        return None
    mat = bool(re.search(r"\b(?:yoga mat|exercise mat|fitness mat|pilates mat|"
                         r"podlozk\w* (?:na|pro) cvicen\w*|cvicic\w* podlozk\w*|"
                         r"jog\w* podlozk\w*|karimatk\w*)\b", title))
    band = bool(re.search(r"\b(?:posilovac\w* gum\w*|odporov\w* gum\w*|"
                          r"resistance band\w*|power band\w*|booty band\w*|"
                          r"mini ?band\w*|rezistencn\w* pas\w*|expander\w*)\b", title))
    return "mat" if mat and not band else "band" if band and not mat else None


def shortlist(catalog, base, sample):
    if catalog.get("merchant") != "namaximum.cz" or catalog.get("merchant_match") is not True:
        raise PublishError("Equipment comparison requires verified merchant")
    items = catalog.get("products")
    if not isinstance(items, list) or len(items) > MAX_FULL_CATALOG_SCAN:
        raise PublishError("Unexpected catalog inventory")
    # Resolve duplicate identities before applying price or availability limits.
    # Contradictory variants cannot be silently promoted as the cheapest deal.
    records, identities = [], defaultdict(list)
    for row in items:
        kind = equipment_kind(row)
        if not kind:
            continue
        pid, url, ean = row.get("id"), row.get("source_url"), row.get("ean") or ""
        if row.get("merchant") != "NaMaximum.cz" or not isinstance(url, str):
            continue
        try:
            if not catalog_identity_matches_url(pid, url):
                continue
            affiliate = build_tracked_url(url, base, sample)
            if isinstance(row.get("price_czk"), bool):
                continue
            price = Decimal(str(row["price_czk"]))
            if not price.is_finite() or not 0 < price <= 1000000 or price != price.quantize(Decimal("0.01")):
                continue
        except (ValueError, PublishError, InvalidOperation, KeyError, TypeError):
            continue
        state = delivery_state(row)
        candidate = {"id": pid, "title": row["title"], "source_url": url,
                     "ean": ean, "price": price, "kind": kind, "affiliate_url": affiliate,
                     "image": safe_image(row.get("image_url") or ""), "availability_state": state}
        for field in ("id", "ean", "source_url"):
            if candidate[field]:
                identities[(field, candidate[field])].append(len(records))
        records.append(candidate)
    bad = set()
    for indices in identities.values():
        signatures = {(records[i]["id"], records[i]["ean"], records[i]["source_url"],
                       records[i]["price"], records[i]["title"], records[i]["kind"],
                       records[i]["availability_state"]) for i in indices}
        if len(signatures) > 1:
            bad.update(indices)
    grouped = {kind: {} for kind in GROUPS}
    for i, row in enumerate(records):
        if i in bad or row["price"] > PRICE_LIMIT or row["availability_state"] not in (
                "feed_stocked", "up_to_week", "unknown"):
            continue
        family = urlsplit(row["source_url"]).path.rstrip("/")
        prior = grouped[row["kind"]].get(family)
        if prior is None or (row["price"], row["id"]) < (prior["price"], prior["id"]):
            grouped[row["kind"]][family] = row
    return {kind: sorted(rows.values(), key=lambda r: (r["price"], r["title"], r["id"]))
            for kind, rows in grouped.items()}


BUDGET_MARKER = 'id="xfit-gear-budget-v1"'
NAV_MARKER = 'id="xfit-equipment-nav-v2"'
LEGACY_NAV = '<nav aria-label="Výběr vybavení"><ul><li><a href="#xfit-gear-mat" style="display:inline-block;padding:12px 0;">Potřebuji podložku</a></li><li><a href="#xfit-gear-band" style="display:inline-block;padding:12px 0;">Potřebuji odporovou gumu</a></li></ul></nav>'
LEGACY_INTRO = '<p><strong>Co opravdu potřebujete pro domácí cvičení?</strong> Podložka řeší kontakt se zemí a odporová guma umožňuje přidat odpor. Není nutné kupovat obě věci najednou. Pokud vám vyhovuje stávající vybavení, nekupujte nic. Zvolte nejprve účel a až potom nabídku podle ceny.</p>'
INTRO = '<p><strong>Co opravdu potřebujete pro domácí cvičení nebo silový trénink?</strong> Vyberte si konkrétní účel a přejděte k aktuálním cenám. Základní podložka a odporová guma, pomůcky pro regeneraci nebo silové příslušenství řeší odlišné potřeby. Pokud vám vyhovuje stávající vybavení, nekupujte nic. Nabídky jednotlivých skupin se aktualizují podle katalogu.</p>'
NAV_LABELS = {"mat": "Podložky", "band": "Odporové gumy", "ball": "Gymnastické míče",
              "massage": "Masážní sady", "glove": "Fitness rukavice", "belt": "Opasky", "strap": "Trhačky"}


def equipment_nav(groups):
    links = ['<a href="#xfit-gear-'+kind+'" style="display:inline-flex;align-items:center;min-height:44px;box-sizing:border-box;padding:8px 12px;border:1px solid #cdded7;border-radius:8px;color:#115e59;font-weight:600;max-width:100%;overflow-wrap:anywhere;">'+NAV_LABELS[kind]+'</a>' for kind in GROUPS if groups.get(kind)]
    return ('<nav '+NAV_MARKER+' aria-label="Aktuální kategorie vybavení" style="margin:12px 0 16px;">'
            '<p><strong>Rychlý výběr podle potřeby</strong></p>'
            '<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:stretch;">'+''.join(links)+
            '</div><p><a href="#xfit-gear-budget-v1" style="display:inline-block;min-height:44px;box-sizing:border-box;padding:12px 0;">Porovnat ceny a rozpočet včetně možnosti nic nekoupit</a></p></nav>')

def budget_block(groups):
    mat, band = groups["mat"][0], groups["band"][0]
    total = mat["price"] + band["price"]
    optional = "".join(
        '<p><a href="#xfit-gear-'+kind+'" style="display:block;min-height:44px;box-sizing:border-box;padding:10px 0">'
        '<strong>'+OPTIONAL_LABELS[kind]+': od '+money(groups[kind][0]["price"])+'</strong> – volitelná pomůcka</a></p>'
        for kind in OPTIONAL_GROUPS if groups.get(kind)
    )
    return ('<section '+BUDGET_MARKER+' aria-label="Rozpočet na domácí cvičení" style="border:1px solid #cdded7;border-radius:12px;padding:14px;margin:16px 0;background:#f6faf8;overflow-wrap:anywhere">'
        '<h2>Kolik stojí základní vybavení na domácí cvičení?</h2>'
        '<p>Vyberte jen to, co vám chybí. Níže jsou nejnižší ceny způsobilých katalogových nabídek v jednotlivých skupinách, nikoli doporučení kvality.</p>'
        '<p><strong>0 Kč – využiji vlastní vybavení.</strong> Pokud mi vyhovuje, nic dalšího nepotřebuji.</p>'
        '<p><a href="#xfit-gear-mat" style="display:block;min-height:44px;box-sizing:border-box;padding:10px 0"><strong>Jen podložka: '+money(mat["price"])+'</strong> – přejít na nabídku</a></p>'
        '<p><a href="#xfit-gear-band" style="display:block;min-height:44px;box-sizing:border-box;padding:10px 0"><strong>Jen odporová guma: '+money(band["price"])+'</strong> – přejít na nabídku</a></p>'
        '<p><strong>Podložka + guma: '+money(total)+'</strong> (součet nejnižších cen obou skupin, ne cena akčního setu).</p>'
        + optional + '<p><small>Ceny bez dopravy a poplatků, pouze z jednoho prodejce. Ověřte parametry a cenu konkrétní varianty v košíku. Pokud nejlevnější varianta nevyhovuje vašemu pohybu, není pro vás výhodná.</small></p></section>')


def build_document(catalog, base, sample):
    groups = shortlist(catalog, base, sample)
    if any(not groups[kind] for kind in REQUIRED_GROUPS):
        raise PublishError("Both equipment purposes must have genuine eligible products")
    parts = [
        INTRO,
        catalog_retrieval_notice(catalog),
        equipment_nav(groups),
        '<p><strong>Rozsah a cena:</strong> katalogové nabídky do 2 000 Kč za nabízenou variantu od jediného prodejce NaMaximum.cz; nejde o srovnání celého trhu. Neznáme skutečné rozměry, odpor, počet kusů ani materiál, pokud nejsou v názvu. Cena je za katalogovou nabídku, nikoli nutně za jeden kus, a nezahrnuje dopravu. Seřazení uvnitř skupiny je podle ceny, ne kvality, bezpečnosti nebo provize.</p>',
        '<h2>Jak rozhodnout, za co utratit peníze</h2>',
        '<ul><li><strong>Cvičíte na zemi:</strong> nejdřív řešte prostor, povrch a rozměry podložky.</li><li><strong>Potřebujete přidat odpor:</strong> zvažte typ gumy podle pohybu, délky a bezpečného použití podle návodu.</li><li><strong>Obojí:</strong> ověřte, že každou pomůcku skutečně využijete. Nekupujte set jen kvůli slevě nebo dopravě zdarma.</li></ul>',
    ]
    parts.append(budget_block(groups))
    n = 0
    for kind, (heading, guide, caution) in GROUPS.items():
        if not groups[kind]:
            continue
        guide_link = (' <a href="https://xfit.cz/' + guide + '/">Podrobný návod k výběru</a>.') if guide else ""
        if kind in ("glove", "belt", "strap"):
            guide_link = ' <a href="#xfit-strength-accessory-guide-v1">Podrobný průvodce velikostí a výběrem</a>.'
        parts += [
            '<h2 id="xfit-gear-' + kind + '">' + heading + ' – aktuální nabídky</h2>',
            '<p>' + caution + guide_link + '</p>',
        ]
        for item in groups[kind][:GROUP_LIMITS.get(kind, 3)]:
            n += 1
            title = html.escape(item["title"])
            attr = html.escape(item["title"], quote=True)
            pic = ('<p><img src="' + html.escape(item["image"], quote=True) + '" alt="' + attr +
                   '" loading="lazy" width="120" height="120" style="max-width:100%;object-fit:contain;" /></p>'
                   if item["image"] else "")
            parts.append(
                '<article class="xfit-product-card" id="xfit-gear-offer-' + str(n) +
                '" style="border:1px solid #dce5e8;border-radius:12px;padding:16px;margin:16px 0;overflow-wrap:anywhere;">'
                '<h3>' + title + '</h3>' + pic +
                '<p><strong>Cena nabídky: ' + money(item["price"]) + '</strong> (bez dopravy a poplatků).</p>'
                '<p>' + delivery_note(item) + '</p>'
                '<p><small>Partnerský odkaz · Xfit.cz může získat provizi · NaMaximum.cz · nová karta.</small></p>'
                '<p><a href="' + html.escape(item["affiliate_url"], quote=True) +
                '" rel="sponsored nofollow noopener noreferrer" target="_blank" aria-label="Ověřit variantu a cenu: ' + attr +
                ' (nová karta)" style="display:inline-block;min-height:44px;box-sizing:border-box;padding:12px 16px;'
                'background-color:#116a70;color:#ffffff;border-radius:8px;font-weight:700;">Ověřit variantu a cenu</a></p></article>'
            )
    parts += [
        '<h2>Co zkontrolovat v obchodě před objednávkou</h2>',
        '<ol><li>Změřte místo, kde budete cvičit, a zvažte místo pro uložení vybavení.</li><li>U podložky zkontrolujte skutečné rozměry, materiál, stabilitu na konkrétním povrchu a pokyny pro údržbu.</li><li>U gumy zkontrolujte tvar, délku, materiál, deklarovaný rozsah odporu a povolený způsob uchycení. Neodvozujte odpor z barvy ani z ceny.</li><li>Ověřte přesný počet kusů v balení, konečnou cenu v košíku, dopravu a podmínky vrácení. Pokud prodejce důležité údaje neuvádí, výběr odložte.</li><li>Používejte vybavení pouze v souladu s návodem výrobce; poškozené součásti nepoužívejte.</li></ol>',
        '<p>Další pomůcky vybírejte až podle konkrétní potřeby: <a href="https://xfit.cz/xfit-os-vyber-jednorucek-na-doma/">jednoruční činky pro domácnost</a> nebo <a href="https://xfit.cz/xfit-os-vyber-hrazdy-do-dveri/">hrazda do dveří</a>. Pro obecné informace o bezpečnosti spotřebitelských výrobků slouží <a href="https://commission.europa.eu/topics/business-and-industry/product-safety_en">Evropská komise – bezpečnost výrobků</a>.</p>',
        '<h2>Metodika výběru</h2>',
        '<p>Pracujeme s čerstvě načteným XML katalogem a přesnými produktovými variantami. Vyřazujeme nejasné nebo konfliktní identifikátory a ceny, výslovně nedostupné nabídky, předobjednávky a katalogovou expedici přes sedm dní. Z každé produktové rodiny uvádíme nejlevnější způsobilou variantu; jiné varianty mohou mít rozdílné parametry. Nabídky různých typů nepovažujeme za zaměnitelné. Neprováděli jsme vlastní fyzické testování pomůcek. Zobrazený stav katalogu nepotvrzuje skutečný sklad ani bezpečnost konkrétního výrobku.</p>',
    ]
    doc = {"slug": SLUG, "title": "Vybavení na domácí cvičení: nabídky podložek a odporových gum",
           "excerpt": "Aktuální katalogové nabídky domácích podložek a odporových gum, cena podle varianty, výběr podle účelu a rozměrů.",
           "content": "\n".join(parts)}
    check_document(doc, commercial=True)
    return doc


def prepare():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    base, sample = os.environ["XFIT_AFFIL_DEFAULT_LINK"], os.environ["XFIT_AFFIL_SAMPLE_PRODUCT_LINK"]
    groups = shortlist(catalog, base, sample)
    print(json.dumps({"state": "EQUIPMENT_SOURCE_COVERAGE", "eligible_families":
                      {kind: len(rows) for kind, rows in groups.items()},
                      "actual_stock_verified": False, "wordpress_writes": 0}))
    doc = build_document(catalog, base, sample)
    PREPARED.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "EQUIPMENT_COMPARISON_PREPARED", "cards": check_document(doc)["product_cards"],
                      "wordpress_writes": 0}))


def apply():
    # Build once using the same actual feed; validate age again before POST.
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    source = json.loads(PREPARED.read_text(encoding="utf-8"))
    expected = build_document(catalog, os.environ["XFIT_AFFIL_DEFAULT_LINK"], os.environ["XFIT_AFFIL_SAMPLE_PRODUCT_LINK"])
    if source != expected:
        raise PublishError("Prepared equipment document drifted")
    doc = validate_document(source)
    base = normalized_base()
    matches = wp_request(base, "posts?" + urlencode({"slug": SLUG, "context": "edit", "status": "any", "per_page": 10,
                    "_fields": "id,slug,status,content,link,title"}))
    if not isinstance(matches, list) or len(matches) > 1:
        raise PublishError("Unexpected equipment slug lookup")
    if matches:
        post = matches[0]
        raw = (post.get("content") or {}).get("raw", "")
        if (post.get("slug") != SLUG or post.get("status") != "publish"
                or post.get("link") != URL or not isinstance(raw, str) or MARKER not in raw
                or article_visible(raw)[0] != article_visible(doc["content"])[0]
                or editorial_links(raw) != editorial_links(doc["content"])):
            raise PublishError("Existing equipment post differs; no rewrite or automatic retry")
        verify_public(URL, doc["title"], doc["content"])
        print(json.dumps({"state": "unchanged_public_verified", "post_id": post["id"], "slug": SLUG,
                          "url": URL, "public_site_modified": False}))
        return
    result = publish(doc, live=True, new_only=True)
    if result.get("state") != "live_verified" or result.get("url") != URL or result.get("slug") != SLUG:
        raise PublishError("Equipment permalink or release proof mismatch; no retry")
    # Verify exact authenticated affiliate hrefs as well as visible body.
    post = wp_request(base, "posts/" + str(result["post_id"]) + "?context=edit&_fields=id,slug,status,content")
    raw = (post.get("content") or {}).get("raw")
    if post.get("id") != result["post_id"] or post.get("slug") != SLUG or not isinstance(raw, str) or editorial_links(raw) != editorial_links(doc["content"]):
        raise PublishError("Equipment authenticated destination readback mismatch")
    print(json.dumps({"state": "PUBLIC_VERIFIED_NEW_POST", "post_id": result["post_id"], "slug": SLUG,
                      "url": URL, "new_posts": 1, "public_site_modified": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=("prepare", "apply"))
    args = parser.parse_args()
    try:
        (prepare if args.step == "prepare" else apply)()
    except (PublishError, ValueError, OSError, KeyError) as exc:
        # Never echo URLs or private feed rows.
        print("XFIT_EQUIPMENT_RELEASE_BLOCKED: " + type(exc).__name__)
        raise SystemExit(2)
