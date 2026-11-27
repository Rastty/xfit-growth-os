"""One-time, feed-bound plant protein comparison. No overwrite of existing posts."""
import argparse
import html
import json
import os
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, urlencode

from scripts.xfit_select import select_offers, choose_price_scenarios, plant_powder, mass_grams
from scripts.xfit_creatine_guide import build_tracked_url, safe_image
from scripts.xfit_catalog_retrieval import verified_catalog_fetch_time, catalog_retrieval_notice
from scripts.xfit_budget_choices import money
from scripts.xfit_availability import delivery_note
from scripts.xfit_editorial_gate import check_document
from scripts.wp_publish import (
    MARKER, PublishError, normalized_base, wp_request, validate_document,
    publish, verify_public, editorial_links, article_visible,
)

SLUG = "xfit-os-rostlinne-proteiny-porovnani"
URL = "https://xfit.cz/" + SLUG + "/"
CATALOG = Path("reports/private-greenmedical-catalog.json")
PREPARED = Path("reports/private-plant-comparison.json")


def shortlist(catalog, base, sample):
    if catalog.get("merchant") != "namaximum.cz" or catalog.get("merchant_match") is not True:
        raise PublishError("Plant comparison requires verified merchant catalog")
    candidates = select_offers(catalog, "plant_protein", max_price=2000, min_mass_g=100, limit=None)
    source = {}
    for item in catalog["products"]:
        source.setdefault(item.get("id"), item)
    grouped = {}
    for row in candidates:
        try:
            link = build_tracked_url(row["source_url"], base, sample)
        except (ValueError, PublishError):
            continue
        key = (urlsplit(row["source_url"]).path.rstrip("/"), row["mass_g"])
        candidate = {**row, "affiliate_url": link,
                     "image": safe_image(source[row["id"]].get("image_url") or "")}
        prior = grouped.get(key)
        if prior is None or (row["price_czk"], row["id"]) < (prior["price_czk"], prior["id"]):
            grouped[key] = candidate
    rows = list(grouped.values())
    # No claims of actual stock, protein percentage, purity or dairy-free status.
    # Require at least two different merchant product paths, not just flavors/sizes.
    families = {urlsplit(row["source_url"]).path.rstrip("/") for row in rows}
    return rows, len(families)


def build_document(catalog, base, sample):
    rows, families = shortlist(catalog, base, sample)
    if families < 2:
        raise PublishError("Not enough distinct source-verified plant protein families")
    chosen, _, upfront = choose_price_scenarios(rows, limit=6)
    # Preserve a second product family if top price-ranked packs are all one family.
    family = lambda item: urlsplit(item["source_url"]).path.rstrip("/")
    if len({family(item) for item in chosen}) < 2:
        other = min((item for item in rows if family(item) != family(chosen[0])),
                    key=lambda item: (item["price_per_100g_powder_czk"], item["price_czk"], item["id"]))
        replace_at = next(i for i in reversed(range(len(chosen))) if i not in (0, upfront))
        chosen[replace_at] = other
        chosen.sort(key=lambda item: (item["price_per_100g_powder_czk"], item["price_czk"], item["title"], item["id"]))
    cheapest = min(range(len(chosen)), key=lambda i: (chosen[i]["price_czk"], chosen[i]["price_per_100g_powder_czk"], i))
    parts = [
        '<p><strong>Hledáte rostlinný protein za rozumnou cenu?</strong> Pokud potřebné bílkoviny získáváte z běžného jídla, prášek nemusíte kupovat. Pokud vám usnadní přípravu jídla, nejdřív zkontrolujte složení a alergeny, potom cenu konkrétního balení. <a href="#xfit-plant-offers" style="display:inline-block;padding:12px 0;">Přejít na aktuální nabídky</a>.</p>',
        catalog_retrieval_notice(catalog),
        '<p><strong>Rozsah:</strong> porovnáváme jen omezený výběr NaMaximum.cz z ověřeného XML katalogu. Názvy naznačují rostlinný původ, ale samy nedokládají kompletní složení ani nepřítomnost mléka či jiných alergenů. Cena za 100 g prášku není cena za 100 g skutečných bílkovin. Cena dopravy není zahrnuta.</p>',
        '<h2>Rychlé cenové rozhodnutí</h2>',
        '<p>Nejnižší cena za 100 g prášku ve výběru: <a href="#xfit-plant-offer-1">' + html.escape(chosen[0]["title"]) + '</a> — ' + money(chosen[0]["price_per_100g_powder_czk"]) + '. Nejnižší jednorázová útrata: <a href="#xfit-plant-offer-' + str(cheapest+1) + '">' + html.escape(chosen[cheapest]["title"]) + '</a> — ' + money(chosen[cheapest]["price_czk"]) + ' za balení. Pořadí neurčuje provize ani slibovaná účinnost.</p>',
        '<h2 id="xfit-plant-offers">Rostlinné proteiny: balení a ceny</h2>',
        '<p>Partnerské odkazy: Xfit.cz může získat provizi z nákupu. Výběr je omezený na jednoho prodejce a není nezávislým testem kvality. U každé nabídky ověřte přesnou variantu, aktuální cenu, složení a dostupnost u prodejce.</p>',
    ]
    for n, item in enumerate(chosen, start=1):
        title = html.escape(item["title"])
        attr = html.escape(item["title"], quote=True)
        img = ('<p><img src="' + html.escape(item["image"], quote=True) + '" alt="' + attr +
               '" loading="lazy" width="120" height="120" style="max-width:100%;object-fit:contain;" /></p>'
               if item["image"] else "")
        parts.append(
            '<article class="xfit-product-card" id="xfit-plant-offer-' + str(n) +
            '" style="border:1px solid #dce5e8;border-radius:12px;padding:16px;margin:16px 0;overflow-wrap:anywhere;">'
            '<h3>' + title + '</h3>' + img +
            '<p><strong>' + money(item["price_czk"]) + '</strong> za balení ' + str(item["mass_g"]) + ' g.</p>'
            '<p><strong>' + money(item["price_per_100g_powder_czk"]) + '</strong> za 100 g prášku.</p>'
            '<p>' + delivery_note(item) + '</p>'
            '<p><small>Partnerský odkaz · Xfit.cz může získat provizi · NaMaximum.cz · nová karta.</small></p>'
            '<p><a href="' + html.escape(item["affiliate_url"], quote=True) +
            '" rel="sponsored nofollow noopener noreferrer" target="_blank" aria-label="Ověřit cenu a etiketu: ' +
            attr + ' (nová karta)" style="display:inline-block;min-height:44px;box-sizing:border-box;padding:12px 16px;'
            'background-color:#116a70;color:#ffffff;border-radius:8px;font-weight:700;">Ověřit cenu a etiketu</a></p></article>'
        )
    parts += [
        '<h2>Jak vybrat konkrétní zdroj bílkovin</h2>',
        '<p>Sója, hrách, rýže a směsi jsou různé zdroje, nikoli automaticky zaměnitelné výrobky. Začněte u surovin uvedených na etiketě, nikoli u slova „vegan“ v názvu. Při výběru porovnejte obsah bílkovin na 100 g samotného prášku, příchuť, úplné složení a případné alergeny. Samotný rostlinný název neprokazuje vhodnost při potravinové alergii.</p>',
        '<p>Pokud si nejste jistí, zda bude prášek vyhovovat při běžné přípravě, může být menší balení praktičtější i při vyšší ceně na 100 g. Nekupujte zásobu jen proto, že má výhodnější přepočet. U zcela rozdílných výrobků porovnávejte cenu až po kontrole, že oba odpovídají vašemu účelu.</p>',
        '<h2>Co zjistit ještě před objednávkou</h2>',
        '<ol><li>Ověřte hmotnost vybrané varianty, nikoli jen nejnižší cenu uvedenou u rodiny produktů.</li>'
        '<li>Najděte bílkoviny na 100 g prášku a spočítejte cenu za stejné množství bílkovin podle <a href="https://xfit.cz/xfit-os-cena-proteinu-podle-etikety/">návodu s modelovými výpočty</a>.</li>'
        '<li>Přečtěte úplné složení i zvýrazněné alergeny. Zvláště při alergii nespoléhejte na název nebo naši cenovou tabulku.</li>'
        '<li>V košíku zkontrolujte dopravu, poplatky a konečnou cenu. Pokud přesahuje rozpočet, nákup odložte.</li>'
        '<li>Pokud běžná strava stačí, není potřeba objednávat nic.</li></ol>',
        '<p>Rozdíly mezi typy proteinů vysvětluje <a href="https://xfit.cz/xfit-os-protein-guide/">hlavní průvodce proteinem</a>. K orientaci v deklarovaných údajích a alergenech slouží <a href="https://food.ec.europa.eu/food-safety/labelling-and-nutrition/food-information-consumers-legislation_en">evropská pravidla označování potravin</a>. Sportovní kontext poskytuje <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC5477153/">stanovisko ISSN o bílkovinách a cvičení</a>. Při zdravotních omezeních řešte výběr individuálně s odborníkem.</p>',
        '<h2>Jak vzniká srovnání</h2>',
        '<p>Z katalogu vybíráme produkty s výslovným rostlinným proteinovým názvem, známou gramáží a cenou, bez nejednoznačných multipacků či zjevných mléčných směsí. Vyřazujeme známé nedostupné produkty, předobjednávky a zpožděnou expedici přes sedm dní. Chybějící údaje o skladu přiznáváme. U různých příchutí stejné gramáže a produktové rodiny uvádíme nejlevnější ověřenou variantu. Údaje z feedu nejsou laboratorní test ani živá skladová kontrola. Naše výpočty jsou orientační cenovou pomůckou, nikoli doporučeným množstvím k jídlu.</p>',
    ]
    doc = {"slug": SLUG, "title": "Srovnání rostlinných proteinů: ceny a velikosti balení",
           "excerpt": "Výběr rostlinných proteinů z reálného katalogu NaMaximum podle ceny balení a 100 g prášku; kontrola etikety a možnost nic nekoupit.",
           "content": "\n".join(parts)}
    check_document(doc, commercial=True)
    return doc


def prepare():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    base, sample = os.getenv("XFIT_AFFIL_DEFAULT_LINK", ""), os.getenv("XFIT_AFFIL_SAMPLE_PRODUCT_LINK", "")
    rows, families = shortlist(catalog, base, sample)
    matches = [item for item in catalog["products"] if plant_powder(item)]
    print(json.dumps({"state": "PLANT_SOURCE_COVERAGE", "title_category_matches": len(matches),
                      "unambiguous_title_mass": sum(mass_grams(item["title"]) is not None for item in matches),
                      "eligible_offer_variants": len(rows), "distinct_product_families": families,
                      "actual_stock_verified": False, "wordpress_writes": 0}))
    if families < 2:
        raise PublishError("No two comparable plant product families; no publication")
    doc = build_document(catalog, base, sample)
    PREPARED.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "PLANT_COMPARISON_PREPARED", "cards": check_document(doc)["product_cards"],
                      "wordpress_writes": 0}))


def apply():
    # Build once using the same actual feed; validate age again before POST.
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    source = json.loads(PREPARED.read_text(encoding="utf-8"))
    expected = build_document(catalog, os.environ["XFIT_AFFIL_DEFAULT_LINK"], os.environ["XFIT_AFFIL_SAMPLE_PRODUCT_LINK"])
    if source != expected:
        raise PublishError("Prepared plant document drifted")
    doc = validate_document(source)
    base = normalized_base()
    matches = wp_request(base, "posts?" + urlencode({"slug": SLUG, "context": "edit", "status": "any", "per_page": 10,
                    "_fields": "id,slug,status,content,link,title"}))
    if not isinstance(matches, list) or len(matches) > 1:
        raise PublishError("Unexpected plant slug lookup")
    if matches:
        post = matches[0]
        raw = (post.get("content") or {}).get("raw", "")
        if (post.get("slug") != SLUG or post.get("status") != "publish"
                or post.get("link") != URL or not isinstance(raw, str) or MARKER not in raw
                or article_visible(raw)[0] != article_visible(doc["content"])[0]
                or editorial_links(raw) != editorial_links(doc["content"])):
            raise PublishError("Existing plant post differs; no rewrite or automatic retry")
        verify_public(URL, doc["title"], doc["content"])
        print(json.dumps({"state": "unchanged_public_verified", "post_id": post["id"], "slug": SLUG,
                          "url": URL, "public_site_modified": False}))
        return
    result = publish(doc, live=True, new_only=True)
    if result.get("state") != "live_verified" or result.get("url") != URL or result.get("slug") != SLUG:
        raise PublishError("Plant permalink or release proof mismatch; no retry")
    # Verify exact authenticated affiliate hrefs as well as visible body.
    post = wp_request(base, "posts/" + str(result["post_id"]) + "?context=edit&_fields=id,slug,status,content")
    raw = (post.get("content") or {}).get("raw")
    if post.get("id") != result["post_id"] or post.get("slug") != SLUG or not isinstance(raw, str) or editorial_links(raw) != editorial_links(doc["content"]):
        raise PublishError("Plant authenticated destination readback mismatch")
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
        print("XFIT_PLANT_RELEASE_BLOCKED: " + type(exc).__name__)
        raise SystemExit(2)
