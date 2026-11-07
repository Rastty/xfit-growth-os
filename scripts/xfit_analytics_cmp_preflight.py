#!/usr/bin/env python3
"""Read-only XFIT production CMP/analytics integration preflight.

Checks public HTML of two owned pages and, when permitted, names of active
WordPress plugins. Emits a small allowlisted evidence report. No JS execution,
no consent clicks, no WP writes, no raw HTML, links, IDs or secrets in output.
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from scripts.wp_publish import PublishError, normalized_base, wp_request

SLUGS = ("xfit-os-kreatin-poradce", "xfit-os-syrovatkovy-protein-porovnani")
REPORT = Path("reports/xfit-analytics-cmp-preflight.json")

# Detect evidence, NEVER infer effective consent, GTM/GA4 configuration or
# compliant deployment from the mere presence of a third-party script.
CMP_SIGNATURES = {
    "complianz": ("complianz", "cmplz-"),
    "cookieyes": ("cookieyes", "cky-"),
    "cookiebot": ("cookiebot", "cookieconsent.com", "cybotcookiebot"),
    "borlabs": ("borlabs",),
    "real_cookie_banner": ("real-cookie-banner", "real_cookie_banner", "devowl"),
    "webtoffee": ("cookie-law-info", "webtoffee", "cli_cookiebar_settings"),
    "moove": ("moove_gdpr", "gdpr-cookie-compliance"),
    "cookie_notice": ("cookie-notice",),
}

ANALYTICS_SIGNATURES = {
    "gtm": ("googletagmanager.com/gtm.js", "gtm.start"),
    "google_tag": ("googletagmanager.com/gtag/js", "gtag('config'", 'gtag("config"'),
    "google_site_kit": ("google-site-kit", "googlesitekit"),
    "gtm4wp": ("gtm4wp",),
    "monsterinsights": ("monsterinsights",),
    "matomo": ("matomo.js", "piwik.js"),
}

# Plugin inventory may be private. Record only provider fingerprints, not
# plugin slugs, versions, names, users or settings.
PLUGIN_SIGNATURES = {
    **CMP_SIGNATURES,
    **ANALYTICS_SIGNATURES,
    "ga_google_analytics": ("ga-google-analytics",),
    "pixel_your_site": ("pixelyoursite",),
    "xfit_analytics_plugin": ("xfit-analytics/xfit-analytics.php",),
}

SAFE_HOSTS = frozenset(("xfit.cz", "www.xfit.cz"))


def public_url(slug):
    if slug not in SLUGS:
        raise ValueError("Unapproved slug")
    return "https://xfit.cz/" + slug + "/"


class MinimalHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.scripts = []
        self.ctas = 0
        self.marker = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script":
            self.scripts.append(attributes.get("src") or "")
        if tag == "a" and attributes.get("data-xfit-product-id"):
            self.ctas += 1


def scan_public_html(value):
    if not isinstance(value, str) or len(value) > 2500000:
        raise ValueError("Unexpected HTML")
    lowered = value.casefold()
    parser = MinimalHTML()
    parser.feed(value)
    cmp_found = sorted(
        k for k, patterns in CMP_SIGNATURES.items()
        if any(s in lowered for s in patterns)
    )
    analytics_found = sorted(
        k for k, patterns in ANALYTICS_SIGNATURES.items()
        if any(s in lowered for s in patterns)
    )
    scripts = [src.casefold() for src in parser.scripts]
    bridge_indices = [i for i, src in enumerate(scripts)
                      if "xfit-webtoffee-bridge.js" in src]
    outbound_indices = [i for i, src in enumerate(scripts)
                        if "xfit-outbound.js" in src]
    return {
        "cmp_html_fingerprints": cmp_found,
        "analytics_html_fingerprints": analytics_found,
        "first_party_analytics_script_reference": bool(outbound_indices),
        "first_party_consent_bridge_script_reference": bool(bridge_indices),
        "bridge_precedes_outbound_script": bool(
            bridge_indices and outbound_indices and
            bridge_indices[0] < outbound_indices[0]
        ),
        "consent_bridge_symbol_in_html": "xfitgetanalyticsconsent" in lowered,
        "catalog_cta_metadata_count": parser.ctas,
        "analytics_event_observed": False,
        "consent_decision_observed": False,
    }


def get_public_html(url):
    wanted = urllib.parse.urlsplit(url)
    if wanted.scheme != "https" or wanted.hostname not in SAFE_HOSTS:
        raise ValueError("Unexpected host")
    req = urllib.request.Request(url, headers={
        "User-Agent": "XfitAnalyticsReadinessReadOnly/1.0",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=25) as response:
        final = urllib.parse.urlsplit(response.geturl())
        if (response.status != 200 or final.scheme != "https"
                or final.hostname not in SAFE_HOSTS or final.path != wanted.path
                or final.query or final.fragment):
            raise ValueError("Unexpected public redirect")
        return response.read(2500000).decode("utf-8", errors="replace")


def inspect_plugins(*, wp_fetch=wp_request):
    """Best effort; lack of administrator plugins.read permission != no CMP."""
    try:
        response = wp_fetch(
            normalized_base(),
            "plugins?per_page=100&status=active&_fields=plugin,status,version",
        )
        if not isinstance(response, list):
            raise ValueError("Unexpected plugins inventory")
        active = []
        webtoffee_major = None
        for item in response:
            if not isinstance(item, dict):
                continue
            if item.get("status") != "active" or not isinstance(item.get("plugin"), str):
                continue
            slug = item["plugin"].casefold()
            active.append(slug)
            if any(term in slug for term in
                   ("cookie-law-info", "webtoffee", "gdpr-cookie-consent")):
                version = item.get("version")
                if isinstance(version, str):
                    match = re.match(r"^([0-9]{1,2})\.", version)
                    if match:
                        webtoffee_major = int(match.group(1))
        return {
            "inventory_status": "READ_ONLY_VISIBLE",
            "recognized_active_providers": sorted(
                key for key, patterns in PLUGIN_SIGNATURES.items()
                if any(part in name for name in active for part in patterns)
            ),
            "active_plugin_count": len(active),
            "webtoffee_major_version": webtoffee_major,
        }
    except (PublishError, ValueError, OSError):
        return {
            "inventory_status": "UNKNOWN_NO_AUTHORIZED_INVENTORY",
            "recognized_active_providers": [],
            "active_plugin_count": None,
            "webtoffee_major_version": None,
        }


def run(*, public_reader=get_public_html, plugin_reader=inspect_plugins):
    pages = []
    for slug in SLUGS:
        try:
            html = public_reader(public_url(slug))
            pages.append({"page": slug, "read_status": "PUBLIC_HTTP_VERIFIED",
                          **scan_public_html(html)})
        except (OSError, ValueError, PublishError):
            pages.append({"page": slug, "read_status": "PUBLIC_READ_UNAVAILABLE",
                          "catalog_cta_metadata_count": None,
                          "cmp_html_fingerprints": [],
                          "analytics_html_fingerprints": [],
                          "first_party_analytics_script_reference": False,
                          "first_party_consent_bridge_script_reference": False,
                          "bridge_precedes_outbound_script": False,
                          "consent_bridge_symbol_in_html": False,
                          "analytics_event_observed": False,
                          "consent_decision_observed": False})
    plugins = plugin_reader()
    # This script NEVER tests cookies or authenticated GA4. A technical
    # fingerprint cannot establish lawful consent or actual recorded clicks.
    return {
        "site": "https://xfit.cz",
        "mode": "read_only",
        "wordpress_writes": 0,
        "browser_events_sent": 0,
        "pages": pages,
        "wp_plugins": plugins,
        "integration_stage": "PREFLIGHT_ONLY_NO_CONSENT_OR_GA4_PROOF",
        "affiliate_orders": "UNKNOWN",
        "affiliate_commission": "UNKNOWN",
    }


def main():
    report = run()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if all(p["read_status"] == "PUBLIC_HTTP_VERIFIED"
                    for p in report["pages"]) else 2


if __name__ == "__main__":
    sys.exit(main())
