"""Catalog-bound drink containers; separate mixing and carrying purposes."""
import argparse
import html
import json
import os
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlsplit, urlencode
from scripts.xfit_select import folded, MAX_FULL_CATALOG_SCAN, mass_grams
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

SLUG = "xfit-os-arasidova-a-orechova-masla"
URL = "https://xfit.cz/" + SLUG + "/"
CATALOG = Path("reports/private-greenmedical-catalog.json")
PREPARED = Path("reports/private-nut_butter-comparison.json")
GROUPS = {
    "peanut": "Arašídová másla",
    "almond": "Mandlová másla",
    "cashew": "Kešu másla",
}
PRICE_LIMIT = Decimal("2000")

def nut_butter_kind(row):
    title = folded(row.get("title") or "")
    category = folded(row.get("category") or "")
    if not re.search(r"masl|butter|orechov\w* krem", category):
        return None
    if re.search(r"\b(?:tycink\w*|bar|mouk\w*|flour|napoj\w*|kapsl\w*|tablet\w*|aroma|balicek|multipack)\b", title):
        return None
    kinds = [kind for kind, pattern in {
        "peanut": r"\b(?:arasidov\w* masl\w*|peanut butter)\b",
        "almond": r"\b(?:mandlov\w* masl\w*|almond butter)\b",
        "cashew": r"\b(?:kesu masl\w*|cashew butter)\b",
    }.items() if re.search(pattern,title)]
    return kinds[0] if len(kinds)==1 else None

def shortlist(catalog, base, sample):
    if catalog.get("merchant") != "namaximum.cz" or catalog.get("merchant_match") is not True:
        raise PublishError("Nut butter comparison requires verified merchant")
    items = catalog.get("products")
    if not isinstance(items, list) or len(items) > MAX_FULL_CATALOG_SCAN:
        raise PublishError("Unexpected catalog inventory")
    # Resolve duplicate identities before applying price or availability limits.
    # Contradictory variants cannot be silently promoted as the cheapest deal.
    records, identities = [], defaultdict(list)
    for row in items:
        kind = nut_butter_kind(row)
        mass = mass_grams(row.get("title"))
        if not kind or mass is None or not 100 <= mass <= 5000:
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
                     "ean": ean, "price": price, "kind": kind, "mass": mass,
                     "unit_price": (price * 100 / mass).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                     "affiliate_url": affiliate,
                     "image": safe_image(row.get("image_url") or ""), "availability_state": state}
        for field in ("id", "ean", "source_url"):
            if candidate[field]:
                identities[(field, candidate[field])].append(len(records))
        records.append(candidate)
    bad = set()
    for indices in identities.values():
        signatures = {(records[i]["id"], records[i]["ean"], records[i]["source_url"],
                       records[i]["price"], records[i]["title"], records[i]["kind"],
                       records[i]["availability_state"], records[i]["mass"]) for i in indices}
        if len(signatures) > 1:
            bad.update(indices)
    grouped = {kind: {} for kind in GROUPS}
    for i, row in enumerate(records):
        if i in bad or row["price"] > PRICE_LIMIT or row["availability_state"] not in (
                "feed_stocked", "up_to_week", "unknown"):
            continue
        family = urlsplit(row["source_url"]).path.rstrip("/")
        prior = grouped[row["kind"]].get(family)
        if prior is None or (row["unit_price"], row["price"], row["id"]) < (prior["unit_price"], prior["price"], prior["id"]):
            grouped[row["kind"]][family] = row
    return {kind: sorted(rows.values(), key=lambda r: (r["unit_price"], r["price"], r["title"], r["id"]))
            for kind, rows in grouped.items()}


def build_document(catalog, base, sample):
    groups=shortlist(catalog,base,sample)
    if sum(map(len,groups.values())) < 2:
        raise PublishError("Need two distinct eligible food families with exact mass")
    parts=[
        '<p><strong>Arašídové, mandlové nebo kešu máslo?</strong> Nejprve vyberte surovinu, kterou běžně používáte, a teprve poté velikost balení. Pokud máte doma vyhovující máslo, další nepotřebujete. Níže najdete skutečné katalogové nabídky s přepočtem na 100 g, nikoli výživový žebříček.</p>',
        catalog_retrieval_notice(catalog),
        '<p><strong>Rozsah:</strong> výběr jednoho prodejce NaMaximum.cz; ceny bez dopravy a poplatků. Porovnáváme vždy výrobky ve stejné skupině podle ceny za 100 g. Název sám nepotvrzuje podíl ořechů, arašídů ani další složky. Při alergii zkontrolujte úplnou etiketu včetně možného křížového kontaktu.</p>',
        '<nav aria-label="Druhy másel"><ul>'+''.join('<li><a href="#xfit-butter-'+kind+'" style="display:inline-block;padding:12px 0">'+heading+'</a></li>' for kind,heading in GROUPS.items() if groups[kind])+'</ul></nav>',
        '<h2>Jak rozhodnout mezi malým a velkým balením</h2>',
        '<p>Modelově: 250 g za 100 Kč vychází na 40 Kč za 100 g; 500 g za 170 Kč na 34 Kč za 100 g. Druhé balení je levnější na gramáž, první znamená menší jednorázovou útratu. Pokud větší balení nespotřebujete včas, nižší jednotková cena nemusí být výhodná. Nejde o ceny aktuálních produktů.</p>',
    ]
    n=0
    for kind,heading in GROUPS.items():
        if not groups[kind]:
            continue
        parts += ['<h2 id="xfit-butter-'+kind+'">'+heading+' – katalogové nabídky</h2>',
                  '<p>V této skupině řadíme podle ceny za 100 g. Složení, konzistenci a alergeny ověřte u konkrétní varianty.</p>' if n==0 else '<p>Porovnejte cenu a velikost balení; úplné složení najdete na etiketě.</p>' if n<=3 else '<p>Zkontrolujte deklarovanou surovinu, gramáž a podmínky skladování.</p>']
        for item in groups[kind][:3]:
            n+=1
            title=html.escape(item["title"])
            attr=html.escape(item["title"],quote=True)
            pic=('<p><img src="'+html.escape(item["image"],quote=True)+'" alt="'+attr+'" loading="lazy" width="120" height="120" style="max-width:100%;object-fit:contain;" /></p>' if item["image"] else "")
            parts.append('<article class="xfit-product-card" id="xfit-butter-offer-'+str(n)+'" style="border:1px solid #dce5e8;border-radius:12px;padding:16px;margin:16px 0;overflow-wrap:anywhere;">'
                '<h3>'+title+'</h3>'+pic+
                '<p><strong>'+money(item["price"])+'</strong> za balení '+str(item["mass"])+' g.</p>'
                '<p><strong>'+money(item["unit_price"])+'</strong> za 100 g výrobku.</p>'
                '<p>'+delivery_note(item)+'</p>'
                '<p><small>Partnerský odkaz · Xfit.cz může získat provizi · NaMaximum.cz · nová karta.</small></p>'
                '<p><a href="'+html.escape(item["affiliate_url"],quote=True)+'" rel="sponsored nofollow noopener noreferrer" target="_blank" aria-label="Ověřit cenu a etiketu: '+attr+' (nová karta)" style="display:inline-block;min-height:44px;box-sizing:border-box;padding:12px 16px;background-color:#116a70;color:#ffffff;border-radius:8px;font-weight:700;">Ověřit cenu a etiketu</a></p></article>')
    parts += [
        '<h2>Co zkontrolovat na etiketě před nákupem</h2>',
        '<ul><li>Podíl hlavní suroviny a ostatní přísady, například cukr, sůl nebo olej. Neodvozujte složení z fotografie ani slova „přírodní“.</li><li>Arašídy jsou luštěnina, mandlové a kešu výrobky patří mezi jiné alergeny. Cenová tabulka neurčuje vhodnost při alergii; zkontrolujte i upozornění na stopy alergenů.</li><li>Čistou hmotnost, datum minimální trvanlivosti a pokyny pro skladování po otevření.</li><li>Konečnou cenu s dopravou a kolik balení opravdu spotřebujete.</li></ul>',
        '<h2>Jak vzniká srovnání</h2>',
        '<p>Vycházíme z aktuálně načteného XML katalogu jediného prodejce, jednoznačného názvu suroviny, názvem deklarované hmotnosti a přesné ceny varianty. Vyřazujeme nejasná balení, konfliktní identifikátory a známou nedostupnost. Z rodiny vybíráme nejvýhodnější jednotkovou cenu; nejde o srovnání celého trhu ani fyzický test chuti nebo složení. Cena za 100 g výrobku není cena za bílkoviny. O pravidlech označování potravin a alergenů informuje <a href="https://food.ec.europa.eu/food-safety/labelling-and-nutrition/food-information-consumers-legislation_en">Evropská komise</a>.</p>',
    ]
    doc={"slug":SLUG,"title":"Arašídová a ořechová másla: srovnání cen za 100 g",
         "excerpt":"Praktické porovnání arašídových, mandlových a kešu másel podle ceny a velikosti balení z aktuálního katalogu; kontrola etikety.",
         "content":"\n".join(parts)}
    check_document(doc,commercial=True)
    return doc

def prepare():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    verified_catalog_fetch_time(catalog, required=True)
    base, sample = os.environ["XFIT_AFFIL_DEFAULT_LINK"], os.environ["XFIT_AFFIL_SAMPLE_PRODUCT_LINK"]
    groups = shortlist(catalog, base, sample)
    print(json.dumps({"state": "NUT_BUTTER_SOURCE_COVERAGE", "eligible_families":
                      {kind: len(rows) for kind, rows in groups.items()},
                      "actual_stock_verified": False, "wordpress_writes": 0}))
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
        raise PublishError("Prepared nut_butter document drifted")
    doc = validate_document(source)
    base = normalized_base()
    matches = wp_request(base, "posts?" + urlencode({"slug": SLUG, "context": "edit", "status": "any", "per_page": 10,
                    "_fields": "id,slug,status,content,link,title"}))
    if not isinstance(matches, list) or len(matches) > 1:
        raise PublishError("Unexpected nut_butter slug lookup")
    if matches:
        post = matches[0]
        raw = (post.get("content") or {}).get("raw", "")
        if (post.get("slug") != SLUG or post.get("status") != "publish"
                or post.get("link") != URL or not isinstance(raw, str) or MARKER not in raw
                or article_visible(raw)[0] != article_visible(doc["content"])[0]
                or editorial_links(raw) != editorial_links(doc["content"])):
            raise PublishError("Existing nut_butter post differs; no rewrite or automatic retry")
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
