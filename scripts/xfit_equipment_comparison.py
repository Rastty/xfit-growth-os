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
}
PRICE_LIMIT = Decimal("2000")


def equipment_kind(row):
    title = folded(row.get("title") or "")
    category = folded(row.get("category") or "")
    if not any(term in category for term in ("pomucky pro cviceni", "treninkove prislusenstvi",
                    "podlozk", "expand", "posilovaci gum", "odporove gum", "fitness pomucky",
                    "pomocky na cvicenie", "treningove prislusenstvo")):
        return None
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


def build_document(catalog, base, sample):
    groups = shortlist(catalog, base, sample)
    if any(not groups[kind] for kind in GROUPS) or sum(map(len, groups.values())) < 2:
        raise PublishError("Both equipment purposes must have genuine eligible products")
    parts = [
        '<p><strong>Co opravdu potřebujete pro domácí cvičení?</strong> Podložka řeší kontakt se zemí a odporová guma umožňuje přidat odpor. Není nutné kupovat obě věci najednou. Pokud vám vyhovuje stávající vybavení, nekupujte nic. Zvolte nejprve účel a až potom nabídku podle ceny.</p>',
        catalog_retrieval_notice(catalog),
        '<nav aria-label="Výběr vybavení"><ul><li><a href="#xfit-gear-mat" style="display:inline-block;padding:12px 0;">Potřebuji podložku</a></li><li><a href="#xfit-gear-band" style="display:inline-block;padding:12px 0;">Potřebuji odporovou gumu</a></li></ul></nav>',
        '<p><strong>Rozsah a cena:</strong> katalogové nabídky do 2 000 Kč za nabízenou variantu od jediného prodejce NaMaximum.cz; nejde o srovnání celého trhu. Neznáme skutečné rozměry, odpor, počet kusů ani materiál, pokud nejsou v názvu. Cena je za katalogovou nabídku, nikoli nutně za jeden kus, a nezahrnuje dopravu. Seřazení uvnitř skupiny je podle ceny, ne kvality, bezpečnosti nebo provize.</p>',
        '<h2>Jak rozhodnout, za co utratit peníze</h2>',
        '<ul><li><strong>Cvičíte na zemi:</strong> nejdřív řešte prostor, povrch a rozměry podložky.</li><li><strong>Potřebujete přidat odpor:</strong> zvažte typ gumy podle pohybu, délky a bezpečného použití podle návodu.</li><li><strong>Obojí:</strong> ověřte, že každou pomůcku skutečně využijete. Nekupujte set jen kvůli slevě nebo dopravě zdarma.</li></ul>',
    ]
    n = 0
    for kind, (heading, guide, caution) in GROUPS.items():
        parts += [
            '<h2 id="xfit-gear-' + kind + '">' + heading + ' – aktuální nabídky</h2>',
            '<p>' + caution + ' <a href="https://xfit.cz/' + guide + '/">Podrobný návod k výběru</a>.</p>',
        ]
        for item in groups[kind][:3]:
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
