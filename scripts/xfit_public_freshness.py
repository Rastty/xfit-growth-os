#!/usr/bin/env python3
"""Read-only source-versus-public freshness probe for XFIT decision funnel.

No uploads, retries of POST, user events, cookies, or full WP content in logs.
Helps distinguish a successful WP write from public cache/render staleness.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo
import html
import json
import re
import sys
import time
import urllib.error
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
                # WordPress may display an en dash / curly quote instead of the
                # source punctuation. Ignore typography only, never amounts or words.
                text = typography_key(" ".join(html.unescape("".join(self.buffer)).casefold().split()))
                self.cards.append(text)
        elif tag in ("h3","p","strong","a","li"):
            self.buffer.append(" ")


def product_card_texts(value):
    parsed = ProductCards()
    parsed.feed(value)
    return parsed.cards


class ProductCardIdentity(HTMLParser):
    """Extract product title and merchant destination without logging URLs."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.in_heading = False
        self.heading = []
        self.links = []
        self.items = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "article":
            if self.depth:
                self.depth += 1
            elif "xfit-product-card" in (attributes.get("class") or "").split():
                self.depth = 1
                self.in_heading = False
                self.heading = []
                self.links = []
        elif self.depth:
            if tag == "h3":
                self.in_heading = True
            elif tag == "a":
                rel = (attributes.get("rel") or "").lower().split()
                self.links.append((attributes.get("href"), "sponsored" in rel))

    def handle_data(self, data):
        if self.depth and self.in_heading:
            self.heading.append(data)

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag == "h3":
            self.in_heading = False
        elif tag == "article":
            self.depth -= 1
            if not self.depth:
                title = " ".join(html.unescape("".join(self.heading)).casefold().split())
                self.items.append((title, self.links[:]))


def product_card_identities(value):
    parser = ProductCardIdentity()
    parser.feed(value)
    return parser.items


def safe_affiliate_card(identity):
    """Each public card must have exactly one disclosed HTTPS product link."""
    title, links = identity
    if not title or len(links) != 1:
        return False
    href, sponsored = links[0]
    parsed = urllib.parse.urlsplit(href or "")
    params = urllib.parse.parse_qs(parsed.query)
    return (
        sponsored and parsed.scheme == "https"
        and parsed.hostname in ("namaximum.cz", "www.namaximum.cz")
        and not parsed.username and not parsed.password and not parsed.port
        and parsed.path.rstrip("/") not in ("", "/")
        and params.get("utm_medium") == ["affiliate"]
        and bool(params.get("a_aid")) and bool(params.get("a_bid"))
    )


class CTAMetadata(HTMLParser):
    """Report only attribute coverage, never product IDs or tracking URLs."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.links = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "article":
            if self.depth:
                self.depth += 1
            elif "xfit-product-card" in (values.get("class") or "").split():
                self.depth = 1
        elif self.depth and tag == "a" and "sponsored" in (
                values.get("rel") or "").split():
            self.links.append((
                values.get("data-xfit-engine"),
                values.get("data-xfit-partner"),
                values.get("data-xfit-product-id"),
            ))

    def handle_endtag(self, tag):
        if tag == "article" and self.depth:
            self.depth -= 1


def cta_metadata(raw):
    parsed = CTAMetadata()
    parsed.feed(raw)
    return parsed.links


def metadata_readiness(source, public, engine, expected_cards):
    """Read-only triage of WP vs public metadata, never claim GA4 events."""
    valid = lambda xs: (
        len(xs) == expected_cards >= 2
        and all(row[0] == engine and row[1] == "namaximum"
                and isinstance(row[2], str)
                and re.fullmatch(r"[1-9][0-9]{0,9}", row[2])
                and int(row[2]) <= 2**31 - 1
                for row in xs))
    src_valid = valid(source)
    pub_valid = valid(public)
    return {
        "source_cta_metadata_count": len(source),
        "public_cta_metadata_count": len(public),
        "source_cta_metadata_valid": src_valid,
        "public_cta_metadata_valid": pub_valid,
        "cta_metadata_match": src_valid and pub_valid and source == public,
        "cta_measurement_stage": (
            "PUBLIC_METADATA_VERIFIED" if src_valid and pub_valid and source == public
            else "SOURCE_METADATA_INCOMPLETE" if not src_valid
            else "PUBLIC_METADATA_MISSING_OR_DIFFERENT"),
    }


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


def typography_key(text):
    """Classify harmless punctuation transforms; never use to approve a page."""
    translation = str.maketrans({
        "–": "-", "—": "-", "−": "-",
        "‘": "'", "’": "'", "“": '"', "”": '"',
    })
    return " ".join(text.translate(translation).split())


def card_drift_diagnostics(source_cards, public_cards, source_identities=None, public_identities=None):
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
    source_identities = source_identities or []
    public_identities = public_identities or []
    title_drift = []
    typographic_title_drift = []
    substantive_title_drift = []
    link_drift = []
    unsafe_links = []
    for index in range(max(len(source_identities), len(public_identities))):
        left = source_identities[index] if index < len(source_identities) else None
        right = public_identities[index] if index < len(public_identities) else None
        if left is None or right is None:
            title_drift.append(index + 1)
            link_drift.append(index + 1)
            unsafe_links.append(index + 1)
            continue
        if left[0] != right[0]:
            title_drift.append(index + 1)
            if typography_key(left[0]) == typography_key(right[0]):
                typographic_title_drift.append(index + 1)
            else:
                substantive_title_drift.append(index + 1)
        if left[1] != right[1]:
            link_drift.append(index + 1)
        if not safe_affiliate_card(left) or not safe_affiliate_card(right):
            unsafe_links.append(index + 1)
    return {
        "product_title_drift_positions": title_drift,
        "typographic_title_drift_positions": typographic_title_drift,
        "substantive_title_drift_positions": substantive_title_drift,
        "affiliate_link_drift_positions": link_drift,
        "unsafe_affiliate_link_positions": unsafe_links,
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
    # Public reads are safe to retry; POSTs are never retried here.
    # Intermittent WEDOS TLS/HTTP issues must not be confused with stale prices.
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                final = response.geturl()
                if (not owns_public_url(final, urllib.parse.urlsplit(url).path.strip("/"))
                        or response.status != 200):
                    raise PublishError("Unexpected public page response/redirect")
                page = response.read(2000000).decode("utf-8", errors="replace")
                cache = {k: response.headers.get(k) for k in ALLOWED_CACHE_HEADERS
                         if response.headers.get(k)}
                return page, cache
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 502, 503, 504) or attempt == 2:
                raise
        except OSError:
            if attempt == 2:
                raise
        time.sleep(2 * (attempt + 1))
    raise PublishError("Unexpected exhausted public read retry")


class CatalogRetrievalNotes(HTMLParser):
    """Capture only the branded feed-retrieval notice, never product URLs."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = False
        self.buffer = []
        self.notices = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "p" and "xfit-feed-retrieval" in (
                values.get("class") or "").split():
            self.active = True
            self.buffer = []

    def handle_data(self, data):
        if self.active:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "p" and self.active:
            self.notices.append(" ".join("".join(self.buffer).split()))
            self.active = False
            self.buffer = []


def _catalog_notes(value):
    parser = CatalogRetrievalNotes()
    parser.feed(value)
    return parser.notices


def _catalog_date(note):
    match = re.search(r"\\b([0-3]?[0-9])\\.\\s+([01]?[0-9])\\.\\s+(20[0-9]{2})\\b", note)
    if not match:
        return None
    try:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    except ValueError:
        return None


def catalog_retrieval_readiness(source, public, *, today=None):
    """Read-only fail-closed evidence; return no raw price, token or timestamp."""
    original, exposed = _catalog_notes(source), _catalog_notes(public)
    if (len(original) != 1 or not _catalog_date(original[0]) or
            "Datum označuje načtení katalogu" not in original[0]):
        stage = "SOURCE_DATE_MISSING_OR_INVALID"
    else:
        day = today if today is not None else datetime.now(
            ZoneInfo("Europe/Prague")).date()
        age = (day - _catalog_date(original[0])).days
        if not 0 <= age <= 2:
            stage = "SOURCE_DATE_STALE_OR_IN_FUTURE"
        elif (len(exposed) != 1 or
              typography_key(original[0]) != typography_key(exposed[0])):
            stage = "PUBLIC_DATE_MISSING_OR_DIFFERENT"
        else:
            stage = "PUBLIC_DATE_VERIFIED"
    return {
        "catalog_retrieval_stage": stage,
        "source_retrieval_notice_count": len(original),
        "public_retrieval_notice_count": len(exposed),
        "catalog_date_source_public_match": stage == "PUBLIC_DATE_VERIFIED",
    }


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
    source_identities = product_card_identities(raw) if product else []
    public_identities = product_card_identities(page) if product else []
    title_integrity = (len(source_identities) == len(public_identities)
                       == len(source_cards) >= 2
                       and all(typography_key(a[0]) == typography_key(b[0])
                               for a, b in zip(
                                   source_identities, public_identities))) if product else True
    link_integrity = (len(source_identities) == len(public_identities)
                      == len(source_cards) >= 2
                      and all(a[1] == b[1] for a, b in zip(
                          source_identities, public_identities))
                      and all(safe_affiliate_card(x) for x in source_identities)
                      and all(safe_affiliate_card(x) for x in public_identities)) if product else True
    cards_match = (len(source_cards) >= 2 and source_cards == public_cards
                   and title_integrity and link_integrity) if product else True
    diagnostics = (card_drift_diagnostics(
        source_cards, public_cards, source_identities, public_identities)
        if product else {})
    retrieval = (catalog_retrieval_readiness(raw, page) if product else
                 {"catalog_retrieval_stage": "NOT_APPLICABLE"})
    if product:
        engine = "creatine" if slug == "xfit-os-kreatin-poradce" else "whey"
        metadata = metadata_readiness(
            cta_metadata(raw), cta_metadata(page), engine, len(source_cards))
    else:
        metadata = {"cta_measurement_stage": "NOT_APPLICABLE"}
    status = ("SOURCE_NOT_UPDATED" if not source_has
              else "WP_SOURCE_INCOMPLETE" if product and (
                  len(source_cards) < 2 or
                  retrieval["catalog_retrieval_stage"] in (
                      "SOURCE_DATE_MISSING_OR_INVALID",
                      "SOURCE_DATE_STALE_OR_IN_FUTURE"))
              else "PUBLIC_FRESH" if public_has and cards_match and (
                  not product or retrieval["catalog_retrieval_stage"] ==
                  "PUBLIC_DATE_VERIFIED")
              else "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
    return {"slug": slug, "post_id": post_id, "status": status,
            "wp_source_has_target": source_has, "public_has_target": public_has,
            "wp_product_cards": len(source_cards), "public_product_cards": len(public_cards),
            "product_cards_match": cards_match,
            "public_affiliate_link_integrity": link_integrity,
            "public_product_title_integrity": title_integrity,
            "cache_headers": headers,
            **diagnostics,
            **metadata,
            **retrieval}


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
