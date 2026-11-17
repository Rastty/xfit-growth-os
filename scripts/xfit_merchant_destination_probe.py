#!/usr/bin/env python3
"""Read-only, non-affiliate merchant URL diagnostic for XFIT public cards.

This is deliberately NOT a stock checker or a release gate. It never follows
tracked Affial links, never contacts a non-allowlisted host, and prints only
aggregate statuses. A robot-visible 404/410 is a review signal, not proof that
a human buyer cannot purchase an item.
"""
import json
import os
import re
import sys
from collections import Counter
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from scripts.xfit_affil_deeplink import affiliate_signature
from scripts.xfit_affiliate_public_audit import (
    Cards, MERCHANTS, PAGES, read_public_page, safe_affiliate_url,
    variant_identity_status,
)

MAX_PROBES = 12
TIMEOUT_SECONDS = 9
STATUS_AVAILABLE = "HTTP_2XX"
STATUS_REVIEW = "SUSPECT_404_OR_410"
STATUS_UNKNOWN = "UNKNOWN_ROBOT_OR_NETWORK"


def clean_product_destination(tracked, product_id, aid, bid):
    """Keep only the actual merchant product path and validated variant.

    No Affial/PAP IDs, UTM campaign, data1/data2 or referrer are sent in the
    diagnostic request. Reject malformed destinations before any network I/O.
    """
    if not safe_affiliate_url(tracked, aid, bid):
        raise ValueError("invalid_affiliate_card")
    if variant_identity_status(tracked, product_id) != "MATCH":
        raise ValueError("unverified_merchant_variant")
    p = urlsplit(tracked)
    if (p.hostname not in MERCHANTS or p.port is not None or p.fragment
            or p.path.startswith("//") or p.path.rstrip("/") in ("", "/")):
        raise ValueError("unsafe_merchant_destination")
    variant = parse_qs(p.query)["variant"][0]
    return urlunsplit(("https", p.hostname, p.path, urlencode({"variant": variant}), ""))


def card_destinations(public_html, slug, base):
    if slug not in PAGES:
        raise ValueError("unapproved_advisor")
    aid, bid = affiliate_signature(base)
    parser = Cards()
    parser.feed(public_html)
    if not 2 <= len(parser.cards) <= 6:
        raise ValueError("unexpected_public_product_count")
    destinations = []
    for card in parser.cards:
        if len(card["anchors"]) != 1:
            raise ValueError("ambiguous_product_card")
        item = card["anchors"][0]
        if (item["engine"] != PAGES[slug][1]
                or item["partner"] != "namaximum"
                or "sponsored" not in item["rel"]):
            raise ValueError("invalid_card_context")
        destinations.append(clean_product_destination(
            item["href"], item["product_id"], aid, bid))
    if len(set(destinations)) != len(destinations):
        raise ValueError("repeated_merchant_destination")
    return destinations


class MerchantOnlyRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        p = urlsplit(newurl)
        previous = urlsplit(req.full_url)
        # Never contact non-merchant targets even if the merchant redirects.
        # A redirected product path or new query parameter is not evidence
        # that the original advertised variant is still purchasable.
        if (p.scheme != "https" or p.hostname not in MERCHANTS
                or p.username or p.password or p.port is not None
                or p.path.startswith("//") or p.path != previous.path
                or p.query != previous.query or p.fragment):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def probe_clean_destination(clean_url, opener=None):
    p = urlsplit(clean_url)
    if (p.scheme != "https" or p.hostname not in MERCHANTS
            or p.username or p.password or p.port is not None
            or p.path.startswith("//")
            or set(parse_qs(p.query)) != {"variant"}
            or len(parse_qs(p.query)["variant"]) != 1
            or not re.fullmatch(r"[1-9][0-9]{0,9}",
                                parse_qs(p.query)["variant"][0])):
        raise ValueError("unsafe_probe_url")
    fetcher = opener or build_opener(MerchantOnlyRedirect())
    req = Request(clean_url, headers={
        "User-Agent": "XFITMerchantProductDiagnostic/1.0",
        "Accept": "text/html",
        "Cache-Control": "no-cache",
    })
    try:
        # GET (not HEAD) avoids merchants that treat HEAD as missing.
        # Opening a response without reading the body sends no extra page
        # requests and avoids storing customer-facing merchant HTML.
        with fetcher.open(req, timeout=TIMEOUT_SECONDS) as response:
            return STATUS_AVAILABLE if 200 <= response.status < 300 else STATUS_UNKNOWN
    except HTTPError as exc:
        return STATUS_REVIEW if exc.code in (404, 410) else STATUS_UNKNOWN
    except (URLError, TimeoutError, ConnectionError, OSError):
        return STATUS_UNKNOWN


def diagnose(pages, base, probe=probe_clean_destination):
    all_urls = []
    per_page = []
    for slug in PAGES:
        urls = card_destinations(pages[slug], slug, base)
        all_urls.extend(urls)
        per_page.append((slug, urls))
    if len(all_urls) > MAX_PROBES:
        raise ValueError("too_many_merchant_requests")
    # A non-affiliate request is made at most once per distinct product URL.
    checked = {url: probe(url) for url in dict.fromkeys(all_urls)}
    return [{"slug": slug, "products_checked": len(urls),
             "statuses": dict(sorted(Counter(checked[u] for u in urls).items()))}
            for slug, urls in per_page]


def main():
    base = os.getenv("XFIT_AFFIL_DEFAULT_LINK", "")
    if not base:
        raise ValueError("missing_affiliate_config")
    affiliate_signature(base)
    pages = {slug: read_public_page(slug) for slug in PAGES}
    results = diagnose(pages, base)
    print(json.dumps({
        "state": "MERCHANT_DESTINATION_DIAGNOSTIC_ONLY",
        "pages": results,
        "affiliate_click_requests": 0,
        "wordpress_writes": 0,
        "stock_verified": False,
        "manual_review_required": any(
            p["statuses"].get(STATUS_REVIEW, 0) for p in results),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Error messages/URLs may contain campaign IDs. Emit type only.
        print("XFIT_MERCHANT_PROBE_ERROR: " + type(exc).__name__, file=sys.stderr)
        sys.exit(2)
