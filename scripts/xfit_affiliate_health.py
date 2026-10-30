#!/usr/bin/env python3
"""Read-only public affiliate URL health gate for Xfit owned guides.

Checks the actually published markup against the owner's secret Affial
campaign IDs. No click requests, tracking pixels, credential logs or WP writes.
"""
import html
from html.parser import HTMLParser
import json
import os
import sys
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen
from scripts.xfit_affil_deeplink import affiliate_signature

SLUGS=("xfit-os-kreatin-poradce","xfit-os-syrovatkovy-protein-porovnani")
TARGET_HOSTS=("namaximum.cz","www.namaximum.cz")

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            a=dict(attrs)
            self.links.append({"url":html.unescape(a.get("href") or ""),
                "rel":(a.get("rel") or "").split(),
                "text":a.get("aria-label") or ""})

def check_markdown_html(body, base_url, *, min_links=2):
    aid,bid=affiliate_signature(base_url)
    parser=LinkParser()
    parser.feed(body)
    errors=[]
    merchant=[]
    for item in parser.links:
        p=urlsplit(item["url"])
        if p.hostname not in TARGET_HOSTS:
            continue
        q=parse_qs(p.query)
        merchant.append(p)
        if p.scheme!="https" or p.username or p.password:
            errors.append("invalid_https")
        if p.path in ("","/"):
            errors.append("homepage_not_product")
        if "sponsored" not in item["rel"]:
            errors.append("missing_sponsored_rel")
        if q.get("a_aid")!=[aid] or q.get("a_bid")!=[bid]:
            errors.append("wrong_campaign_ids")
        if q.get("utm_campaign")!=["affial.com"] or q.get("utm_source")!=["pap"]:
            errors.append("wrong_campaign_utm")
        if q.get("utm_medium")!=["affiliate"]:
            errors.append("wrong_campaign_medium")
        if q.get("utm_source")==["heureka"]:
            errors.append("heureka_cpc_tracking")
    if len(merchant)<min_links:
        errors.append("insufficient_affiliate_product_links")
    return {"merchant_link_count":len(merchant),
        "has_disclosure":("provizi" in body.casefold() or "affiliate" in body.casefold()),
        "errors":sorted(set(errors))}

def inspect_live(slug, base):
    url="https://xfit.cz/wp-json/wp/v2/posts?"+urlencode({"slug":slug,"per_page":2,
        "_fields":"id,slug,status,content,link"})
    req=Request(url,headers={"User-Agent":"XfitRevenueQA/1.0"})
    with urlopen(req,timeout=35) as response:
        posts=json.load(response)
    matches=[p for p in posts if p.get("slug")==slug and p.get("status")=="publish"]
    if len(matches)!=1: raise ValueError("missing_or_duplicate_live_post")
    body=(matches[0].get("content") or {}).get("rendered") or ""
    check=check_markdown_html(body,base)
    if not check["has_disclosure"]:check["errors"].append("missing_affiliate_disclosure")
    return {"slug":slug,"wp_post_id":matches[0]["id"],"public_url":matches[0].get("link"),
        "affiliate_count":check["merchant_link_count"],"errors":check["errors"]}

def main():
    secret=os.getenv("XFIT_AFFIL_DEFAULT_LINK","")
    if not secret:raise ValueError("missing_XFIT_AFFIL_DEFAULT_LINK")
    affiliate_signature(secret)
    reports=[inspect_live(slug,secret) for slug in SLUGS]
    safe={"state":"PASS" if all(not p["errors"] for p in reports) else "FAIL",
          "pages":reports,"no_clicks_sent":True,"no_wp_writes":True}
    print(json.dumps(safe,ensure_ascii=False))
    if safe["state"]!="PASS":sys.exit(2)

if __name__=="__main__":
    try:main()
    except Exception as exc:
        # Never print supplied affiliate URL or identifiers.
        print("XFIT_AFFILIATE_HEALTH_ERROR: "+type(exc).__name__,file=sys.stderr)
        sys.exit(2)
