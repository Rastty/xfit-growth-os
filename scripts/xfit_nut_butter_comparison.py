"""One-time, feed-bound plant protein comparison. No overwrite of existing posts."""
import argparse
import html
import json
import os
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, urlencode

from scripts.xfit_select import select_offers, choose_price_scenarios, nut_butter, mass_grams
from scripts.xfit_creatine_guide import build_tracked_url, safe_image
from scripts.xfit_catalog_retrieval import verified_catalog_fetch_time, catalog_retrieval_notice
from scripts.xfit_budget_choices import money
from scripts.xfit_availability import delivery_note
from scripts.xfit_editorial_gate import check_document
from scripts.wp_publish import (
    MARKER, PublishError, normalized_base, wp_request, validate_document,
    publish, verify_public, editorial_links, article_visible,
)

SLUG = "xfit-os-orechova-masla-porovnani"
URL = "https://xfit.cz/" + SLUG + "/"
CATALOG = Path("reports/private-greenmedical-catalog.json")
PREPARED = Path("reports/private-nut-butter-comparison.json")


def shortlist(catalog, base, sample):
    if catalog.get("merchant") != "namaximum.cz" or catalog.get("merchant_match") is not True:
        raise PublishError("Nut butter comparison requires verified merchant catalog")
    candidates = select_offers(catalog, "nut_butter", max_price=1000, min_mass_g=100, limit=None)
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
        raise PublishError("Not enough distinct source-verified nut butter families")
    # Keep one representative per family by unit price, then preserve the
    # cheapest initial purchase even if it is another size of that family.
    family = lambda item: urlsplit(item["source_url"]).path.rstrip("/")
    rank = lambda item: (item["price_per_100g_powder_czk"], item["price_czk"], item["title"], item["id"])
    by_family = {}
    for item in sorted(rows,key=rank):
        by_family.setdefault(family(item),item)
    chosen = sorted(by_family.values(), key=rank)[:6]
    upfront = min(rows,key=lambda x:(x["price_czk"],x["price_per_100g_powder_czk"],x["id"]))
    if upfront not in chosen:
        if len(chosen)<6:
            chosen.append(upfront)
        else:
            chosen[-1]=upfront
        chosen.sort(key=rank)
    if len({family(x) for x in chosen})<2:
        raise PublishError("Too few distinct families")
    cheapest = chosen.index(upfront)
    parts = [
        '<p><strong>Hledáte arašídové, mandlové nebo jiné ořechové máslo do kaše, na pečivo či do receptu?</strong> Pokud máte doma vyhovující surovinu, novou nepotřebujete. Nejdříve vyberte podle chuti a složení, až potom porovnejte cenu a velikost balení. <a href="#xfit-nut-offers" style="display:inline-block;padding:12px 0;">Přejít na aktuální nabídky</a>.</p>',
        catalog_retrieval_notice(catalog),
        '<p><strong>Rozsah:</strong> katalogové nabídky do 1 000 Kč za balení od jednoho prodejce NaMaximum.cz. Cena za 100 g celého výrobku není cena za 100 g ořechů ani bílkovin. Úplné složení, alergeny a podíl hlavní suroviny ověřte na etiketě. Doprava není zahrnuta.</p>',
        '<h2>Rychlé cenové rozhodnutí</h2>',
        '<p>Nejnižší cena za 100 g v katalogovém výběru: <a href="#xfit-nut-offer-1">'+html.escape(chosen[0]["title"])+'</a> — '+money(chosen[0]["price_per_100g_powder_czk"])+'. Nejnižší jednorázová útrata: <a href="#xfit-nut-offer-'+str(cheapest+1)+'">'+html.escape(upfront["title"])+'</a> — '+money(upfront["price_czk"])+'. Různé receptury nejsou automaticky zaměnitelné; nejde o žebříček kvality.</p>',
        '<h2 id="xfit-nut-offers">Ořechová másla: balení a ceny</h2>',
        '<p>Partnerské odkazy: Xfit.cz může získat provizi z nákupu. Výběr je omezený na jednoho prodejce; žádný výrobek jsme fyzicky netestovali. Ověřte konkrétní variantu a etiketu, zejména při alergii na arašídy či skořápkové plody.</p>',
    ]
    for n,item in enumerate(chosen,start=1):
        title=html.escape(item["title"])
        attr=html.escape(item["title"],quote=True)
        pic=('<p><img src="'+html.escape(item["image"],quote=True)+'" alt="'+attr+'" loading="lazy" width="120" height="120" style="max-width:100%;object-fit:contain;" /></p>' if item["image"] else "")
        parts.append('<article class="xfit-product-card" id="xfit-nut-offer-'+str(n)+'" style="border:1px solid #dce5e8;border-radius:12px;padding:16px;margin:16px 0;overflow-wrap:anywhere;">'
            '<h3>'+title+'</h3>'+pic+
            '<p><strong>'+money(item["price_czk"])+'</strong> za balení '+str(item["mass_g"])+' g.</p>'
            '<p><strong>'+money(item["price_per_100g_powder_czk"])+'</strong> za 100 g výrobku.</p>'
            '<p>'+delivery_note(item)+'</p>'
            '<p><small>Partnerský odkaz · Xfit.cz může získat provizi · NaMaximum.cz · nová karta.</small></p>'
            '<p><a href="'+html.escape(item["affiliate_url"],quote=True)+'" rel="sponsored nofollow noopener noreferrer" target="_blank" aria-label="Ověřit cenu a etiketu: '+attr+' (nová karta)" style="display:inline-block;min-height:44px;box-sizing:border-box;padding:12px 16px;background-color:#116a70;color:#ffffff;border-radius:8px;font-weight:700;">Ověřit cenu a etiketu</a></p></article>')
    parts += [
        '<h2>Jak vybrat složení podle využití</h2>',
        '<ul><li><strong>Do kaše nebo receptu:</strong> ověřte konzistenci a složení. Hladké a křupavé varianty mají odlišnou strukturu, ne automaticky odlišnou výživovou hodnotu.</li><li><strong>Samotná pomazánka:</strong> pokud chcete konkrétní hlavní surovinu bez dalších přísad, hledejte její podíl a úplný seznam složek. Údaj „100 %“ posuzujte podle skutečné etikety.</li><li><strong>Ochucená varianta:</strong> zkontrolujte přidaný cukr, oleje a další suroviny. Nesrovnávejte různé receptury jen podle ceny.</li></ul>',
        '<p>Ořechové máslo není přímá náhrada proteinového prášku. Porovnejte deklarované živiny na 100 g podle svého jídelníčku. Arašídy a jednotlivé druhy skořápkových plodů patří mezi alergeny uváděné v pravidlech EU; u alergie nespoléhejte na název či naši cenu. Ověřte také případné upozornění na křížový kontakt.</p>',
        '<h2>Malé balení nebo zásoba?</h2>',
        '<p>Modelově: 250 g za 100 Kč vychází na 40 Kč za 100 g, zatímco 500 g za 170 Kč na 34 Kč za 100 g. Druhá možnost je levnější na jednotku, ale zaplatíte o 70 Kč více. Pokud větší balení nespotřebujete, výhoda se může ztratit. Čísla jsou příklad výpočtu, nikoli aktuální nabídka. Přičtěte dopravu a podívejte se na podmínky skladování po otevření.</p>',
        '<h2>Co ověřit před objednávkou</h2>',
        '<ol><li>Vyberte konkrétní surovinu a recepturu; zkontrolujte podíl hlavní suroviny, přísady a alergeny.</li><li>Potvrďte čistou hmotnost zvolené varianty, datum trvanlivosti a skladování.</li><li>Porovnejte konečnou cenu včetně dopravy, ne jen katalogovou cenu.</li><li>Pokud máte doma vhodnou surovinu nebo nepotřebujete další balení, nekupujte nic.</li></ol>',
        '<p>Pravidla pro údaje o potravinách a alergenech vysvětluje <a href="https://food.ec.europa.eu/food-safety/labelling-and-nutrition/food-information-consumers-legislation_en">Evropská komise – informace o potravinách pro spotřebitele</a>. Pro jiný účel využijte <a href="https://xfit.cz/xfit-os-protein-guide/">průvodce výběrem proteinu</a>.</p>',
        '<h2>Metodika výběru</h2>',
        '<p>Pracujeme s čerstvým XML. Vyžadujeme výslovný druh másla v názvu, odpovídající katalogovou kategorii, jednoznačnou hmotnost a přesný produktový odkaz. Nejasná balení, konfliktní identifikátory a známé nedostupné položky vyřazujeme. Z rodiny obvykle zobrazujeme variantu s nejnižší cenou za 100 g, zachováváme také nejnižší jednorázovou útratu. Není to laboratorní test, kontrola skutečného skladu ani srovnání všech obchodů.</p>',
    ]
    doc={"slug":SLUG,"title":"Ořechová a arašídová másla: srovnání cen a balení",
         "excerpt":"Ořechová másla podle skutečných katalogových cen, velikosti balení a ceny za 100 g. Rozhodnutí podle složení a alergenů.",
         "content":"\n".join(parts)}
    check_document(doc,commercial=True)
    return doc


def prepare():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    base, sample = os.getenv("XFIT_AFFIL_DEFAULT_LINK", ""), os.getenv("XFIT_AFFIL_SAMPLE_PRODUCT_LINK", "")
    rows, families = shortlist(catalog, base, sample)
    matches = [item for item in catalog["products"] if nut_butter(item)]
    print(json.dumps({"state": "NUT_BUTTER_SOURCE_COVERAGE", "title_category_matches": len(matches),
                      "unambiguous_title_mass": sum(mass_grams(item["title"]) is not None for item in matches),
                      "eligible_offer_variants": len(rows), "distinct_product_families": families,
                      "actual_stock_verified": False, "wordpress_writes": 0}))
    if families < 2:
        raise PublishError("No two comparable nut butter product families; no publication")
    doc = build_document(catalog, base, sample)
    PREPARED.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "NUT_BUTTER_COMPARISON_PREPARED", "cards": check_document(doc)["product_cards"],
                      "wordpress_writes": 0}))


def apply():
    # Build once using the same actual feed; validate age again before POST.
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    source = json.loads(PREPARED.read_text(encoding="utf-8"))
    expected = build_document(catalog, os.environ["XFIT_AFFIL_DEFAULT_LINK"], os.environ["XFIT_AFFIL_SAMPLE_PRODUCT_LINK"])
    if source != expected:
        raise PublishError("Prepared nut butter document drifted")
    doc = validate_document(source)
    base = normalized_base()
    matches = wp_request(base, "posts?" + urlencode({"slug": SLUG, "context": "edit", "status": "any", "per_page": 10,
                    "_fields": "id,slug,status,content,link,title"}))
    if not isinstance(matches, list) or len(matches) > 1:
        raise PublishError("Unexpected nut butter slug lookup")
    if matches:
        post = matches[0]
        raw = (post.get("content") or {}).get("raw", "")
        if (post.get("slug") != SLUG or post.get("status") != "publish"
                or post.get("link") != URL or not isinstance(raw, str) or MARKER not in raw
                or article_visible(raw)[0] != article_visible(doc["content"])[0]
                or editorial_links(raw) != editorial_links(doc["content"])):
            raise PublishError("Existing nut butter post differs; no rewrite or automatic retry")
        verify_public(URL, doc["title"], doc["content"])
        print(json.dumps({"state": "unchanged_public_verified", "post_id": post["id"], "slug": SLUG,
                          "url": URL, "public_site_modified": False}))
        return
    result = publish(doc, live=True, new_only=True)
    if result.get("state") != "live_verified" or result.get("url") != URL or result.get("slug") != SLUG:
        raise PublishError("Nut butter permalink or release proof mismatch; no retry")
    # Verify exact authenticated affiliate hrefs as well as visible body.
    post = wp_request(base, "posts/" + str(result["post_id"]) + "?context=edit&_fields=id,slug,status,content")
    raw = (post.get("content") or {}).get("raw")
    if post.get("id") != result["post_id"] or post.get("slug") != SLUG or not isinstance(raw, str) or editorial_links(raw) != editorial_links(doc["content"]):
        raise PublishError("Nut butter authenticated destination readback mismatch")
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
        print("XFIT_NUT_BUTTER_RELEASE_BLOCKED: " + type(exc).__name__)
        raise SystemExit(2)
