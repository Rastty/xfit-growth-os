#!/usr/bin/env python3
"""NaMaximum whey comparison for Xfit; independently updates a single owned WP page.

Prices are from real feed; ranking uses package powder mass, not protein grams.
Affiliate links are generated only if owner-supplied original sample validates.
"""
import argparse
import html
import json
import os
import re
import sys
from pathlib import Path
from scripts.xfit_creatine_guide import build_tracked_url
from scripts.xfit_select import select_offers
from scripts.wp_publish import PublishError, normalized_base, MARKER, existing_content, wp_request, validate_document, publish

SLUG = "xfit-os-syrovatkovy-protein-porovnani"
RISK_WORDS = ("mass gainer", "gain mass", "gainer", "kapsl", "tablet", "capsule", "protein bar", "tycink", "tyčink")
def kind_label(title):
    lower=title.casefold()
    if any(w in lower for w in ("isolate", "isolat", "izolat", "izolát", "wpi")):
        return "Pravděpodobně izolát – ověřit etiketu"
    if any(w in lower for w in ("koncentr", "concentr", "wpc")):
        return "Pravděpodobně koncentrát – ověřit etiketu"
    return "Typ ověřit na etiketě"

def build_document(catalog, base, sample):
    if catalog.get("merchant") != "namaximum.cz" or not catalog.get("merchant_match"):
        raise PublishError("Wrong merchant feed")
    # First include all eligible whey powders; filtering is conservative.
    candidates = select_offers(catalog, "whey", max_price=2000, min_mass_g=500, limit=20)
    chosen=[]
    for p in candidates:
        title=p["title"].casefold()
        if any(w in title for w in RISK_WORDS):
            continue
        try:
            deeplink=build_tracked_url(p["source_url"],base,sample)
        except (PublishError, ValueError):
            continue
        chosen.append({**p, "affiliate_url":deeplink})
    if len(chosen)<3:
        raise PublishError("Insufficient consistent whey offers for public guide")
    chosen=chosen[:6]
    parts=[
        '<p><strong>Výběr syrovátkového proteinu nemusí začínat značkou.</strong> '
        'Nejdříve zvažte, zda vám vyhovuje mléčná bílkovina, co říká etiketa '
        'o složení a jakou porci chcete. Teprve potom má smysl srovnávat cenu.</p>',
        '<p><strong>Jak srovnáváme:</strong> níže používáme cenu za 100 g proteinového '
        'prášku, nikoli za 100 g skutečných bílkovin. K tomu bychom potřebovali '
        'spolehlivý údaj o jejich obsahu pro každou variantu; nelze jej odhadovat '
        'jen z názvu nebo ceny. Ceny se mohou měnit.</p>',
        '<h2>Syrovátkové proteiny – porovnání balení a ceny</h2>',
        '<p><em>Partnerské odkazy (Affial / NaMaximum.cz). Při nákupu přes odkaz '
        'může Xfit.cz získat provizi. Pořadí určuje jednotková cena za hmotnost '
        'prášku, nikoliv provize.</em></p>',
        '<table><thead><tr><th>Produkt</th><th>Typ dle názvu</th><th>Balení</th>'
        '<th>Cena</th><th>100 g prášku</th><th>Obchod</th></tr></thead><tbody>'
    ]
    for item in chosen:
        parts.append('<tr><td><strong>'+html.escape(item["title"])+'</strong></td><td>'+
            html.escape(kind_label(item["title"]))+'</td><td>'+
            str(item["mass_g"])+' g</td><td>'+str(round(item["price_czk"]))+
            ' Kč</td><td>'+str(round(item["price_per_100g_powder_czk"]))+
            ' Kč</td><td><a href="'+html.escape(item["affiliate_url"],quote=True)+
            '" rel="sponsored nofollow noopener noreferrer" target="_blank">Zobrazit</a></td></tr>')
    parts += [
      '</tbody></table>',
      '<h2>Koncentrát, izolát nebo něco jiného?</h2>',
      '<p><strong>WPC (koncentrát)</strong> bývá cenově dostupnější, ale obvykle '
      'obsahuje více laktózy než izolát. <strong>WPI (izolát)</strong> má často '
      'vyšší podíl bílkovin a méně laktózy, ale za vyšší cenu. '
      'Ani označení izolát samo o sobě nezaručuje nulovou laktózu. '
      'Složení a alergeny vždy ověřte u konkrétního balení.</p>',
      '<h2>Na co se zaměřit před objednávkou</h2>',
      '<ol><li>Bílkoviny na 100 g a velikost výrobní dávky.</li>'
      '<li>Mléčné alergeny a případná deklarace bez laktózy.</li>'
      '<li>Cena za 100 g skutečných bílkovin, pokud výrobce uvádí jejich obsah.</li>'
      '<li>Gramáž varianty, chuť, další přísady a energetická hodnota.</li>'
      '<li>Zkušenosti s trávením a místo prášku v celkovém jídelníčku.</li></ol>',
      '<h2>Je potřeba pít protein po každém tréninku?</h2>',
      '<p>Proteinový prášek není podmínkou pro růst svalů. '
      'Pokud přijímáte dostatek bílkovin z běžné stravy, nemusíte žádný kupovat. '
      'Sportovní zdroje zdůrazňují především celkový denní příjem bílkovin '
      'a pravidelnost tréninku, nikoli značku nebo čas jedné dávky.</p>',
      '<p>Detailnější základy jsou v průvodci '
      '<a href="https://xfit.cz/xfit-os-protein-guide/">Jak vybrat protein</a>.</p>',
      '<h2>Metodika a zdroje</h2>',
      '<p>Podklady k bílkovinám: <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC5477153/">'
      'ISSN Position Stand: Protein and exercise</a> a '
      '<a href="https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/">'
      'NIH Office of Dietary Supplements</a>. Produkty a ceny pocházejí z '
      'XML feedu NaMaximum.cz. Vyřazujeme tyčinky, gainery a produkty bez '
      'spolehlivě rozpoznané gramáže. Cena za 100 g prášku není totéž '
      'co cena za 100 g čistých bílkovin.</p>',
      '<p><small>Informace slouží zdravým dospělým. '
      'Při zdravotních omezeních, onemocnění ledvin či alergiích '
      'konzultujte individuální příjem bílkovin s odborníkem. '
      'Cenu a dostupnost vždy ověřte v obchodě.</small></p>'
    ]
    return {
      "slug":SLUG,
      "title":"Srovnání syrovátkových proteinů: cena, balení a typ",
      "excerpt":"Aktuální výběr syrovátkových proteinů z NaMaximum podle ceny a velikosti balení, s vysvětlením koncentrátu a izolátu.",
      "content":"\n".join(parts)
    }

def deploy(doc):
    base=normalized_base()
    rows=wp_request(base,"posts?slug="+SLUG+"&context=edit&status=any&per_page=10&_fields=id,slug,status,content,link")
    if not isinstance(rows,list):
        raise PublishError("Invalid WP lookup")
    matches=[p for p in rows if p.get("slug")==SLUG]
    if len(matches)>1:raise PublishError("Duplicate slug")
    if matches:
        p=matches[0]
        if MARKER not in existing_content(p):
            raise PublishError("Ownership marker not found")
        raw=(p.get("content") or {}).get("raw","")
        if p.get("status")=="publish" and raw.strip()==(MARKER+"\n"+doc["content"]).strip():
            return {"state":"unchanged_no_write","url":p.get("link"),"post_id":p.get("id")}
    return publish(validate_document(doc),live=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--catalog",default="reports/private-greenmedical-catalog.json")
    ap.add_argument("--deploy",action="store_true")
    args=ap.parse_args()
    base=os.getenv("XFIT_AFFIL_DEFAULT_LINK","")
    sample=os.getenv("XFIT_AFFIL_SAMPLE_PRODUCT_LINK","")
    if not base or not sample:raise PublishError("Affiliate secrets missing")
    data=json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    doc=build_document(data,base,sample)
    if not args.deploy:
        print(json.dumps({"state":"whey_guide_dry_run","chars":len(doc["content"]),"slug":SLUG,"public_site_modified":False}))
        return
    r=deploy(doc)
    print(json.dumps({"state":r["state"],"url":r.get("url"),"post_id":r.get("post_id"),
          "public_site_modified":r["state"]!="unchanged_no_write"},ensure_ascii=False))

if __name__=="__main__":
    try:main()
    except (ValueError,PublishError,OSError,KeyError,json.JSONDecodeError) as ex:
        print("XFIT_WHEY_ERROR: "+type(ex).__name__+(": "+str(ex) if isinstance(ex,PublishError) else ""),file=sys.stderr)
        sys.exit(2)
