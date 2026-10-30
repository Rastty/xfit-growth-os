#!/usr/bin/env python3
"""Classify an owner-generated Affial product deeplink without leaking URLs.

A supplied real product deeplink is used only to understand the campaign's
tracking-link structure. This does NOT prove credited orders or commission.
No redirects are followed and no clicks sent.
"""
import json
import os
import sys
from urllib.parse import urlsplit, parse_qs

MERCHANTS={"www.namaximum.cz","namaximum.cz"}
AFFIL_HOSTS={"login.affial.com","affial.com","www.affial.com"}

def query(url):
    return parse_qs(urlsplit(url).query, keep_blank_values=False)

def affiliate_signature(link):
    p=urlsplit(link)
    q=query(link)
    if p.scheme!="https" or p.hostname not in MERCHANTS:
        raise ValueError("Base affiliate link must target HTTPS NaMaximum")
    if q.get("utm_campaign")!=["affial.com"] or q.get("utm_source")!=["pap"]:
        raise ValueError("Affial campaign attribution parameters missing")
    ids=(q.get("a_aid",[""])[0],q.get("a_bid",[""])[0])
    if not all(ids):
        raise ValueError("Affial publisher/campaign ID missing")
    return ids

def classify_product_link(base, sample):
    aid,bid=affiliate_signature(base)
    p=urlsplit(sample)
    if p.scheme!="https" or p.username or p.password:
        raise ValueError("Product link is not a valid HTTPS URL")
    q=query(sample)
    if (q.get("a_aid",[""])[0],q.get("a_bid",[""])[0])!=(aid,bid):
        raise ValueError("Product deeplink IDs do not match campaign")
    if p.hostname in MERCHANTS:
        if not p.path or p.path=="/":
            raise ValueError("Product example points to shop homepage")
        if q.get("utm_campaign")!=["affial.com"]:
            raise ValueError("Missing campaign attribution")
        return {"scheme":"merchant_direct_query","format_consistent":True,
                "campaign_conversion_verified":False,"publish_ready":False}
    if p.hostname in AFFIL_HOSTS:
        dest=q.get("desturl",[""])[0]
        to=urlsplit(dest)
        if to.scheme!="https" or to.hostname not in MERCHANTS or to.path in ("","/"):
            raise ValueError("Redirect destination must be exact NaMaximum product")
        return {"scheme":"affial_redirect_desturl","format_consistent":True,
                "campaign_conversion_verified":False,"publish_ready":False}
    raise ValueError("Unrecognized product tracking host")

if __name__=="__main__":
    base=os.getenv("XFIT_AFFIL_DEFAULT_LINK","")
    product=os.getenv("XFIT_AFFIL_SAMPLE_PRODUCT_LINK","")
    if not base or not product:
        print(json.dumps({"status":"sample_affiliate_product_link_not_configured","public_site_modified":False}))
        sys.exit(0)
    try:
        result=classify_product_link(base,product)
        print(json.dumps(result,ensure_ascii=False))
    except ValueError:
        # No user-generated URL or tracking ID gets into GitHub Logs.
        print("XFIT_DEEPLINK_CHECK_FAILED: campaign sample structure does not match base URL",file=sys.stderr)
        sys.exit(2)
