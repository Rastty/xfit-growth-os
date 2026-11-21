#!/usr/bin/env python3
"""Read-only verification that Xfit affiliate CTAs reach the public visitor.

Unlike an authenticated WP REST-only check, this compares product cards AND
first-screen quick-pick CTAs with the same offers in source and public HTML.
No external merchant requests, WP writes, cookies, personal data or events.
Only redacted aggregate counts and enumerated failure reasons are emitted.
"""
from html import unescape
from html.parser import HTMLParser
import json
import os
import re
import sys
import time
from urllib.error import HTTPError, URLError
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
READ_ATTEMPTS = 3
RETRIABLE_HTTP = frozenset((429, 500, 502, 503, 504))


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


def merchant_offer_anchor(card):
    """Single commercial CTA, optionally followed by the exact budget jump.

    Shared by the live parity audit and the untracked merchant probe. No
    second merchant link or arbitrary in-page anchor is silently ignored.
    """
    anchors = card["anchors"]
    if (len(anchors) == 2
            and anchors[1]["href"] == "#xfit-vyber-podle-rozpoctu"
            and not any(anchors[1][field] for field in
                        ("rel", "engine", "partner", "product_id"))):
        anchors = anchors[:1]
    return anchors[0] if len(anchors) == 1 else None


class QuickPicks(HTMLParser):
    """Observe the real hero CTA section, including its visible no-buy path."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.sections = 0
        self.no_buy = 0
        self.no_buy_link = False
        self.in_no_buy = False
        self.links = []
        self.copy = []
        self.copy_before_first_offer = []
        self.first_offer_seen = False
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "section":
            if self.depth:
                self.depth += 1
            elif a.get("id") == "xfit-rychly-vyber":
                self.sections += 1
                self.depth = 1
        if tag in ("script", "style", "noscript", "template"):
            self.suppressed += 1
        if self.depth and tag == "p" and a.get("data-xfit-quick-pick") == "no-buy":
            self.no_buy += 1
            self.in_no_buy = True
        if tag == "a":
            if self.depth and self.in_no_buy and a.get("href") == "#xfit-need":
                self.no_buy_link = True
            if a.get("data-xfit-cta") == "quick-pick":
                self.first_offer_seen = True
                self.links.append({
                    "inside": bool(self.depth),
                    "href": unescape(a.get("href") or ""),
                    "rel": (a.get("rel") or "").lower().split(),
                    "engine": a.get("data-xfit-engine"),
                    "partner": a.get("data-xfit-partner"),
                    "product_id": a.get("data-xfit-product-id"),
                })

    def handle_data(self, data):
        if self.depth and not self.suppressed:
            self.copy.append(data)
            if not self.first_offer_seen:
                self.copy_before_first_offer.append(data)

    def handle_endtag(self, tag):
        if tag == "p":
            self.in_no_buy = False
        if tag == "section" and self.depth:
            self.depth -= 1
        if tag in ("script", "style", "noscript", "template") and self.suppressed:
            self.suppressed -= 1


class VisibleText(HTMLParser):
    """Capture only reader-visible disclosure before the first tracked offer.

    Do not mistake UTM values in href, scripts, hidden blocks, footer copy
    after a commercial CTA, or third-party ad annotations for disclosure.
    When the document markup is malformed, the parser conservatively ignores
    text remaining beneath an unclosed hidden ancestor.
    """
    HIDDEN_TAGS = frozenset(("script", "style", "noscript", "template", "svg"))
    VOID_TAGS = frozenset(("area", "base", "br", "col", "embed", "hr",
                           "img", "input", "link", "meta", "param",
                           "source", "track", "wbr"))

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts = []
        self.first_offer_seen = False

    @staticmethod
    def _hidden(tag, attrs):
        style = (attrs.get("style") or "").lower().replace(" ", "")
        return (tag in VisibleText.HIDDEN_TAGS
                or "hidden" in attrs
                or (attrs.get("aria-hidden") or "").lower() == "true"
                or "display:none" in style or "visibility:hidden" in style)

    @staticmethod
    def _tracked_offer(attrs):
        href = attrs.get("href") or ""
        p = urlsplit(href)
        if p.hostname not in MERCHANTS:
            return False
        q = parse_qs(p.query, keep_blank_values=True)
        return (attrs.get("data-xfit-partner") == "namaximum"
                or attrs.get("data-xfit-cta") == "quick-pick"
                or ("a_aid" in q and "a_bid" in q))

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        parent_hidden = self.stack[-1][1] if self.stack else False
        hidden = parent_hidden or self._hidden(tag, a)
        if tag == "a" and not hidden and self._tracked_offer(a):
            self.first_offer_seen = True
        if tag not in self.VOID_TAGS:
            self.stack.append((tag, hidden))

    def handle_startendtag(self, tag, attrs):
        # XML-like self-closing elements must not leave a hidden ancestor.
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        # Native WordPress text may contain incidental malformed HTML.
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, text):
        if not self.first_offer_seen and not (
                self.stack and self.stack[-1][1]):
            self.parts.append(text)


def has_visible_disclosure(body):
    """True only for a visible fee notice before the first tracked merchant CTA.

    Mere 'affiliate' in an href is NOT a disclosure to the reader.
    """
    parser = VisibleText()
    parser.feed(body)
    text = " ".join(parser.parts).casefold()
    return ("provizi" in text
            and ("affiliate" in text or "partnersk" in text or "xfit" in text))


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


def origin_tag_matches(value, slug):
    """Exact, nonpersonal source tag, never a claim of network credit.

    Creatine is the only approved experiment. The whey control must remain
    untagged; duplicate/partial values are never accepted as valid proof.
    """
    query = parse_qs(urlsplit(value).query, keep_blank_values=True)
    if slug == "xfit-os-kreatin-poradce":
        return (query.get("data1") == ["xfit"]
                and query.get("data2") == ["creatine"])
    return "data1" not in query and "data2" not in query


def comparable_href(value):
    """Ignore only harmless URL encoding/query order, not product/campaign."""
    p = urlsplit(value)
    return (p.scheme, p.hostname, p.path,
            tuple(sorted(parse_qsl(p.query, keep_blank_values=True))))


def variant_identity_status(url, numeric_id):
    """Observe whether a merchant variant parameter binds to the CTA ID.

    The affiliate link is never followed. A missing variant is UNKNOWN, not
    necessarily a broken merchant URL: some canonical routes omit variants.
    """
    if not isinstance(numeric_id, str) or not re.fullmatch(r"[1-9][0-9]{0,9}", numeric_id):
        return "UNVERIFIABLE_CATALOG_ID"
    query = parse_qs(urlsplit(url).query, keep_blank_values=True)
    variants = query.get("variant")
    if variants is None:
        return "NO_VARIANT"
    if (len(variants) != 1
            or not re.fullmatch(r"[1-9][0-9]{0,9}", variants[0])):
        return "AMBIGUOUS_VARIANT"
    return "MATCH" if variants[0] == numeric_id else "MISMATCH"


def card_evidence(body, slug, affiliate_base):
    """Keep sensitive URLs and IDs in memory; expose only safe summary."""
    if not isinstance(body, str) or not 1 <= len(body.encode("utf-8")) <= MAX_PUBLIC_BYTES:
        raise ValueError("invalid_html_body")
    engine = PAGES[slug][1]
    aid, bid = affiliate_signature(affiliate_base)
    parser = Cards()
    parser.feed(body)
    errors = set()
    if not 2 <= len(parser.cards) <= MAX_CARDS:
        errors.add("unexpected_card_count")
    observed_ids = set()
    variant_counts = {
        "MATCH": 0, "MISMATCH": 0,
        "NO_VARIANT": 0, "AMBIGUOUS_VARIANT": 0,
        "UNVERIFIABLE_CATALOG_ID": 0,
    }
    signature = []
    origin_tagged = 0
    for card in parser.cards:
        item = merchant_offer_anchor(card)
        if item is None:
            errors.add("card_needs_exactly_one_link")
            continue
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
        if origin_tag_matches(item["href"], slug):
            origin_tagged += 1
        else:
            errors.add("incorrect_affiliate_origin_tag")
        # A valid campaign link does not prove that the *catalog ID* we would
        # put into GA4 belongs to its actual merchant product variant.
        # Observe the match without blocking a known working merchant link.
        variant_counts[variant_identity_status(item["href"], numeric)] += 1
        signature.append((numeric, item["engine"], item["partner"],
                          comparable_href(item["href"])))
    if not has_visible_disclosure(body):
        errors.add("missing_affiliate_disclosure")
    return {
        "count": len(parser.cards),
        "metadata_count": len(observed_ids),
        "origin_tag_verified_count": origin_tagged,
        "variant_linkage_counts": {
            "matched": variant_counts["MATCH"],
            "mismatched": variant_counts["MISMATCH"],
            "missing_variant": variant_counts["NO_VARIANT"],
            "ambiguous_variant": variant_counts["AMBIGUOUS_VARIANT"],
            "invalid_catalog_id": variant_counts["UNVERIFIABLE_CATALOG_ID"],
        },
        "errors": sorted(errors),
        # Internal only: MUST NOT copy to any printable report.
        "_private_card_signature": signature,
    }


def quick_pick_evidence(body, slug, affiliate_base, card_signature):
    """Hero destinations must be byte-equivalent in meaning to selected cards.

    Never log or return merchant URLs, campaign tokens or catalog IDs.
    The private signature is removed by the caller before printing.
    """
    if not isinstance(body, str) or not 1 <= len(body.encode("utf-8")) <= MAX_PUBLIC_BYTES:
        raise ValueError("invalid_html_body")
    hero = QuickPicks()
    hero.feed(body)
    aid, bid = affiliate_signature(affiliate_base)
    engine = PAGES[slug][1]
    card_by_id = {numeric: (card_engine, partner, href)
                  for numeric, card_engine, partner, href in card_signature}
    errors = set()
    if hero.sections != 1:
        errors.add("missing_or_repeated_quick_pick_section")
    if not 1 <= len(hero.links) <= 2:
        errors.add("unexpected_quick_pick_cta_count")
    if hero.no_buy != 1 or not hero.no_buy_link:
        errors.add("missing_quick_pick_no_buy_path")
    # The notice must precede the first commercial hero CTA, not follow it.
    visible = " ".join(hero.copy_before_first_offer).casefold()
    if "affiliate" not in visible or "provizi" not in visible:
        errors.add("missing_quick_pick_disclosure")
    seen = set()
    signature = []
    origin_tagged = 0
    for link in hero.links:
        numeric = link["product_id"]
        if not link["inside"]:
            errors.add("quick_pick_cta_outside_hero")
        if (link["engine"] != engine or link["partner"] != "namaximum"
                or not isinstance(numeric, str)
                or not re.fullmatch(r"[1-9][0-9]{0,9}", numeric)
                or int(numeric) > 2**31 - 1):
            errors.add("invalid_quick_pick_metadata")
        elif numeric in seen:
            errors.add("duplicate_quick_pick_product")
        else:
            seen.add(numeric)
        if "sponsored" not in link["rel"]:
            errors.add("missing_quick_pick_sponsored_rel")
        if not safe_affiliate_url(link["href"], aid, bid):
            errors.add("invalid_quick_pick_merchant_campaign")
        if origin_tag_matches(link["href"], slug):
            origin_tagged += 1
        else:
            errors.add("incorrect_quick_pick_origin_tag")
        card = card_by_id.get(numeric)
        if (card is None or card != (link["engine"], link["partner"],
                                     comparable_href(link["href"]))):
            errors.add("quick_pick_not_exact_card_offer")
        signature.append((numeric, link["engine"], link["partner"],
                          comparable_href(link["href"])))
    return {"count": len(hero.links), "metadata_count": len(seen),
            "origin_tag_verified_count": origin_tagged,
            "errors": sorted(errors), "_private_quick_signature": signature}


def fetch_bytes_with_retry(request, max_bytes):
    """Retry bounded, side-effect-free reads on transient network errors only.

    Preserve real 403/404 and malformed public responses as hard failures.
    Exception messages may include affiliate data; the CLI only emits types.
    """
    for attempt in range(READ_ATTEMPTS):
        try:
            with urlopen(request, timeout=25) as response:
                return response.status, response.geturl(), response.read(max_bytes + 1)
        except HTTPError as exc:
            if exc.code not in RETRIABLE_HTTP or attempt == READ_ATTEMPTS - 1:
                raise
        except (URLError, TimeoutError, ConnectionResetError):
            if attempt == READ_ATTEMPTS - 1:
                raise
        time.sleep(2**attempt)
    raise ValueError("unexpected_retry_exhaustion")


def read_wp_post(slug):
    url = "https://xfit.cz/wp-json/wp/v2/posts?" + urlencode({
        "slug": slug, "per_page": 2, "_fields": "id,slug,status,link,content",
    })
    req = Request(url, headers={"User-Agent": "XFITPublicAffiliateAudit/1.0"})
    status, _, data = fetch_bytes_with_retry(req, MAX_PUBLIC_BYTES)
    if status != 200:
        raise ValueError("unexpected_wp_response_status")
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
    status, final_url, content = fetch_bytes_with_retry(req, MAX_PUBLIC_BYTES)
    if status != 200 or not canonical_article(final_url, slug):
        raise ValueError("wrong_public_page_or_redirect")
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
    q_source = quick_pick_evidence(source, slug, base, source_sig)
    q_public = quick_pick_evidence(public, slug, base, public_sig)
    source_quick_sig = q_source.pop("_private_quick_signature")
    public_quick_sig = q_public.pop("_private_quick_signature")
    errors = {"wp_" + e for e in a["errors"]}
    errors.update("public_" + e for e in b["errors"])
    errors.update("wp_" + e for e in q_source["errors"])
    errors.update("public_" + e for e in q_public["errors"])
    if source_sig != public_sig:
        errors.add("wp_public_offer_or_tracking_mismatch")
    if source_quick_sig != public_quick_sig:
        errors.add("wp_public_quick_pick_or_tracking_mismatch")
    return {
        "slug": slug, "wp_post_id": expected_id,
        "public_url": "https://xfit.cz/" + slug + "/",
        "source_card_count": a["count"],
        "public_card_count": b["count"],
        "source_cta_metadata_count": a["metadata_count"],
        "public_cta_metadata_count": b["metadata_count"],
        "source_origin_verified_cards": a["origin_tag_verified_count"],
        "public_origin_verified_cards": b["origin_tag_verified_count"],
        "offer_destinations_match": source_sig == public_sig,
        "source_quick_pick_count": q_source["count"],
        "public_quick_pick_count": q_public["count"],
        "source_quick_pick_metadata_count": q_source["metadata_count"],
        "public_quick_pick_metadata_count": q_public["metadata_count"],
        "source_origin_verified_quick_picks": q_source["origin_tag_verified_count"],
        "public_origin_verified_quick_picks": q_public["origin_tag_verified_count"],
        "quick_pick_destinations_match": source_quick_sig == public_quick_sig,
        # This is limited URL-to-catalog identity evidence, NOT proof that
        # Affial/GA4 credited a click or that the product remains in stock.
        "catalog_variant_linkage": (
            "EXACT_VARIANT_IDS_MATCH"
            if (a["variant_linkage_counts"]["matched"] == a["count"]
                and b["variant_linkage_counts"]["matched"] == b["count"]
                and not errors)
            else "MISMATCH_REQUIRES_REVIEW"
            if (a["variant_linkage_counts"]["mismatched"]
                or b["variant_linkage_counts"]["mismatched"])
            else "UNPROVEN_VARIANT_LINKAGE"
        ),
        "source_variant_linkage_counts": a["variant_linkage_counts"],
        "public_variant_linkage_counts": b["variant_linkage_counts"],
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
