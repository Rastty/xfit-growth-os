"""Catalog-bound drink containers; separate mixing and carrying purposes."""
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

SLUG = "xfit-os-sejkry-a-sportovni-lahve"
URL = "https://xfit.cz/" + SLUG + "/"
CATALOG = Path("reports/private-greenmedical-catalog.json")
PREPARED = Path("reports/private-drinkware-comparison.json")
GROUPS = {
    "shaker": ("Šejkry na míchání", "Ověřte objem, uzávěr, možnost rozebrání a způsob mytí."),
    "bottle": ("Sportovní lahve", "Ověřte objem, rozměry, uzávěr a určení nádoby pro daný nápoj."),
}
PRICE_LIMIT = Decimal("1000")

def drinkware_kind(row):
    title = folded(row.get("title") or "")
    category = folded(row.get("category") or "")
    if not re.search(r"sejkr|shaker|lahv|lahev|flas|treninkov\w* prislusenstv|pomuck\w* pro cvicen",category):
        return None
    if re.search(r"\b(?:nahradn\w*|replacement|vicko|uzaver|lid|obal|obaly|cistic\w*|kartac\w*|proteinov\w* mix|balicek|napoj\w* koncentrat)\b",title):
        return None
    # Match the leading product designation, not an incidental accessory
    # mentioned in a supplement bundle or a cosmetic's packaging.
    shaker = bool(re.search(r"^(?:smart\s+)?(?:shaker\w*|sejkr\w*|sejker\w*)\b",title))
    bottle = bool(re.search(r"^(?:sportovni\s+)?(?:lahev|lahv\w*|flas\w*|bottle\w*)\b",title))
    return "shaker" if shaker and not bottle else "bottle" if bottle and not shaker else None

def shortlist(catalog, base, sample):
    if catalog.get("merchant") != "namaximum.cz" or catalog.get("merchant_match") is not True:
        raise PublishError("Drinkware comparison requires verified merchant")
    items = catalog.get("products")
    if not isinstance(items, list) or len(items) > MAX_FULL_CATALOG_SCAN:
        raise PublishError("Unexpected catalog inventory")
    # Resolve duplicate identities before applying price or availability limits.
    # Contradictory variants cannot be silently promoted as the cheapest deal.
    records, identities = [], defaultdict(list)
    for row in items:
        kind = drinkware_kind(row)
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
    groups=shortlist(catalog,base,sample)
    if len(groups["shaker"]) < 2 or not groups["bottle"]:
        raise PublishError("Need distinct real shaker families and one bottle")
    parts=[
        '<p><strong>Šejkr potřebujete hlavně k rozmíchání prášku; sportovní láhev k přenášení nápoje.</strong> Pokud doma máte funkční nádobu, která vám vyhovuje a je určená pro kontakt s potravinami, nekupujte novou. Vyberte nejprve účel a teprve potom cenu a provedení.</p>',
        catalog_retrieval_notice(catalog),
        '<nav aria-label="Výběr nádoby"><ul><li><a href="#xfit-drink-shaker" style="display:inline-block;padding:12px 0">Chci míchat protein</a></li><li><a href="#xfit-drink-bottle" style="display:inline-block;padding:12px 0">Chci přenášet nápoj</a></li></ul></nav>',
        '<p><strong>Rozsah:</strong> katalogové nabídky do 1 000 Kč od jednoho prodejce NaMaximum.cz. Cena za nabízenou variantu, ne nutně za jeden kus; bez dopravy a poplatků. Srovnáváme cenu uvnitř účelu, ne kvalitu ani těsnost. Materiál, přesný objem a použití v myčce neodvozujeme z názvu ani fotografie.</p>',
        '<h2>Jak vybrat nádobu podle využití</h2>',
        '<ul><li><strong>Míchání:</strong> zkontrolujte, zda vám vyhovuje způsob míchání a zda lze všechny části vyčistit podle návodu.</li><li><strong>Přenášení:</strong> ověřte rozměry, způsob uzavření a určení pro konkrétní nápoj; těsnost není zaručena cenou.</li><li><strong>Doplňky:</strong> úložné přihrádky mají smysl jen tehdy, když je opravdu potřebujete. Z názvu vícedílného modelu nelze automaticky odvodit objem pro nápoj.</li></ul>',
    ]
    n=0
    for kind,(heading,caution) in GROUPS.items():
        parts += ['<h2 id="xfit-drink-'+kind+'">'+heading+' – aktuální nabídky</h2>','<p>'+caution+'</p>']
        for item in groups[kind][:5 if kind=="shaker" else 3]:
            n+=1
            title=html.escape(item["title"])
            attr=html.escape(item["title"],quote=True)
            pic=('<p><img src="'+html.escape(item["image"],quote=True)+'" alt="'+attr+'" loading="lazy" width="120" height="120" style="max-width:100%;object-fit:contain;" /></p>' if item["image"] else "")
            parts.append('<article class="xfit-product-card" id="xfit-drink-offer-'+str(n)+'" style="border:1px solid #dce5e8;border-radius:12px;padding:16px;margin:16px 0;overflow-wrap:anywhere;">'
                '<h3>'+title+'</h3>'+pic+
                '<p><strong>Cena nabídky: '+money(item["price"])+'</strong> (bez dopravy a poplatků).</p>'
                '<p>'+delivery_note(item)+'</p>'
                '<p><small>Partnerský odkaz · Xfit.cz může získat provizi · NaMaximum.cz · nová karta.</small></p>'
                '<p><a href="'+html.escape(item["affiliate_url"],quote=True)+'" rel="sponsored nofollow noopener noreferrer" target="_blank" aria-label="Ověřit variantu a cenu: '+attr+' (nová karta)" style="display:inline-block;min-height:44px;box-sizing:border-box;padding:12px 16px;background-color:#116a70;color:#ffffff;border-radius:8px;font-weight:700;">Ověřit variantu a cenu</a></p></article>')
    parts += [
        '<h2>Kolik zaplatíte při samostatné objednávce</h2>',
        '<p>U levného příslušenství může doprava změnit rozhodnutí. Modelově: nádoba za 80 Kč s dopravou za 70 Kč stojí celkem 150 Kč. Přidáte-li ji k už plánované objednávce za stejných přepravních podmínek, dodatečný náklad může být jen 80 Kč. Jde o ilustrační částky, nikoli nabídku obchodu. Nekupujte nepotřebné zboží kvůli dopravě zdarma.</p>',
        '<h2>Co zkontrolovat v obchodě před objednávkou</h2>',
        '<ol><li>Ověřte skutečný použitelný objem nádoby, počet kusů a rozměry.</li><li>Přečtěte si údaje o materiálu, kontaktu s potravinami a povoleném použití. Horké nebo sycené nápoje dávejte pouze do nádoby, jejíž výrobce takové použití dovoluje.</li><li>Zkontrolujte způsob čištění, těsnění a zda výrobce dovoluje myčku.</li><li>Porovnejte konečnou cenu v košíku a podmínky vrácení. Pokud chybí důležitá vlastnost, objednávku odložte.</li></ol>',
        '<p>Nejste-li si jistí samotným proteinem, využijte <a href="https://xfit.cz/xfit-os-protein-guide/">průvodce výběrem proteinu</a>. K obecným pravidlům bezpečnosti výrobků viz <a href="https://commission.europa.eu/topics/business-and-industry/product-safety_en">Evropská komise – bezpečnost výrobků</a>.</p>',
        '<h2>Metodika výběru</h2>',
        '<p>Vycházíme z čerstvého XML, pouze z přesných variant a z jednoho prodejce. Vyřazujeme konfliktní identity a ceny, výslovně nedostupné položky, předobjednávky a katalogovou expedici nad sedm dní. Z produktové rodiny uvádíme nejlevnější způsobilou variantu. Doložený katalogový údaj není ověření skutečného skladu ani vlastnosti výrobku. Žádné nádoby jsme fyzicky netestovali.</p>',
    ]
    doc={"slug":SLUG,"title":"Šejkry a sportovní lahve: aktuální nabídky a praktický výběr",
         "excerpt":"Jak vybrat šejkr nebo sportovní láhev, kdy nic nekupovat a aktuální katalogové ceny jednotlivých variant.",
         "content":"\n".join(parts)}
    check_document(doc,commercial=True)
    return doc

def prepare():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    base, sample = os.environ["XFIT_AFFIL_DEFAULT_LINK"], os.environ["XFIT_AFFIL_SAMPLE_PRODUCT_LINK"]
    groups = shortlist(catalog, base, sample)
    print(json.dumps({"state": "DRINKWARE_SOURCE_COVERAGE", "eligible_families":
                      {kind: len(rows) for kind, rows in groups.items()},
                      "actual_stock_verified": False, "wordpress_writes": 0}))
    doc = build_document(catalog, base, sample)
    PREPARED.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "DRINKWARE_COMPARISON_PREPARED", "cards": check_document(doc)["product_cards"],
                      "wordpress_writes": 0}))


def apply():
    # Build once using the same actual feed; validate age again before POST.
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    source = json.loads(PREPARED.read_text(encoding="utf-8"))
    expected = build_document(catalog, os.environ["XFIT_AFFIL_DEFAULT_LINK"], os.environ["XFIT_AFFIL_SAMPLE_PRODUCT_LINK"])
    if source != expected:
        raise PublishError("Prepared drinkware document drifted")
    doc = validate_document(source)
    base = normalized_base()
    matches = wp_request(base, "posts?" + urlencode({"slug": SLUG, "context": "edit", "status": "any", "per_page": 10,
                    "_fields": "id,slug,status,content,link,title"}))
    if not isinstance(matches, list) or len(matches) > 1:
        raise PublishError("Unexpected drinkware slug lookup")
    if matches:
        post = matches[0]
        raw = (post.get("content") or {}).get("raw", "")
        if (post.get("slug") != SLUG or post.get("status") != "publish"
                or post.get("link") != URL or not isinstance(raw, str) or MARKER not in raw
                or article_visible(raw)[0] != article_visible(doc["content"])[0]
                or editorial_links(raw) != editorial_links(doc["content"])):
            raise PublishError("Existing drinkware post differs; no rewrite or automatic retry")
        verify_public(URL, doc["title"], doc["content"])
        print(json.dumps({"state": "unchanged_public_verified", "post_id": post["id"], "slug": SLUG,
                          "url": URL, "public_site_modified": False}))
        return
    result = publish(doc, live=True, new_only=True)
    if result.get("state") != "live_verified" or result.get("url") != URL or result.get("slug") != SLUG:
        raise PublishError("Drinkware permalink or release proof mismatch; no retry")
    # Verify exact authenticated affiliate hrefs as well as visible body.
    post = wp_request(base, "posts/" + str(result["post_id"]) + "?context=edit&_fields=id,slug,status,content")
    raw = (post.get("content") or {}).get("raw")
    if post.get("id") != result["post_id"] or post.get("slug") != SLUG or not isinstance(raw, str) or editorial_links(raw) != editorial_links(doc["content"]):
        raise PublishError("Drinkware authenticated destination readback mismatch")
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
        print("XFIT_DRINKWARE_RELEASE_BLOCKED: " + type(exc).__name__)
        raise SystemExit(2)
