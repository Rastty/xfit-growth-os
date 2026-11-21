#!/usr/bin/env python3
"""One-time, GET-only proof of the native GA4 outbound-click measurement path.

We already have native external <a href> merchant links and one Google tag
fingerprint, but that does not prove a GA4 property or collected events.
Check the *actual public static document*, avoiding installation and all
tracking requests. Do not print measurement IDs, affiliate IDs, links, HTML,
visitor attributes or cookies. Missing static evidence means UNKNOWN, not off.
"""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, parse_qs

from scripts.xfit_analytics_cmp_preflight import (
    get_public_html, inspect_plugins, public_url, SLUGS,
)

REPORT = Path("reports/xfit-ga4-native-outbound-readonly.json")
ALLOWED_MERCHANTS = frozenset(("namaximum.cz", "www.namaximum.cz"))
G4_ID = re.compile(r"^G-[A-Z0-9]{5,16}$", re.I)
ADS_ID = re.compile(r"^AW-[0-9]{5,16}$", re.I)
GTM_ID = re.compile(r"^GTM-[A-Z0-9]{4,14}$", re.I)
GTAG_CONFIG = re.compile(
    r"\bgtag\s*\(\s*['\"]config['\"]\s*,\s*['\"](G-[A-Z0-9]{5,16})['\"]",
    re.I,
)
GTAG_ADS_CONFIG = re.compile(
    r"\bgtag\s*\(\s*['\"]config['\"]\s*,\s*['\"](AW-[0-9]{5,16})['\"]",
    re.I,
)
CONSENT_DEFAULT = re.compile(
    r"\bgtag\s*\(\s*['\"]consent['\"]\s*,\s*['\"]default['\"]",
    re.I,
)
MAX_BYTES = 2_500_000


class Signals(HTMLParser):
    """Observe static script references, inline config and actual CTA anchors."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.script_src = []
        self.script_text = []
        self._script_stack = 0
        self.external_merchant_anchors = 0
        self.catalog_identified_external_anchors = 0
        self.verified_rel_external_anchors = 0
        self.external_with_inline_handlers = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script":
            self._script_stack += 1
            src = a.get("src")
            if isinstance(src, str):
                self.script_src.append(src)
        if tag == "a":
            href = a.get("href") or ""
            try:
                p = urlsplit(href)
            except ValueError:
                return
            if (p.scheme != "https" or p.hostname not in ALLOWED_MERCHANTS
                    or p.username or p.password or p.port is not None):
                return
            self.external_merchant_anchors += 1
            identified = (
                a.get("data-xfit-partner") == "namaximum"
                and a.get("data-xfit-engine") in ("creatine", "whey")
                and isinstance(a.get("data-xfit-product-id"), str)
                and re.fullmatch(r"[1-9][0-9]{0,9}",
                                 a.get("data-xfit-product-id"))
            )
            if identified:
                self.catalog_identified_external_anchors += 1
            rel = (a.get("rel") or "").lower().split()
            if "sponsored" in rel:
                self.verified_rel_external_anchors += 1
            if any(key.startswith("on") for key in a):
                self.external_with_inline_handlers += 1

    def handle_endtag(self, tag):
        if tag == "script" and self._script_stack:
            self._script_stack -= 1

    def handle_data(self, data):
        if self._script_stack and data:
            self.script_text.append(data)


def classify(html, slug):
    if slug not in SLUGS or not isinstance(html, str) or not 500 <= len(html) <= MAX_BYTES:
        raise ValueError("Unexpected public advisor document")
    p = Signals()
    p.feed(html)
    ga4_loader = False
    ads_loader = False
    gtm_loader = False
    for src in p.script_src:
        try:
            parts = urlsplit(src)
        except ValueError:
            continue
        if (parts.scheme != "https" or
                parts.hostname not in ("www.googletagmanager.com", "googletagmanager.com")
                or parts.username or parts.password or parts.port is not None):
            continue
        tag_id = parse_qs(parts.query).get("id") or []
        if len(tag_id) != 1:
            continue
        ga4_loader |= (parts.path == "/gtag/js" and bool(G4_ID.fullmatch(tag_id[0])))
        ads_loader |= (parts.path == "/gtag/js" and bool(ADS_ID.fullmatch(tag_id[0])))
        gtm_loader |= (parts.path == "/gtm.js" and bool(GTM_ID.fullmatch(tag_id[0])))
    inline = "\n".join(p.script_text)
    ga4_config_inline = bool(GTAG_CONFIG.search(inline))
    google_ads_config_inline = bool(GTAG_ADS_CONFIG.search(inline))
    consent_default_present = bool(CONSENT_DEFAULT.search(inline))
    native_ready = ga4_loader and ga4_config_inline
    if native_ready:
        state = "STATIC_GA4_LOAD_AND_CONFIG_FOUND_EVENTS_UNPROVEN"
    elif ga4_loader:
        state = "GA4_LOADER_PRESENT_CONFIG_UNPROVEN"
    elif ga4_config_inline:
        state = "GA4_CONFIG_INLINE_LOADER_UNPROVEN"
    elif gtm_loader:
        state = "GTM_PRESENT_GA4_RUNTIME_UNKNOWN"
    elif ads_loader or google_ads_config_inline:
        state = "GOOGLE_ADS_TAG_ONLY_GA4_UNKNOWN"
    else:
        state = "NO_STATIC_GA4_EVIDENCE_RUNTIME_UNKNOWN"
    return {
        "page": slug, "ga4_loader_static": ga4_loader,
        "ga4_config_inline_static": ga4_config_inline,
        "google_ads_loader_static": ads_loader,
        "google_ads_config_inline_static": google_ads_config_inline,
        "gtm_loader_static": gtm_loader,
        "consent_default_call_static": consent_default_present,
        "existing_tag_readiness": state,
        "merchant_external_anchor_count": p.external_merchant_anchors,
        "catalog_identified_external_anchor_count":
            p.catalog_identified_external_anchors,
        "external_sponsored_rel_count": p.verified_rel_external_anchors,
        "external_anchors_with_inline_handlers": p.external_with_inline_handlers,
        "events_observed": False,
        "enhanced_measurement_enabled_proven": False,
        "cmp_consent_effectively_enforced_proven": False,
    }


def run(*, public_reader=get_public_html, plugins_reader=inspect_plugins):
    pages = []
    for slug in SLUGS:
        try:
            doc = public_reader(public_url(slug))
            pages.append({"read_status": "PUBLIC_HTML_OK", **classify(doc, slug)})
        except (ValueError, OSError, TypeError):
            pages.append({"page": slug, "read_status": "PUBLIC_HTML_UNKNOWN",
                          "existing_tag_readiness": "UNKNOWN",
                          "events_observed": False})
    plugins = plugins_reader()
    state = plugins.get("xfit_analytics_plugin_state", "UNKNOWN")
    # Fail closed; a plugin present in WP is NOT proof it is enqueued, nor
    # proof a real event reached GA4.
    return {
        "mode": "public_and_wp_get_only",
        "wordpress_writes": 0, "affiliate_clicks_sent": 0,
        "browser_analytics_events_sent": 0,
        "pages": pages,
        "xfit_plugin_inventory_state": state,
        "wp_plugin_inventory_status": plugins.get("inventory_status", "UNKNOWN"),
        "known_active_cmp_provider_count":
            len([x for x in plugins.get("recognized_active_providers", [])
                 if x == "webtoffee"]),
        "ga4_actual_clicks": "UNKNOWN",
        "ga4_enhanced_outbound_setting": "NOT_READABLE_FROM_PUBLIC_HTML",
        "commission_approved_or_paid": "UNKNOWN",
        "limitations": [
            "Inline static gtag config and loader references are not live GA4 event evidence.",
            "Runtime GTM, dynamic tag loading, actual consent and GA4 settings are not evaluated.",
            "An ordinary external anchor is only eligible for native click tracking when GA4 enhanced measurement and compliant consent are configured.",
            "No merchant URL is fetched and no synthetic conversion is counted.",
        ],
    }


def main():
    result = run()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if all(p["read_status"] == "PUBLIC_HTML_OK"
                    for p in result["pages"]) else 2


if __name__ == "__main__":
    sys.exit(main())
