#!/usr/bin/env python3
"""GreenMedical Heureka feed reconnaissance for Xfit.

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
ALLOWED_HOST = "greenmedical.venalio.com"
BLOCK_TERMS = re.compile(r"(?i)\b(cbd|thc|hhc|kratom|steroid\w*|nikotin\w*|nicotine|marihuan\w*|konopn\w*\s+kv[eě]t)\b")
DROP_QUERY_KEYS = {"secretkey", "token", "api_key", "apikey", "password", "authorization", "auth"}

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
            "affiliate_url": None,
            "publish_ready": False,
        })
    return offers, skipped

def fetch_feed():
    url = os.getenv("XFIT_GREENMEDICAL_FEED_URL", "").strip()
    if not url:
        raise ValueError("Set XFIT_GREENMEDICAL_FEED_URL in encrypted GitHub Actions Secrets")
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

def validate_ehub_link():
    link = os.getenv("XFIT_EHUB_DEFAULT_LINK", "").strip()
    if not link:
        return "not_configured"
    p = urllib.parse.urlsplit(link)
    qs = urllib.parse.parse_qs(p.query)
    if (p.scheme != "https" or p.hostname != "ehub.cz" or
        p.path != "/system/scripts/click.php" or
        not qs.get("a_aid") or not qs.get("a_bid")):
        raise ValueError("eHUB redirect is not a valid default click URL")
    return "default_link_validated_but_product_deeplinks_unverified"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="reports/private-greenmedical-catalog.json")
    args=ap.parse_args()
    offers,skipped = parse_feed(fetch_feed())
    report = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "merchant": "greenmedical_feed_unverified_match",
        "status": "PRIVATE_REVIEW_REQUIRED",
        "currency_assumption": "CZK; confirm source feed currency before using offers",
        "affiliate_default_link": validate_ehub_link(),
        "product_deeplinks": "NOT_VERIFIED",
        "offer_count": len(offers),
        "skipped": dict(skipped),
        "categories_top": Counter(o["category"] for o in offers).most_common(30),
        "products": offers,
    }
    out=Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    # Print statistics only, never the secret URL or product tracking destinations.
    print(json.dumps({"state":"private_feed_normalized", "items":len(offers),
        "skipped":dict(skipped), "affiliate_status": report["affiliate_default_link"],
        "public_site_modified":False}, ensure_ascii=False))
    if not offers:
        raise ValueError("Feed contained no valid suitable offers")

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("XFIT_FEED_ERROR: "+str(exc).split("https://")[0], file=__import__("sys").stderr)
        raise SystemExit(2)
