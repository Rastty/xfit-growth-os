#!/usr/bin/env python3
"""NaMaximum product feed reconnaissance for Xfit (hosted on GreenMedical Venalio).

Read-only: downloads a provider feed from an encrypted GitHub Actions Secret,
validates XML, normalizes offers and writes a private Actions artifact.
Never publishes to WordPress or commits feed data.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request
from xml.etree import ElementTree as ET

MAX_BYTES = 35 * 1024 * 1024
MAX_ITEMS = 100000
ALLOWED_HOST = "greenmedical.venalio.com"  # feed infrastructure, NOT the seller
PRODUCT_HOSTS = {"namaximum.cz", "www.namaximum.cz"}
BLOCK_TERMS = re.compile(r"(?i)\b(cbd|thc|hhc|kratom|steroid\w*|nikotin\w*|nicotine|marihuan\w*|konopn\w*\s+kv[eě]t)\b")
DROP_QUERY_KEYS = {"secretkey", "token", "api_key", "apikey", "password", "authorization", "auth", "gclid", "fbclid", "a_aid", "a_bid", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"}

def local(tag):
    return tag.rsplit("}", 1)[-1].upper()

def value(element, *names):
    names = {n.upper() for n in names}
    for child in element:
        if local(child.tag) in names and child.text:
            return " ".join(child.text.split())
    return ""

def safe_product_url(text):
    if not text:
        return ""
    parsed = urllib.parse.urlsplit(text)
    if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
        return ""
    safe_query = urllib.parse.urlencode([
        (k,v) for k,v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in DROP_QUERY_KEYS
    ])
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, safe_query, ""))

def parse_price(value):
    if not value:
        return None
    try:
        n = float(value.strip().replace(" ", "").replace(",", "."))
        if n <= 0 or n > 1000000:
            return None
        return round(n, 2)
    except ValueError:
        return None

def parse_feed(xml_bytes):
    # Reject XML DTDs/entities: we only expect a simple product export.
    prefix = xml_bytes[:2048].upper()
    if b"<!DOCTYPE" in prefix or b"<!ENTITY" in prefix:
        raise ValueError("DTD/entity declarations are not supported")
    offers = []
    skipped = Counter()
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError("Malformed XML feed") from exc
    items = (el for el in root.iter() if local(el.tag) in ("SHOPITEM", "ITEM"))
    for i, el in enumerate(items):
        if i >= MAX_ITEMS:
            raise ValueError("Feed exceeds maximum item count")
        title = value(el, "PRODUCTNAME", "PRODUCT", "NAME")
        price = parse_price(value(el, "PRICE_VAT", "PRICE"))
        category = value(el, "CATEGORYTEXT", "CATEGORY")
        if not title or price is None:
            skipped["missing_title_or_price"] += 1
            continue
        if BLOCK_TERMS.search(title + " " + category):
            skipped["restricted_or_sensitive_product"] += 1
            continue
        item_id = value(el, "ITEM_ID", "ITEMID", "ID")[:120]
        link = safe_product_url(value(el, "URL", "LINK"))
        image = safe_product_url(value(el, "IMGURL", "IMAGE", "IMGURL_ALTERNATIVE"))
        # Merchant identity is proved by EACH item URL, not the feed hosting CDN.
        if urllib.parse.urlsplit(link).hostname not in PRODUCT_HOSTS:
            skipped["not_namaximum_product_link"] += 1
            continue
        offers.append({
            "id": item_id or str(i + 1),
            "title": title[:250],
            "category": category[:300],
            "price_czk": price,  # Verify feed's actual currency before use in public UI.
            "manufacturer": value(el, "MANUFACTURER", "BRAND")[:150],
            "ean": value(el, "EAN", "GTIN")[:32],
            "source_url": link,
            "image_url": image,
            "stock_indicator": value(el, "DELIVERY_DATE", "AVAILABILITY")[:80],
            "merchant": "NaMaximum.cz",
            "affiliate_url": None,  # Do NOT infer a commissioned product link from a Heureka CPC link.
            "publish_ready": False,
        })
    return offers, skipped

def fetch_feed():
    # Legacy secret alias is kept so the already-instructed configuration still works.
    url = (os.getenv("XFIT_NAMAXIMUM_FEED_URL") or os.getenv("XFIT_GREENMEDICAL_FEED_URL") or "").strip()
    if not url:
        raise ValueError("Set XFIT_NAMAXIMUM_FEED_URL (or legacy XFIT_GREENMEDICAL_FEED_URL) in GitHub Actions Secrets")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or parsed.path != "/feeds/heureka":
        raise ValueError("Unexpected feed host/path")
    if not any(k.lower()=="secretkey" for k, _ in urllib.parse.parse_qsl(parsed.query)):
        raise ValueError("Feed URL lacks expected private authorization parameter")
    request = urllib.request.Request(url, headers={"User-Agent": "XfitGrowthOS-FeedValidation/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            content_len = response.headers.get("Content-Length")
            if content_len and int(content_len) > MAX_BYTES:
                raise ValueError("Feed too large")
            data = response.read(MAX_BYTES + 1)
    except Exception as exc:
        # Never include the URL in logs: it contains a feed authorization secret.
        raise ValueError("Feed fetch failed: " + type(exc).__name__) from None
    if len(data) > MAX_BYTES:
        raise ValueError("Feed too large")
    return data

def validate_affiliate_link(link=None):
    """Validate affiliate campaign shape without following click links.

    The tracked advertiser is NaMaximum.cz via Affial (Post Affiliate Pro).
    GreenMedical/Venalio hosts the XML, but merchant identity comes from
    SHOPITEM/URL, not the feed infrastructure hostname.
    """
    if link is None:
        link = os.getenv("XFIT_AFFIL_DEFAULT_LINK", "").strip()
    if not link:
        return "not_configured"
    p = urllib.parse.urlsplit(link)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        return "invalid_https_tracking_url"
    host = p.hostname.lower()
    q = urllib.parse.parse_qs(p.query)
    if host in ("namaximum.cz", "www.namaximum.cz"):
        if (
            q.get("utm_campaign") == ["affial.com"] and
            q.get("utm_source") == ["pap"] and
            bool(q.get("a_aid")) and bool(q.get("a_bid"))
        ):
            return "affial_namaximum_tracking_format_valid__product_deeplinks_unverified"
        return "namaximum_link_missing_expected_affial_parameters"
    if host in ("ehub.cz", "www.ehub.cz"):
        return "ehub_link_is_not_the_confirmed_affial_namaximum_campaign"
    if host in ("affial.com", "www.affial.com"):
        return "affial_network_link_requires_campaign_review"
    return "unrecognized_affiliate_link_needs_manual_review"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="reports/private-greenmedical-catalog.json")
    args=ap.parse_args()
    offers,skipped = parse_feed(fetch_feed())
    report = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "merchant": "namaximum.cz",
        "feed_host": ALLOWED_HOST,
        "merchant_match": bool(offers) and not skipped.get("not_namaximum_product_link"),
        "warning": "Correct merchant confirmed from item URLs. Product-specific Affial deeplink and commission tracking NOT yet verified.",
        "status": "PRIVATE_REVIEW_REQUIRED",
        "currency_assumption": "CZK; confirm source feed currency before using offers",
        "affiliate_default_link": validate_affiliate_link(),
        "product_deeplinks": "NOT_VERIFIED",
        "offer_count": len(offers),
        "skipped": dict(skipped),
        "categories_top": Counter(o["category"] for o in offers).most_common(30),
        "products": offers,
    }
    out=Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    # Public GitHub Actions artifacts can be downloaded by repository visitors.
    # Upload only a redacted summary, never the full catalog or feed access URL.
    summary = {
        "fetched_at_utc": report["fetched_at_utc"],
        "merchant": report["merchant"],
        "source_url_merchant_verified": report["merchant_match"],
        "offers": report["offer_count"],
        "skipped": report["skipped"],
        "categories_top": report["categories_top"],
        "affiliate_link_status": report["affiliate_default_link"],
        "product_deeplinks": "NOT_VERIFIED",
        "published_to_site": False,
    }
    summary_path = out.parent / "affiliate-feed-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    # Aggregated diagnostics are safe to show in public Actions logs.
    with_category = sum(bool(o["category"]) for o in offers)
    with_image = sum(bool(o["image_url"]) for o in offers)
    with_ean = sum(bool(o["ean"]) for o in offers)
    print(json.dumps({
        "state": "private_feed_normalized", "items": len(offers),
        "skipped": dict(skipped), "merchant_verified": report["merchant_match"],
        "top_categories": report["categories_top"][:12],
        "with_category": with_category, "with_image": with_image, "with_ean": with_ean,
        "affiliate_status": report["affiliate_default_link"],
        "product_deeplinks": "NOT_VERIFIED",
        "public_site_modified": False
    }, ensure_ascii=False))
    if not offers:
        raise ValueError("Feed contained no valid suitable offers")

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("XFIT_FEED_ERROR: "+str(exc).split("https://")[0], file=__import__("sys").stderr)
        raise SystemExit(2)
