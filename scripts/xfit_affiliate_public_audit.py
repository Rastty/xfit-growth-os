#!/usr/bin/env python3
"""Read-only verification that Xfit affiliate cards reach the public visitor.

Unlike an authenticated WP REST-only check, this compares the exact selected
offer CTAs and affiliate campaign parameters in source and public HTML.
No external merchant requests, WP writes, cookies, personal data or events.
Only redacted aggregate counts and enumerated failure reasons are emitted.
"""
from html import unescape
from html.parser import HTMLParser
import json
import os
import re
import sys
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit
from urllib.request import Request, urlopen

from scripts.xfit_affil_deeplink import affiliate_signature

PAGES = {
    "xfit-os-kreatin-poradce": (25455, "creatine"),
    "xfit-os-syrovatkovy-protein-porovnani": (25456, "whey"),
}
HOSTS = frozenset(("xfit.cz", "www.xfit.cz"))
MERCHANTS = frozenset(("namaximum.cz", "www.namaximum.cz"))
MAX_PUBLIC_BYTES = 2_000_000
MAX_CARDS = 12


class Cards(HTMLParser):
    """Only inspect actual product-card anchors, never unrelated site links."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.cards = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "article":
            if self.depth:
                self.depth += 1
            elif "xfit-product-card" in (a.get("class") or "").split():
                self.depth = 1
                self.current = {"anchors": []}
        if self.depth and tag == "a":
            self.current["anchors"].append({
                "href": unescape(a.get("href") or ""),
                "rel": (a.get("rel") or "").lower().split(),
                "engine": a.get("data-xfit-engine"),
                "partner": a.get("data-xfit-partner"),
                "product_id": a.get("data-xfit-product-id"),
            })

    def handle_endtag(self, tag):
        if tag == "article" and self.depth:
            self.depth -= 1
            if not self.depth:
                self.cards.append(self.current)
                self.current = None


def canonical_article(url, slug):
    p = urlsplit(url or "")
    return (
        p.scheme == "https" and p.hostname in HOSTS
        and not p.username and not p.password and p.port is None
        and not p.query and not p.fragment
        and p.path.rstrip("/") == "/" + slug
    )


def safe_affiliate_url(value, aid, bid):
    p = urlsplit(value)
    q = parse_qs(p.query, keep_blank_values=True)
    if (p.scheme != "https" or p.hostname not in MERCHANTS
            or p.username or p.password or p.port is not None
            or p.path.rstrip("/") in ("", "/") or p.fragment):
        return False
    return all((
        q.get("a_aid") == [aid],
        q.get("a_bid") == [bid],
        q.get("utm_medium") == ["affiliate"],
        q.get("utm_source") == ["pap"],
        q.get("utm_campaign") == ["affial.com"],
    ))


def comparable_href(value):
    """Ignore only harmless URL encoding/query order, not product/campaign."""
    p = urlsplit(value)
    return (p.scheme, p.hostname, p.path,
            tuple(sorted(parse_qsl(p.query, keep_blank_values=True))))


def card_evidence(body, slug, affiliate_base):
    """Keep sensitive URLs and IDs in memory; expose only safe summary."""
    if not isinstance(body, str) or not 500 <= len(body.encode("utf-8")) <= MAX_PUBLIC_BYTES:
        raise ValueError("invalid_html_body")
    engine = PAGES[slug][1]
    aid, bid = affiliate_signature(affiliate_base)
    parser = Cards()
    parser.feed(body)
    errors = set()
    if not 2 <= len(parser.cards) <= MAX_CARDS:
        errors.add("unexpected_card_count")
    observed_ids = set()
    signature = []
    for card in parser.cards:
        if len(card["anchors"]) != 1:
            errors.add("card_needs_exactly_one_link")
            continue
        item = card["anchors"][0]
        numeric = item["product_id"]
        if (item["engine"] != engine or item["partner"] != "namaximum"
                or not isinstance(numeric, str)
                or not re.fullmatch(r"[1-9][0-9]{0,9}", numeric)
                or int(numeric) > 2**31 - 1):
            errors.add("invalid_catalog_cta_metadata")
        elif numeric in observed_ids:
            errors.add("duplicate_catalog_cta")
        else:
            observed_ids.add(numeric)
        if "sponsored" not in item["rel"]:
            errors.add("missing_sponsored_rel")
        if not safe_affiliate_url(item["href"], aid, bid):
            errors.add("invalid_merchant_campaign_destination")
        signature.append((numeric, item["engine"], item["partner"],
                          comparable_href(item["href"])))
    if not ("provizi" in body.casefold() or "affiliate" in body.casefold()):
        errors.add("missing_affiliate_disclosure")
    return {
        "count": len(parser.cards),
        "metadata_count": len(observed_ids),
        "errors": sorted(errors),
        # Internal only: MUST NOT copy to any printable report.
        "_private_card_signature": signature,
    }


def read_wp_post(slug):
    url = "https://xfit.cz/wp-json/wp/v2/posts?" + urlencode({
        "slug": slug, "per_page": 2, "_fields": "id,slug,status,link,content",
    })
    req = Request(url, headers={"User-Agent": "XFITPublicAffiliateAudit/1.0"})
    with urlopen(req, timeout=25) as response:
        data = response.read(MAX_PUBLIC_BYTES + 1)
    if len(data) > MAX_PUBLIC_BYTES:
        raise ValueError("oversized_wp_response")
    posts = json.loads(data)
    if not isinstance(posts, list) or len(posts) != 1:
        raise ValueError("missing_or_duplicate_wp_article")
    return posts[0]


def read_public_page(slug):
    url = "https://xfit.cz/" + slug + "/"
    req = Request(url, headers={
        "User-Agent": "XFITPublicAffiliateAudit/1.0",
        "Cache-Control": "no-cache", "Pragma": "no-cache",
    })
    with urlopen(req, timeout=25) as response:
        if response.status != 200 or not canonical_article(response.geturl(), slug):
            raise ValueError("wrong_public_page_or_redirect")
        content = response.read(MAX_PUBLIC_BYTES + 1)
    if len(content) > MAX_PUBLIC_BYTES:
        raise ValueError("oversized_public_response")
    return content.decode("utf-8", errors="replace")


def audit_page(slug, base, *, wp_reader=read_wp_post, public_reader=read_public_page):
    if slug not in PAGES:
        raise ValueError("unapproved_article")
    expected_id, _ = PAGES[slug]
    article = wp_reader(slug)
    if (not isinstance(article, dict) or type(article.get("id")) is not int
            or article.get("id") != expected_id or article.get("slug") != slug
            or article.get("status") != "publish"
            or not canonical_article(article.get("link"), slug)):
        raise ValueError("wrong_wp_article_identity")
    source = (article.get("content") or {}).get("rendered")
    public = public_reader(slug)
    a = card_evidence(source, slug, base)
    b = card_evidence(public, slug, base)
    source_sig = a.pop("_private_card_signature")
    public_sig = b.pop("_private_card_signature")
    errors = {"wp_" + e for e in a["errors"]}
    errors.update("public_" + e for e in b["errors"])
    if source_sig != public_sig:
        errors.add("wp_public_offer_or_tracking_mismatch")
    return {
        "slug": slug, "wp_post_id": expected_id,
        "public_url": "https://xfit.cz/" + slug + "/",
        "source_card_count": a["count"],
        "public_card_count": b["count"],
        "source_cta_metadata_count": a["metadata_count"],
        "public_cta_metadata_count": b["metadata_count"],
        "offer_destinations_match": source_sig == public_sig,
        "errors": sorted(errors),
    }


def main():
    # Never print or persist the affiliate link, even on exceptions.
    base = os.environ.get("XFIT_AFFIL_DEFAULT_LINK", "")
    if not base:
        raise ValueError("affiliate_secret_missing")
    affiliate_signature(base)
    pages = [audit_page(slug, base) for slug in PAGES]
    state = "PUBLIC_AFFILIATE_PARITY_VERIFIED" if all(not p["errors"] for p in pages) else "BLOCKED_PUBLIC_OR_TRACKING_MISMATCH"
    print(json.dumps({
        "state": state, "pages": pages, "wordpress_writes": 0,
        "merchant_clicks_sent": 0, "ga4_events": "UNKNOWN",
        "affial_orders": "UNKNOWN", "commission": "UNKNOWN",
    }, ensure_ascii=False))
    return 0 if state == "PUBLIC_AFFILIATE_PARITY_VERIFIED" else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        # Never log the exception text: it can contain the WP/affiliate URL.
        print("XFIT_PUBLIC_AFFILIATE_AUDIT_ERROR: " + type(exc).__name__, file=sys.stderr)
        sys.exit(2)
