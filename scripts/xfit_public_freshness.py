#!/usr/bin/env python3
"""Read-only source-versus-public freshness probe for XFIT decision funnel.

No uploads, retries of POST, user events, cookies, or full WP content in logs.
Helps distinguish a successful WP write from public cache/render staleness.
"""
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from html.parser import HTMLParser

from scripts.wp_publish import PublishError, normalized_base, wp_request

TARGETS = (
    ("xfit-os-doplnky-pro-zacatecniky", 25458, "Nejste si jistí, zda potřebujete protein, kreatin"),
    ("xfit-os-kreatin-nebo-protein", 25504, "Jak poznat, co je skutečně levnější?"),
    ("xfit-os-kreatin-poradce", 25455, "Dvě cesty k výběru podle ceny"),
    ("xfit-os-syrovatkovy-protein-porovnani", 25456, "Dvě cesty k výběru podle ceny"),
)
ALLOWED_CACHE_HEADERS = ("Age", "Cache-Control", "X-Cache", "X-LiteSpeed-Cache", "CF-Cache-Status", "X-Proxy-Cache")
REPORT = Path("reports/xfit-public-freshness.json")


def owns_public_url(url, slug):
    u = urllib.parse.urlsplit(url or "")
    return (u.scheme == "https" and u.hostname in ("xfit.cz", "www.xfit.cz")
            and not u.username and not u.password and not u.port and not u.query
            and not u.fragment and u.path.rstrip("/") == "/" + slug)


def visible_has(html_source, phrase):
    text = html.unescape(re.sub(r"<[^>]+>", " ", html_source))
    return " ".join(phrase.casefold().split()) in " ".join(text.casefold().split())


class ProductCards(HTMLParser):
    """Capture visible card copy including actual unit prices, not only a heading."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.buffer = []
        self.cards = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "article":
            if self.depth:
                self.depth += 1
            elif "xfit-product-card" in (a.get("class") or "").split():
                self.depth = 1
                self.buffer = []
        elif self.depth and tag in ("h3","p","strong","a","li"):
            self.buffer.append(" ")

    def handle_data(self, value):
        if self.depth:
            self.buffer.append(value)

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag == "article":
            self.depth -= 1
            if not self.depth:
                text = " ".join(html.unescape("".join(self.buffer)).casefold().split())
                self.cards.append(text)
        elif tag in ("h3","p","strong","a","li"):
            self.buffer.append(" ")


def product_card_texts(value):
    parsed = ProductCards()
    parsed.feed(value)
    return parsed.cards


# Only compare already-visible, non-sensitive commercial figures. Never write
# affiliate tracking URLs, WP HTML, or source article bodies into artifacts.
COMMERCIAL_FACT_PATTERNS = {
    "price_czk": re.compile(r"\bcena:\s*([0-9][0-9\s.,]*)\s*kč\b", re.I),
    "package_g": re.compile(r"\bbalení:\s*(\d+)\s*g\b", re.I),
    "unit_price_czk": re.compile(
        r"\bcena za 100 g prášku:\s*([0-9][0-9\s.,]*)\s*kč\b", re.I),
}


def commercial_facts(card):
    facts = {}
    for field, pattern in COMMERCIAL_FACT_PATTERNS.items():
        match = pattern.search(card)
        facts[field] = "".join(match.group(1).split()) if match else None
    return facts


def card_drift_diagnostics(source_cards, public_cards):
    """Give operators actionable discrepancy categories without leaking links."""
    mismatched = []
    commercial_drift = []
    missing_fields = []
    text_only = []
    for index in range(max(len(source_cards), len(public_cards))):
        left = source_cards[index] if index < len(source_cards) else None
        right = public_cards[index] if index < len(public_cards) else None
        if left == right:
            continue
        pos = index + 1
        mismatched.append(pos)
        if left is None or right is None:
            missing_fields.append(pos)
            continue
        a, b = commercial_facts(left), commercial_facts(right)
        if any(a[k] is None or b[k] is None for k in COMMERCIAL_FACT_PATTERNS):
            missing_fields.append(pos)
        elif a != b:
            commercial_drift.append(pos)
        else:
            text_only.append(pos)
    return {
        "mismatched_card_positions": mismatched,
        "commercial_fact_drift_positions": commercial_drift,
        "unparsed_commercial_fact_positions": missing_fields,
        "noncommercial_copy_drift_positions": text_only,
    }


def public_get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "XfitPublicFreshnessMonitor/1.0",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=25) as response:
        final = response.geturl()
        if not owns_public_url(final, urllib.parse.urlsplit(url).path.strip("/")) or response.status != 200:
            raise PublishError("Unexpected public page response/redirect")
        page = response.read(2000000).decode("utf-8", errors="replace")
        cache = {k: response.headers.get(k) for k in ALLOWED_CACHE_HEADERS if response.headers.get(k)}
        return page, cache


def probe(target, *, read_post=None, read_public=None):
    slug, post_id, marker = target
    read_post = read_post or (lambda ident: wp_request(
        normalized_base(), "posts/" + str(ident) +
        "?context=edit&_fields=id,slug,status,content,link"))
    read_public = read_public or public_get
    post = read_post(post_id)
    if post.get("id") != post_id or post.get("slug") != slug or post.get("status") != "publish":
        raise PublishError("WordPress identity/status drift for " + slug)
    if not owns_public_url(post.get("link"), slug):
        raise PublishError("WordPress returned a noncanonical URL for " + slug)
    raw = (post.get("content") or {}).get("raw")
    if not isinstance(raw, str) or "<!-- xfit-growth-os:v1 -->" not in raw:
        raise PublishError("Missing controlled WordPress source for " + slug)
    source_has = marker.casefold() in html.unescape(raw).casefold()
    try:
        page, headers = read_public(post["link"])
    except (OSError, ValueError, PublishError) as exc:
        return {"slug": slug, "post_id": post_id, "status": "PUBLIC_READ_ERROR",
                "wp_source_has_target": source_has, "reason": type(exc).__name__}
    public_has = visible_has(page, marker)
    product = slug in {"xfit-os-kreatin-poradce", "xfit-os-syrovatkovy-protein-porovnani"}
    source_cards = product_card_texts(raw) if product else []
    public_cards = product_card_texts(page) if product else []
    cards_match = (len(source_cards) >= 2 and source_cards == public_cards) if product else True
    diagnostics = card_drift_diagnostics(source_cards, public_cards) if product else {}
    status = ("SOURCE_NOT_UPDATED" if not source_has
              else "WP_SOURCE_INCOMPLETE" if product and len(source_cards) < 2
              else "PUBLIC_FRESH" if public_has and cards_match
              else "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
    return {"slug": slug, "post_id": post_id, "status": status,
            "wp_source_has_target": source_has, "public_has_target": public_has,
            "wp_product_cards": len(source_cards), "public_product_cards": len(public_cards),
            "product_cards_match": cards_match, "cache_headers": headers,
            **diagnostics}


def main():
    rows = []
    for target in TARGETS:
        try:
            rows.append(probe(target))
        except (PublishError, OSError, ValueError) as exc:
            rows.append({"slug": target[0], "post_id": target[1],
                         "status": "BLOCKED_MANUAL_REVIEW", "reason": type(exc).__name__})
    report = {"site": "https://xfit.cz", "mode": "read_only_freshness",
              "wordpress_writes": 0, "results": rows}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if all(row.get("status") == "PUBLIC_FRESH" for row in rows) else 2


if __name__ == "__main__":
    sys.exit(main())
