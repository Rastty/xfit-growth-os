"""Catalog-bound fitness clothing; compare explicit size variants, not inferred fit."""
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

SLUG = "xfit-os-fitness-obleceni-nabidky"
URL = "https://xfit.cz/" + SLUG + "/"
CATALOG = Path("reports/private-greenmedical-catalog.json")
PREPARED = Path("reports/private-apparel-comparison.json")
GROUPS = {
    "shirt": ("Pánská fitness trička", "Ověřte střih, materiál a tabulku rozměrů konkrétního výrobce."),
    "hoodie": ("Pánské mikiny", "Ověřte střih, tloušťku, materiál a zda chcete zip nebo provedení přes hlavu."),
    "leggings": ("Fitness legíny", "Ověřte rozměry pasu a boků, délku nohavic a možnost vrácení."),
}
PRICE_LIMIT = Decimal("2000")
SIZE = re.compile(r"(?<![\w-])(?:XXXS|XXS|XS|S|M|L|XL|XXL|XXXL|[2-5]XL)(?![\w-])")

def explicit_size(title):
    if not isinstance(title, str):
        return None
    sizes = set(SIZE.findall(title))
    return next(iter(sizes)) if len(sizes) == 1 else None

def apparel_kind(row):
    category = folded(row.get("category") or "").strip()
    title = folded(row.get("title") or "")
    kind = {"panska tricka": "shirt", "panske mikiny": "hoodie",
            "fitness leginy": "leggings"}.get(category)
    patterns = {"shirt": r"\b(?:trick\w*|trik\w*|t-shirt|tshirt|shirt)\b",
                "hoodie": r"\b(?:mikin\w*|hoodie|sweatshirt)\b",
                "leggings": r"\b(?:legin\w*|leggings)\b"}
    if not kind or not re.search(patterns[kind], title) or not explicit_size(row.get("title")):
        return None
    if re.search(r"\b(?:detske|detsky|detska|kids|junior|balicek|multipack|nahradn\w*)\b", title):
        return None
    return kind

def eligible_variants(catalog, base, sample):
    if catalog.get("merchant") != "namaximum.cz" or catalog.get("merchant_match") is not True:
        raise PublishError("Apparel comparison requires verified merchant")
    items = catalog.get("products")
    if not isinstance(items, list) or len(items) > MAX_FULL_CATALOG_SCAN:
        raise PublishError("Unexpected catalog inventory")
    # Resolve duplicate identities before applying price or availability limits.
    # Contradictory variants cannot be silently promoted as the cheapest deal.
    records, identities = [], defaultdict(list)
    for row in items:
        kind = apparel_kind(row)
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
                     "ean": ean, "price": price, "kind": kind, "size": explicit_size(row["title"]), "affiliate_url": affiliate,
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
    eligible = []
    seen = set()
    for i, row in enumerate(records):
        if i in bad or row["price"] > PRICE_LIMIT or row["availability_state"] not in (
                "feed_stocked", "up_to_week", "unknown"):
            continue
        if row["source_url"] not in seen:
            eligible.append(row)
            seen.add(row["source_url"])
    return eligible


def family_shortlist(eligible):
    grouped = {kind: {} for kind in GROUPS}
    for row in eligible:
        family = urlsplit(row["source_url"]).path.rstrip("/")
        prior = grouped[row["kind"]].get(family)
        if prior is None or (row["price"], row["id"]) < (prior["price"], prior["id"]):
            grouped[row["kind"]][family] = row
    return {kind: sorted(rows.values(), key=lambda r: (r["price"], r["title"], r["id"]))
            for kind, rows in grouped.items()}


def shortlist(catalog, base, sample):
    return family_shortlist(eligible_variants(catalog, base, sample))


SIZE_ORDER = ("XXXS", "XXS", "XS", "S", "M", "L", "XL", "XXL", "2XL", "XXXL", "3XL", "4XL", "5XL")


def size_shortlist(eligible):
    # Rank exact source variants only AFTER global identity-conflict detection.
    # Do not silently normalize 2XL and XXL: merchant labels may differ.
    grouped = {kind: {} for kind in GROUPS}
    for row in eligible:
        group = grouped[row["kind"]]
        size = row["size"]
        if size not in group or (row["price"], row["title"], row["id"]) < (
                group[size]["price"], group[size]["title"], group[size]["id"]):
            group[size] = row
    return grouped


def size_picker(kind, variants):
    if not variants:
        return ""
    rows = []
    for size in SIZE_ORDER:
        item = variants.get(size)
        if item is None:
            continue
        label = html.escape(item["title"])
        attr = html.escape(item["title"], quote=True)
        rows.append('<li style="margin:0 0 8px;padding:8px 0;border-bottom:1px solid #dce5e8;overflow-wrap:anywhere" data-xfit-size="'+size+'">'
            '<strong>'+size+' · '+money(item["price"])+'</strong><br> '+label+'<br> '
            '<small>'+delivery_note(item)+'</small><br> '
            '<a href="'+html.escape(item["affiliate_url"], quote=True)+'" rel="sponsored nofollow noopener noreferrer" target="_blank" '
            'aria-label="Ověřit velikost a cenu: '+attr+' (nová karta)" style="display:inline-block;min-height:44px;box-sizing:border-box;padding:12px 0;font-weight:700;">Ověřit tuto variantu</a></li>')
    return ('<details id="xfit-size-picker-'+kind+'" style="border:1px solid #cdded7;border-radius:10px;padding:12px;margin:12px 0;background:#f6faf8">'
        '<summary style="cursor:pointer;min-height:44px;box-sizing:border-box;padding:10px 0;font-weight:700">Vybrat podle velikosti ('+str(len(rows))+' položek)</summary>'
        '<p>'+GROUPS[kind][0]+': nejnižší katalogová cena způsobilé varianty v každé uvedené velikosti, nikoli doporučení kvality. Ceny bez dopravy. Označení velikosti ověřte v tabulce výrobce. Chybějící velikost neznamená, že ji obchod nemá.</p>'
        '<ul style="padding-left:20px">'+''.join(rows)+'</ul>'
        '<p><small>Partnerské odkazy · Xfit.cz může získat provizi · NaMaximum.cz · nová karta.</small></p></details>')


def build_document(catalog, base, sample):
    eligible=eligible_variants(catalog,base,sample)
    groups=family_shortlist(eligible)
    by_size=size_shortlist(eligible)
    if sum(bool(rows) for rows in groups.values()) < 2 or sum(map(len, groups.values())) < 3:
        raise PublishError("Need distinct real clothing families in at least two groups")
    parts=[
        '<p><strong>Tričko, mikina nebo legíny na trénink?</strong> Nejdřív rozhodněte podle toho, co ve vašem šatníku skutečně chybí, a vyberte velikost podle vlastních rozměrů. Pokud vám stávající oblečení vyhovuje, nic dalšího kupovat nemusíte.</p>',
        catalog_retrieval_notice(catalog),
        '<nav aria-label="Výběr oblečení"><ul>'+''.join('<li><a href="#xfit-apparel-'+kind+'" style="display:inline-block;padding:12px 0">'+heading+'</a></li>' for kind,(heading,_) in GROUPS.items() if groups[kind])+'</ul></nav>',
        '<p><strong>Rozsah:</strong> katalogové nabídky do 2 000 Kč za konkrétní variantu od jediného prodejce NaMaximum.cz; ceny bez dopravy a poplatků. Nejde o srovnání celého trhu ani hodnocení kvality. U každé položky uvádíme pouze velikost výslovně uvedenou v katalogovém názvu. Cena ani dostupnost jiné velikosti z této nabídky nevyplývá.</p>',
        '<h2>Jak vybrat velikost bez zbytečného vracení</h2>',
        '<ul><li><strong>Trička a mikiny:</strong> změřte obvod hrudníku a porovnejte jej s tabulkou výrobce. U mikiny počítejte i s vrstvou pod ní.</li><li><strong>Legíny:</strong> změřte pas a boky a ověřte délku. Stejné označení M nemusí znamenat stejný střih u různých značek.</li><li><strong>Využití:</strong> při dřepu, běhu nebo práci s činkami se musí oblečení pohodlně pohybovat; průsvitnost, elasticitu ani odvod potu nelze spolehlivě odvodit z ceny nebo fotografie.</li></ul>',
    ]
    n=0
    for kind,(heading,caution) in GROUPS.items():
        if not groups[kind]:
            continue
        parts += ['<h2 id="xfit-apparel-'+kind+'">'+heading+' – katalogové varianty</h2>','<p>'+caution+'</p>', size_picker(kind,by_size[kind])]
        for item in groups[kind][:3]:
            n+=1
            title=html.escape(item["title"])
            attr=html.escape(item["title"],quote=True)
            pic=('<p><img src="'+html.escape(item["image"],quote=True)+'" alt="'+attr+'" loading="lazy" width="120" height="120" style="max-width:100%;object-fit:contain;" /></p>' if item["image"] else "")
            parts.append('<article class="xfit-product-card" id="xfit-apparel-offer-'+str(n)+'" style="border:1px solid #dce5e8;border-radius:12px;padding:16px;margin:16px 0;overflow-wrap:anywhere;">'
                '<h3>'+title+'</h3>'+pic+
                '<p><strong>Velikost v názvu: '+html.escape(item["size"])+'</strong> · cena této varianty: '+money(item["price"])+' (bez dopravy a poplatků).</p>'
                '<p>'+delivery_note(item)+'</p>'
                '<p><small>Partnerský odkaz · Xfit.cz může získat provizi · NaMaximum.cz · nová karta.</small></p>'
                '<p><a href="'+html.escape(item["affiliate_url"],quote=True)+'" rel="sponsored nofollow noopener noreferrer" target="_blank" aria-label="Ověřit variantu a cenu: '+attr+' (nová karta)" style="display:inline-block;min-height:44px;box-sizing:border-box;padding:12px 16px;background-color:#116a70;color:#ffffff;border-radius:8px;font-weight:700;">Ověřit variantu a cenu</a></p></article>')
    parts += [
        '<h2>Co ověřit před objednáním</h2>',
        '<ol><li>Vyberte svoji velikost podle tabulky výrobce, ne pouze podle písmene na štítku.</li><li>Ověřte cenu a dostupnost zvolené barvy a velikosti přímo u prodejce. Uvedená cena se může týkat jiné varianty, než potřebujete.</li><li>Zkontrolujte složení materiálu, údržbu a podmínky vrácení; započítejte dopravu.</li><li>Pokud chybí rozměry, vyžádejte si je nebo objednávku odložte.</li></ol>',
        '<h2>Jak vzniká srovnání</h2>',
        '<p>Vycházíme z aktuálně načteného XML katalogu jediného prodejce. Vyžadujeme konkrétní kategorii, rozpoznatelné označení oděvu a jednoznačnou velikost přímo v názvu. Vyřazujeme konfliktní identity a ceny, výslovně nedostupné položky, předobjednávky a katalogovou expedici nad sedm dní. V hlavních kartách uvádíme nejlevnější způsobilou variantu vybraných rodin; ve výběru podle velikosti nejlevnější způsobilou variantu daného označení z katalogu. Další velikosti mohou mít odlišnou cenu nebo dostupnost. Žádné oblečení jsme fyzicky netestovali.</p>',
        '<p>Vybíráte také pomůcky na domácí trénink? Projděte <a href="https://xfit.cz/xfit-os-vybaveni-na-domaci-cviceni-nabidky/">nabídky podložek a odporových gum</a>. K obecným pravidlům bezpečnosti výrobků viz <a href="https://commission.europa.eu/topics/business-and-industry/product-safety_en">Evropská komise – bezpečnost výrobků</a>.</p>',
    ]
    doc={"slug":SLUG,"title":"Fitness oblečení: nabídky triček, mikin a legín podle velikosti",
         "excerpt":"Praktický výběr fitness oblečení, konkrétní katalogové velikosti a ceny variant, kontrola rozměrů a podmínek vrácení.",
         "content":"\n".join(parts)}
    check_document(doc,commercial=True)
    return doc

def prepare():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    base, sample = os.environ["XFIT_AFFIL_DEFAULT_LINK"], os.environ["XFIT_AFFIL_SAMPLE_PRODUCT_LINK"]
    groups = shortlist(catalog, base, sample)
    print(json.dumps({"state": "APPAREL_SOURCE_COVERAGE", "eligible_families":
                      {kind: len(rows) for kind, rows in groups.items()},
                      "actual_stock_verified": False, "wordpress_writes": 0}))
    doc = build_document(catalog, base, sample)
    PREPARED.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "APPAREL_COMPARISON_PREPARED", "cards": check_document(doc)["product_cards"],
                      "size_choices": doc["content"].count("data-xfit-size="),
                      "wordpress_writes": 0}))


def apply():
    # Build once using the same actual feed; validate age again before POST.
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    source = json.loads(PREPARED.read_text(encoding="utf-8"))
    expected = build_document(catalog, os.environ["XFIT_AFFIL_DEFAULT_LINK"], os.environ["XFIT_AFFIL_SAMPLE_PRODUCT_LINK"])
    if source != expected:
        raise PublishError("Prepared apparel document drifted")
    doc = validate_document(source)
    base = normalized_base()
    matches = wp_request(base, "posts?" + urlencode({"slug": SLUG, "context": "edit", "status": "any", "per_page": 10,
                    "_fields": "id,slug,status,content,link,title"}))
    if not isinstance(matches, list) or len(matches) > 1:
        raise PublishError("Unexpected apparel slug lookup")
    if matches:
        post = matches[0]
        raw = (post.get("content") or {}).get("raw", "")
        if (post.get("slug") != SLUG or post.get("status") != "publish"
                or post.get("link") != URL or not isinstance(raw, str) or MARKER not in raw
                or article_visible(raw)[0] != article_visible(doc["content"])[0]
                or editorial_links(raw) != editorial_links(doc["content"])):
            raise PublishError("Existing apparel post differs; no rewrite or automatic retry")
        verify_public(URL, doc["title"], doc["content"])
        print(json.dumps({"state": "unchanged_public_verified", "post_id": post["id"], "slug": SLUG,
                          "url": URL, "public_site_modified": False}))
        return
    result = publish(doc, live=True, new_only=True)
    if result.get("state") != "live_verified" or result.get("url") != URL or result.get("slug") != SLUG:
        raise PublishError("Apparel permalink or release proof mismatch; no retry")
    # Verify exact authenticated affiliate hrefs as well as visible body.
    post = wp_request(base, "posts/" + str(result["post_id"]) + "?context=edit&_fields=id,slug,status,content")
    raw = (post.get("content") or {}).get("raw")
    if post.get("id") != result["post_id"] or post.get("slug") != SLUG or not isinstance(raw, str) or editorial_links(raw) != editorial_links(doc["content"]):
        raise PublishError("Apparel authenticated destination readback mismatch")
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
        print("XFIT_APPAREL_RELEASE_BLOCKED: " + type(exc).__name__)
        raise SystemExit(2)
