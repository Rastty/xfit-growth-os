#!/usr/bin/env python3
"""Safe, idempotent Xfit creatine guide built from authenticated NaMaximum feed.

Never invent products, use Heureka CPC links, expose secrets or publish
without a matching real sample Affial product deeplink.
"""
import argparse
import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, parse_qs, urlencode, urlsplit, urlunsplit

from scripts.xfit_affil_deeplink import affiliate_signature, classify_product_link
from scripts.xfit_select import select_offers
from scripts.wp_publish import (MARKER, PublishError, normalized_base, plain,
                                publish, verify_public, wp_request, existing_content)

SLUG = "xfit-os-kreatin-poradce"
EXAMPLE_PATH = "/kategorie/kreatin/creatine-creapure"
EXAMPLE_VARIANT = "392"
AFFIL_KEYS = ("utm_medium", "utm_campaign", "utm_source", "a_aid", "a_bid")
ALLOWED_PRODUCT_PARAMS = {"variant"}
PRODUCT_HOSTS = {"namaximum.cz", "www.namaximum.cz"}
IMAGE_HOSTS = {"greenmedical.bwcdn.net"}
MONOHYDRATE_TERMS = ("monohydr", "creapure")
BLOCK_UNCOMPARABLE = ("capsul", "kapsl", "tablet", "pre workout", "pre-workout",
                      "matrix", "complex", "komplex", "mix", "blend")

def validate_example(base, sample):
    """Requires exact real exemplar, so a guessed commercial URL never ships."""
    result = classify_product_link(base, sample)
    if result.get("scheme") != "merchant_direct_query":
        raise PublishError("Approved product-link sample uses an unsupported tracking scheme")
    p = urlsplit(sample)
    q = parse_qs(p.query)
    # Dynamic-link generators may rewrite the canonical product route and
    # omit variant=392. The essential proof is a NON-HOMEPAGE NaMaximum
    # product with the same campaign attribution IDs as the base link.
    if p.path.rstrip("/") in ("", "/"):
        raise PublishError("Affiliate sample must link to a product page, not homepage")
    if q.get("utm_medium") not in (["affiliate"], []):
        raise PublishError("Affiliate sample uses unexpected traffic medium")
    # Sample direct-query tracking params must correspond to base campaign.
    affiliate_signature(base)
    return True

def build_tracked_url(source_url, base, sample):
    validate_example(base, sample)
    product = urlsplit(source_url)
    if (product.scheme != "https" or product.hostname not in PRODUCT_HOSTS or
        product.username or product.password or product.fragment):
        raise PublishError("Invalid product destination host")
    source_params = parse_qsl(product.query, keep_blank_values=True)
    if any(k.lower() not in ALLOWED_PRODUCT_PARAMS for k, _ in source_params):
        raise PublishError("Unexpected URL parameters in product feed")
    bp = urlsplit(base)
    base_params = parse_qs(bp.query)
    outgoing = source_params + [(k, base_params[k][0]) for k in AFFIL_KEYS]
    link = urlunsplit(("https", product.netloc, product.path, urlencode(outgoing), ""))
    # Validate effective tracking/signature exactly as sample.
    if classify_product_link(base, link).get("scheme") != "merchant_direct_query":
        raise PublishError("Generated product link failed affiliate signature check")
    return link

def safe_image(src):
    p = urlsplit(src or "")
    if p.scheme == "https" and p.hostname in IMAGE_HOSTS and not p.username and not p.password:
        return src
    return None

def shortlist(catalog, base, sample, budget=1500):
    # Filter the entire feed for comparable monohydrate products BEFORE ranking.
    # Previously the cheapest twenty general creatine offers could crowd out
    # relevant powder variants and falsely yield an empty selection.
    eligible = [
        o for o in catalog.get("products", [])
        if any(t in (o.get("title") or "").casefold() for t in MONOHYDRATE_TERMS)
        and not any(t in (o.get("title") or "").casefold() for t in BLOCK_UNCOMPARABLE)
    ]
    items = select_offers({"products": eligible}, "creatine", max_price=budget,
                          min_mass_g=200, limit=20)
    result = []
    for p in items:
        title = p["title"].casefold()
        if not any(t in title for t in MONOHYDRATE_TERMS):
            continue
        if any(t in title for t in BLOCK_UNCOMPARABLE):
            continue
        try:
            url = build_tracked_url(p["source_url"], base, sample)
        except (PublishError, ValueError):
            continue
        result.append({**p, "tracked_url": url, "image": safe_image(
            next((o.get("image_url") for o in catalog["products"]
                  if str(o.get("id")) == p["id"]), ""))})
    if len(result) < 3:
        raise PublishError("Too few comparable offers (named candidates="+str(len(eligible))+", ranked="+str(len(items))+", trackable="+str(len(result))+"); abort")
    return result[:6]

def build_document(catalog, base, sample):
    chosen = shortlist(catalog, base, sample)
    bits = [
      '<p><strong>Jak vybrat kreatin bez zbytečného přeplácení?</strong> '
      'Pro většinu zdravých dospělých, kteří pravidelně silově nebo intenzivně trénují, '
      'je často nejpraktičtější volbou kreatin monohydrát. '
      'Tento přehled srovnává nabídky podle ceny a hmotnosti balení, '
      'nikoli podle marketingových superlativů.</p>',
      '<p><strong>Jak používat výběr:</strong> Porovnejte cenu za 100 g prášku, '
      'velikost balení a celkovou cenu. Nezaměňujte cenu za 100 g výrobku '
      's přesnou cenou za 100 g čistého kreatinu – čistotu konkrétních '
      'výrobků ověřujte na obalu. Ceny a dostupnost se mohou měnit.</p>',
      '<h2>Kreatin monohydrát – přehled ověřených produktových nabídek</h2>',
      '<p><em>Obsahuje affiliate odkazy na NaMaximum.cz přes síť Affial. '
      'Pokud přes odkaz nakoupíte, Xfit.cz může získat provizi. '
      'Řazení je podle ceny za 100 g baleného prášku, nikoli výše provize.</em></p>',
      '<table><thead><tr><th>Produkt</th><th>Balení</th><th>Cena</th>'
      '<th>Cena za 100 g</th><th>Odkaz</th></tr></thead><tbody>'
    ]
    for offer in chosen:
        title = html.escape(offer["title"])
        href = html.escape(offer["tracked_url"], quote=True)
        price = str(round(offer["price_czk"]))
        unit_price = str(round(offer["price_per_100g_powder_czk"]))
        bits.append('<tr><td><strong>' + title + '</strong></td><td>' +
            str(offer["mass_g"]) + ' g</td><td>' + price + ' Kč</td><td>' +
            unit_price + ' Kč</td><td><a href="' + href +
            '" rel="sponsored nofollow noopener noreferrer" target="_blank">' +
            'Zobrazit v obchodě</a></td></tr>')
    bits += [
      '</tbody></table>',
      '<h2>Kdy má kreatin smysl?</h2>',
      '<p>Kreatin monohydrát patří k nejlépe prozkoumaným sportovním doplňkům. '
      'Podle odborných přehledů může při pravidelném tréninku zlepšovat výkon '
      'při opakovaných krátkých intenzivních výkonech. Nejde ale o náhradu tréninku, '
      'odpočinku a běžné stravy.</p>',
      '<h2>Co zkontrolovat před nákupem</h2>',
      '<ul><li><strong>Složení:</strong> zda jde opravdu o monohydrát bez zbytečných směsí.</li>'
      '<li><strong>Gramáž:</strong> větší balení nemusí být vždy nejvýhodnější.</li>'
      '<li><strong>Cena za 100 g:</strong> srovnání zde používá hmotnost celého prášku.</li>'
      '<li><strong>Informace výrobce:</strong> deklarovaná čistota, dávkování a upozornění.</li></ul>',
      '<h2>Časté otázky</h2><h3>Je Creapure automaticky nejlepší?</h3>',
      '<p>Creapure je značka suroviny. Při rozhodování záleží také na '
      'deklarovaném složení, transparentnosti výrobce a ceně. '
      'Samotný název na obalu není důkazem lepšího výkonu než u '
      'jiných kvalitních monohydrátů.</p>',
      '<h3>Kolik kreatinu užívat?</h3>',
      '<p>Ve výzkumu sportovní výkonnosti se často používá dlouhodobý '
      'příjem přibližně 3–5 g kreatin monohydrátu denně u zdravých dospělých. '
      'Konkrétní užívání se musí řídit zdravotním stavem a informacemi '
      'na výrobku; při onemocnění ledvin nebo jiné zdravotní nejistotě '
      'je vhodné poradit se s lékařem.</p>',
      '<p><strong>Související průvodce:</strong> '
      '<a href="https://xfit.cz/xfit-os-protein-guide/">Jak vybrat protein</a>.</p>',
      '<h2>Zdroje a metodika</h2>',
      '<p>Informace o použití kreatinu vycházejí z odborných souhrnů '
      '<a href="https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/">'
      'NIH Office of Dietary Supplements</a> a '
      '<a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC5469049/">'
      'stanoviska ISSN ke kreatinu</a>. '
      'Ceny pocházejí z produktového XML NaMaximum; z nabídky jsou vyřazeny '
      'kapsle, tablety, nejednoznačné směsi a výrobky bez rozpoznatelné gramáže. '
      'Proklik je affiliate, ale pořadí neurčuje provize.</p>',
      '<p><small>Informativní výběr pro dospělé; nejedná se o individuální '
      'zdravotní doporučení. Ceny a dostupnost ověřte v obchodě.</small></p>'
    ]
    return {
      "slug": SLUG,
      "title": "Jak vybrat kreatin: srovnání cen a balení monohydrátu",
      "excerpt": "Kreatin monohydrát: přehled nabídek NaMaximum, gramáže, ceny za 100 g a praktická kritéria výběru. Přehledná metodika a transparentní affiliate odkazy.",
      "content": "\n".join(bits),
    }

def publish_if_changed(doc):
    """Don't rewrite WP post unless actual copy or offer data changed."""
    base=normalized_base()
    rows=wp_request(base,"posts?slug="+SLUG+
        "&context=edit&status=any&per_page=10&_fields=id,slug,status,content,link")
    if not isinstance(rows,list):
        raise PublishError("Unexpected post lookup response")
    matches=[p for p in rows if p.get("slug")==SLUG]
    if len(matches)>1:
        raise PublishError("Duplicate guide slug: abort")
    full_content=MARKER+"\n"+doc["content"]
    if matches:
        p=matches[0]
        if MARKER not in existing_content(p):
            raise PublishError("Existing article does not belong to Xfit Growth OS")
        raw=(p.get("content") or {}).get("raw","")
        if p.get("status")=="publish" and raw.strip()==full_content.strip():
            return {"state":"unchanged_no_write","url":p.get("link"),"post_id":p.get("id")}
    from scripts.wp_publish import validate_document
    result=publish(validate_document(doc),live=True)
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--catalog",default="reports/private-greenmedical-catalog.json")
    ap.add_argument("--deploy",action="store_true")
    args=ap.parse_args()
    base=os.getenv("XFIT_AFFIL_DEFAULT_LINK","")
    sample=os.getenv("XFIT_AFFIL_SAMPLE_PRODUCT_LINK","")
    if not base or not sample:
        raise PublishError("Missing approved affiliate base or sample link secret")
    catalog=json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    if catalog.get("merchant")!="namaximum.cz" or not catalog.get("merchant_match"):
        raise PublishError("Merchant mismatch in XML; cannot build guide")
    doc=build_document(catalog,base,sample)
    if not args.deploy:
        print(json.dumps({"state":"guide_dry_run","slug":SLUG,
             "chars":len(doc["content"]),"public_site_modified":False}))
        return
    result=publish_if_changed(doc)
    print(json.dumps({"state":result["state"],"url":result.get("url"),
        "post_id":result.get("post_id"),"public_site_modified":result["state"]!="unchanged_no_write"},
        ensure_ascii=False))

if __name__=="__main__":
    try:
        main()
    except (ValueError, PublishError, OSError, KeyError, json.JSONDecodeError) as e:
        print("XFIT_GUIDE_ERROR: "+type(e).__name__+(": "+str(e) if isinstance(e,PublishError) else ""),file=sys.stderr)
        sys.exit(2)
