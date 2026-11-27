#!/usr/bin/env python3
"""Source-backed read-only comparison of XFIT public offer cards and CURRENT XML.

The existing audits already prove WP-vs-public affiliate CTA integrity and
provider-feed hygiene independently. This bridge compares exact displayed
catalog IDs and numeric CZK labels to a fresh, secret-backed XML fetch.

No merchant requests, tracked affiliate clicks, checkout claims, WordPress
writes, public product IDs, prices, raw page bodies or private feed URLs.
A feed absence/difference is a review signal, NEVER proof of unavailable stock.
"""
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import sys

from scripts.xfit_affiliate_public_audit import (
    PAGES, Cards, card_evidence, canonical_article, merchant_offer_anchor,
    read_public_page, read_wp_post, safe_affiliate_url, comparable_href,
    has_visible_disclosure, origin_tag_matches,
)
from scripts.xfit_feed_ingest import fetch_feed, parse_feed, catalog_identity_matches_url
from scripts.xfit_public_freshness import commercial_facts, product_card_texts, product_card_identities, typography_key
from scripts.xfit_creatine_guide import build_tracked_url, validate_example
from scripts.xfit_affil_deeplink import affiliate_signature
from scripts.xfit_select import plant_powder, mass_grams
from scripts.xfit_equipment_comparison import equipment_kind
from scripts.xfit_availability import delivery_state
from scripts.wp_publish import PublishError

REPORT = Path("reports/xfit-feed-public-offer-parity.json")
MAX_CARDS_PER_PAGE = 6
PRICE = re.compile(r"(?:0|[1-9][0-9]{0,7})(?:[,.][0-9]{1,2})?\Z")


class ParityError(ValueError):
    """Safe constant errors without private product values."""


def _cents(value):
    """Strictly parse one displayed/normalized price; no locale guesses."""
    if type(value) not in (int, float, str):
        return None
    text = str(value).strip().replace(" ", "").replace("\u00a0", "")
    if not PRICE.fullmatch(text):
        return None
    try:
        number = Decimal(text.replace(",", "."))
        amount = number.quantize(Decimal("0.01"))
        if not amount.is_finite() or amount <= 0 or amount != number:
            return None
        return int(amount * 100)
    except (InvalidOperation, ValueError, OverflowError):
        return None


def _cards(html, slug, base):
    """Keep catalog IDs and hrefs strictly in memory, never in reports."""
    evidence = card_evidence(html, slug, base)
    if evidence["errors"]:
        raise ParityError("INVALID_AFFILIATE_CARD_CONTEXT")
    parser = Cards()
    parser.feed(html)
    if len(parser.cards) != MAX_CARDS_PER_PAGE:
        raise ParityError("UNEXPECTED_PUBLIC_OFFER_COUNT")
    visible_cards = product_card_texts(html)
    if len(visible_cards) != len(parser.cards):
        raise ParityError("VISIBLE_CARD_COUNT_MISMATCH")
    result = []
    for card, visible in zip(parser.cards, visible_cards):
        anchor = merchant_offer_anchor(card)
        if not anchor:
            raise ParityError("UNEXPECTED_PRODUCT_ANCHOR")
        ident = anchor["product_id"]
        if not isinstance(ident, str) or not re.fullmatch(r"[1-9][0-9]{0,9}", ident):
            raise ParityError("INVALID_PUBLIC_CATALOG_ID")
        # Exact affiliate campaign and variant are checked by card_evidence,
        # already used above. Never copy campaign or merchant URLs into output.
        result.append((ident, _cents(commercial_facts(visible)["price_czk"])))
    if len(set(ident for ident, _ in result)) != len(result):
        raise ParityError("DUPLICATE_PUBLIC_PRODUCT")
    return result


def inspect(offers, pages, affiliate_base):
    """Pure, source-only reconciliation with per-adviser redacted counts.

    pages maps each exact approved slug to (WP REST rendered, public HTML).
    May only be called after a successfully parsed fresh feed and authentic
    source/public page reads. Reconcile prices numerically, never claim that
    the merchant checkout displays the same price.
    """
    if type(offers) is not list or not offers:
        raise ParityError("LATEST_FEED_INCOMPLETE")
    if type(pages) is not dict or set(pages) != set(PAGES):
        raise ParityError("SOURCE_OR_PUBLIC_PAGE_MISSING")
    feed = defaultdict(list)
    for offer in offers:
        if type(offer) is not dict:
            raise ParityError("INVALID_LATEST_FEED_OFFER")
        ident = offer.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"[1-9][0-9]{0,9}", ident):
            raise ParityError("INVALID_FEED_CATALOG_ID")
        feed[ident].append(offer)

    rows = []
    for slug in PAGES:
        pair = pages[slug]
        if type(pair) not in (tuple, list) or len(pair) != 2:
            raise ParityError("SOURCE_OR_PUBLIC_PAGE_MISSING")
        source, public = pair
        a = _cards(source, slug, affiliate_base)
        b = _cards(public, slug, affiliate_base)
        # Source/public must match on catalog identity and the same displayed
        # numeric price. The existing full public audit independently verifies
        # canonical merchant hrefs and all tracked campaign parameters.
        if a != b:
            raise ParityError("WP_PUBLIC_OFFER_ID_OR_PRICE_DRIFT")
        statuses = Counter()
        availability_seen = 0
        for ident, shown_price in a:
            matches = feed.get(ident, [])
            if not matches:
                statuses["feed_item_not_observed"] += 1
            elif len(matches) != 1:
                statuses["ambiguous_feed_id"] += 1
            else:
                offer = matches[0]
                if offer.get("delivery_date") or offer.get("availability_raw"):
                    availability_seen += 1
                feed_price = _cents(offer.get("price_czk"))
                if shown_price is None:
                    statuses["displayed_price_not_parseable"] += 1
                elif feed_price is None:
                    statuses["feed_price_not_parseable"] += 1
                elif shown_price == feed_price:
                    statuses["numeric_price_matches_feed"] += 1
                else:
                    statuses["numeric_price_differs_from_feed"] += 1
        rows.append({
            "page": slug,
            "wordpress_post_id": PAGES[slug][0],
            "public_cards": len(b),
            "wp_source_public_ids_and_prices_match": True,
            "feed_ids_observed": len(a) - statuses["feed_item_not_observed"],
            "numeric_price_matches_feed": statuses["numeric_price_matches_feed"],
            "numeric_price_differs_from_feed": statuses["numeric_price_differs_from_feed"],
            "feed_item_not_observed": statuses["feed_item_not_observed"],
            "ambiguous_feed_id": statuses["ambiguous_feed_id"],
            "displayed_price_not_parseable": statuses["displayed_price_not_parseable"],
            "feed_price_not_parseable": statuses["feed_price_not_parseable"],
            "feed_availability_field_present": availability_seen,
        })

    fully_matching = all(
        row["numeric_price_matches_feed"] == row["public_cards"]
        for row in rows
    )
    return {
        "state": ("SOURCE_FEED_NUMERIC_PARITY_OBSERVED"
                  if fully_matching else "REVIEW_CURRENT_FEED_VS_PUBLIC_OFFERS"),
        "source": "FRESH_PRIVATE_NAMAXIMUM_XML_PLUS_LIVE_XFIT_WP_AND_PUBLIC_HTML",
        "feed_offers_accepted": len(offers),
        "pages": rows,
        "currency_note": "SOURCE_CZK_IS_EXISTING_FEED_ASSUMPTION_NOT_INDEPENDENTLY_VERIFIED",
        "merchant_checkout_stock_verified": False,
        "merchant_checkout_price_verified": False,
        "network_commission_attribution": "UNKNOWN",
        "approved_or_paid_commissions": "UNKNOWN",
        "manual_review_required": not fully_matching,
        "affiliate_click_requests": 0,
        "wordpress_writes": 0,
        "public_product_ids_or_prices_logged": 0,
    }



# The new lanes intentionally have no legacy GA4 data attributes or hero CTAs.
# Never infer measurement coverage from a valid tracked product URL.
EXPANDED_PAGES = {
    "xfit-os-rostlinne-proteiny-porovnani": (26152, "plant"),
    "xfit-os-vybaveni-na-domaci-cviceni-nabidky": (26154, "equipment"),
}
PLANT_PRICE = re.compile(r"\b([0-9][0-9 ,.]*?)\s*kč\s+za balení\s+(\d+)\s*g\b")
PLANT_UNIT = re.compile(r"\b([0-9][0-9 ,.]*?)\s*kč\s+za 100 g prášku\b")
EQUIPMENT_PRICE = re.compile(r"\bcena nabídky:\s*([0-9][0-9 ,.]*?)\s*kč\b")


def expanded_cards(body, slug, base):
    """Parse only actual commercial cards; reject unsafe/missing CTA disclosure.

    Track product identity using the complete affiliate destination, not a
    guessed ID from a title. Each card must have one CTA. No raw fields leave
    this helper's in-memory caller.
    """
    if not isinstance(body, str) or not 1 <= len(body.encode("utf-8")) <= 2_000_000:
        raise ParityError("EXPANDED_INVALID_BODY")
    kind = EXPANDED_PAGES[slug][1]
    aid, bid = affiliate_signature(base)
    parser = Cards()
    parser.feed(body)
    visible = product_card_texts(body)
    titles = product_card_identities(body)
    if (parser.depth or not 2 <= len(parser.cards) <= MAX_CARDS_PER_PAGE
            or len(visible) != len(parser.cards) or len(titles) != len(parser.cards)
            or not has_visible_disclosure(body)):
        raise ParityError("EXPANDED_INVALID_CARD_OR_DISCLOSURE")
    result = []
    for card, text, identity in zip(parser.cards, visible, titles):
        if len(card["anchors"]) != 1 or not identity[0]:
            raise ParityError("EXPANDED_UNEXPECTED_CARD_STRUCTURE")
        anchor = card["anchors"][0]
        href = anchor["href"]
        if ("sponsored" not in anchor["rel"]
                or not safe_affiliate_url(href, aid, bid)
                or not origin_tag_matches(href, slug)):
            raise ParityError("EXPANDED_INVALID_AFFILIATE_DESTINATION")
        # Require the disclosure on each card before its exact CTA copy.
        cta = "ověřit cenu a etiketu" if kind == "plant" else "ověřit variantu a cenu"
        if ("partnerský odkaz" not in text or "provizi" not in text
                or cta not in text or text.index("partnerský odkaz") > text.index(cta)
                or text.index("provizi") > text.index(cta)):
            raise ParityError("EXPANDED_CARD_DISCLOSURE_NOT_BEFORE_CTA")
        if kind == "plant":
            prices, units = PLANT_PRICE.findall(text), PLANT_UNIT.findall(text)
            if len(prices) != 1 or len(units) != 1:
                raise ParityError("EXPANDED_PRICE_OR_MASS_AMBIGUOUS")
            price, mass = _cents(prices[0][0]), int(prices[0][1])
            unit = _cents(units[0])
            if not 100 <= mass <= 10000 or unit is None:
                raise ParityError("EXPANDED_PRICE_OR_MASS_AMBIGUOUS")
        else:
            prices = EQUIPMENT_PRICE.findall(text)
            if len(prices) != 1:
                raise ParityError("EXPANDED_PRICE_OR_MASS_AMBIGUOUS")
            price, mass, unit = _cents(prices[0]), None, None
        if price is None:
            raise ParityError("EXPANDED_PRICE_OR_MASS_AMBIGUOUS")
        result.append((comparable_href(href), typography_key(identity[0]), price, mass, unit, text))
    if len({row[0] for row in result}) != len(result):
        raise ParityError("EXPANDED_DUPLICATE_PUBLIC_DESTINATION")
    return result


def inspect_expanded(offers, pages, base, sample):
    """Read-only exact destination + title + price/quantity + eligibility join.

    No fuzzy name matching, no cross-merchant SKU equality, no assumption
    that a feed miss is out of stock. Source/public drift fails; current feed
    drift is a review signal only. Never return product-level data.
    """
    if not isinstance(offers, list) or not 1 <= len(offers) <= 10000:
        raise ParityError("LATEST_FEED_INCOMPLETE")
    if set(pages) != set(EXPANDED_PAGES):
        raise ParityError("EXPANDED_PAGE_SCOPE_INCOMPLETE")
    validate_example(base, sample)
    ids = Counter()
    by_link = defaultdict(list)
    for row in offers:
        if not isinstance(row, dict):
            raise ParityError("INVALID_LATEST_FEED_OFFER")
        pid = row.get("id")
        if not isinstance(pid, str) or not re.fullmatch(r"[1-9][0-9]{0,9}", pid):
            raise ParityError("INVALID_FEED_CATALOG_ID")
        ids[pid] += 1
        try:
            if row.get("merchant") != "NaMaximum.cz" or not catalog_identity_matches_url(pid, row.get("source_url")):
                continue
            url = build_tracked_url(row["source_url"], base, sample)
            by_link[comparable_href(url)].append(row)
        except (ValueError, PublishError, KeyError, TypeError, AttributeError):
            continue
    results = []
    for slug, (pid, kind) in EXPANDED_PAGES.items():
        source, public = pages[slug]
        a = expanded_cards(source, slug, base)
        b = expanded_cards(public, slug, base)
        if a != b:
            raise ParityError("EXPANDED_WP_PUBLIC_OFFER_DRIFT")
        counts = Counter()
        for href, title, price, mass, unit, _text in b:
            matches = by_link[href]
            if not matches:
                counts["feed_destination_not_observed"] += 1
                continue
            if len(matches) != 1 or ids[matches[0]["id"]] != 1:
                counts["ambiguous_feed_identity"] += 1
                continue
            row = matches[0]
            category = plant_powder(row) if kind == "plant" else equipment_kind(row) is not None
            if not category or typography_key(" ".join(row["title"].casefold().split())) != title:
                counts["feed_title_or_category_differs"] += 1
                continue
            feed_price = _cents(row.get("price_czk"))
            if feed_price is None or feed_price != price:
                counts["feed_price_differs_or_invalid"] += 1
                continue
            if kind == "plant":
                if mass_grams(row["title"]) != mass or _cents(round(float(row["price_czk"]) / mass * 100, 2)) != unit:
                    counts["feed_mass_or_unit_price_differs"] += 1
                    continue
            if delivery_state(row) not in {"feed_stocked", "up_to_week", "unknown"}:
                counts["feed_dispatch_no_longer_eligible"] += 1
                continue
            counts["exact_current_feed_match"] += 1
        # Always include zero-valued status buckets, so absence isn't unknown.
        results.append({
            "page": slug, "wordpress_post_id": pid, "public_cards": len(b),
            "wp_source_public_cards_match": True,
            **{key: counts[key] for key in (
                "exact_current_feed_match", "feed_destination_not_observed",
                "ambiguous_feed_identity", "feed_title_or_category_differs",
                "feed_price_differs_or_invalid", "feed_mass_or_unit_price_differs",
                "feed_dispatch_no_longer_eligible")},
        })
    review = any(r["exact_current_feed_match"] != r["public_cards"] for r in results)
    return {
        "state": "REVIEW_EXPANDED_OFFERS" if review else "EXPANDED_SOURCE_FEED_PARITY_OBSERVED",
        "pages": results, "manual_review_required": review,
        "merchant_checkout_price_verified": False, "merchant_checkout_stock_verified": False,
        "network_commission_attribution": "UNKNOWN", "affiliate_click_requests": 0,
        "wordpress_writes": 0, "public_product_ids_or_prices_logged": 0,
    }


def main():
    affiliate_base = os.getenv("XFIT_AFFIL_DEFAULT_LINK", "").strip()
    if not affiliate_base:
        raise ParityError("AFFIL_CONFIGURATION_UNAVAILABLE")
    # Fetch just once, at the same provider and Secret already used by
    # XFIT Affiliate Feed Validation. Never print the secret in error text.
    offers, _skipped = parse_feed(fetch_feed())
    pages = {}
    for slug, (expected_id, _engine) in PAGES.items():
        post = read_wp_post(slug)
        if (type(post) is not dict or post.get("id") != expected_id
                or post.get("slug") != slug or post.get("status") != "publish"
                or not canonical_article(post.get("link"), slug)):
            raise ParityError("PINNED_WORDPRESS_POST_IDENTITY_DRIFT")
        body = (post.get("content") or {}).get("rendered")
        public = read_public_page(slug)
        if not isinstance(body, str) or not isinstance(public, str):
            raise ParityError("SOURCE_OR_PUBLIC_BODY_INCOMPLETE")
        pages[slug] = (body, public)
    result = inspect(offers, pages, affiliate_base)
    # Fetch the two additional pinned pages, using the SAME fresh XML.
    # No extra merchant/feed request or WordPress write.
    expanded_pages = {}
    for slug, (expected_id, _kind) in EXPANDED_PAGES.items():
        post = read_wp_post(slug)
        if (type(post) is not dict or type(post.get("id")) is not int
                or post["id"] != expected_id or post.get("slug") != slug
                or post.get("status") != "publish"
                or not canonical_article(post.get("link"), slug)):
            raise ParityError("EXPANDED_PINNED_POST_IDENTITY_DRIFT")
        expanded_pages[slug] = ((post.get("content") or {}).get("rendered"), read_public_page(slug))
    expanded = inspect_expanded(offers, expanded_pages, affiliate_base,
                                os.environ.get("XFIT_AFFIL_SAMPLE_PRODUCT_LINK", ""))
    result["expanded"] = expanded
    result["total_public_cards_observed"] = sum(row["public_cards"] for row in
                                               result["pages"] + expanded["pages"])
    if expanded["manual_review_required"]:
        result["manual_review_required"] = True
        result["state"] = "REVIEW_CURRENT_FEED_VS_PUBLIC_OFFERS"
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    # Diagnostic mismatches are not proof of a broken checkout or a reason
    # to auto-delete/swap offers. Return zero with explicit REVIEW flag;
    # hard-fail only on invalid identity/unsafe or inconsistent observations.
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ParityError, PublishError, ValueError, OSError, TypeError, KeyError) as exc:
        # Never emit exception text, because it can contain source feed URL,
        # WP content or campaign tokens. Safe type and constant only.
        code = exc.args[0] if type(exc) is ParityError else type(exc).__name__
        print("XFIT_CURRENT_FEED_PARITY_ERROR: " + code, file=sys.stderr)
        sys.exit(2)
