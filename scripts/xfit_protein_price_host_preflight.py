#!/usr/bin/env python3
"""Read-only first-party hosting gate for the XFIT protein calculator.

The operator must separately authorize an asset location and publish the
reviewed files. This gate neither uploads assets nor edits WordPress.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
ASSETS = {
    "calculator.js": ("application/javascript", "text/javascript"),
    "calculator.css": ("text/css",),
}
MAX_BYTES = 200_000
ALLOWED_HOSTS = {"xfit.cz", "www.xfit.cz"}


class HostingGateError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HostingGateError("Asset redirect is not permitted")


def asset_urls(base_url):
    """Accept an exact HTTPS directory on XFIT, without URL ambiguity."""
    if not isinstance(base_url, str) or len(base_url) > 250:
        raise HostingGateError("Invalid first-party asset directory")
    try:
        parts = urlsplit(base_url)
    except ValueError as exc:
        raise HostingGateError("Malformed asset directory") from exc
    if (parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS
            or parts.netloc != parts.hostname or parts.query or parts.fragment
            or not parts.path.startswith("/") or not parts.path.endswith("/")
            or "//" in parts.path or "%" in parts.path
            or any(chunk in (".", "..") for chunk in parts.path.split("/"))):
        raise HostingGateError("Asset directory must be a plain first-party HTTPS path")
    return {name: base_url + name for name in ASSETS}


def fetch_asset(url):
    opener = build_opener(NoRedirect())
    request = Request(url, headers={"User-Agent": "XFIT-Hosting-Preflight/1.0",
                                    "Accept": "text/css, application/javascript"})
    with opener.open(request, timeout=10) as response:
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        return response.read(MAX_BYTES + 1), content_type, response.geturl()


def verify_host(base_url, *, getter=fetch_asset):
    """Compare served bytes against reviewed source; no WP or remote writes."""
    urls = asset_urls(base_url)
    verified = []
    for name, url in urls.items():
        expected = (ROOT / "assets/tools/protein-price" / name).read_bytes()
        if not expected or len(expected) > MAX_BYTES:
            raise HostingGateError("Local reviewed asset exceeds safe size")
        try:
            actual, content_type, final_url = getter(url)
        except (OSError, TimeoutError) as exc:
            raise HostingGateError("First-party asset unavailable") from exc
        if final_url != url:
            raise HostingGateError("Asset redirected from the exact approved URL")
        if content_type not in ASSETS[name]:
            raise HostingGateError("Unexpected asset content type: " + name)
        if actual != expected:
            raise HostingGateError("Live asset differs from reviewed bytes: " + name)
        verified.append({"name": name, "sha256": hashlib.sha256(actual).hexdigest(),
                         "content_type": content_type, "url": url})
    return {"status": "FIRST_PARTY_ASSETS_BYTE_VERIFIED", "assets": verified,
            "wordpress_changed": False, "ready_to_edit_wordpress": False,
            "reason": "Requires separate approved exact-one-post backup/readback and mobile CSP QA"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True,
                        help="Owner-approved exact XFIT asset directory ending with /")
    args = parser.parse_args(argv)
    try:
        result = verify_host(args.base_url)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (HostingGateError, OSError) as exc:
        print(json.dumps({"status": "BLOCKED_NO_WP_WRITE", "error": str(exc),
                          "wordpress_changed": False}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
