#!/usr/bin/env python3
"""One-post read-only rollback snapshot before an adviser refresh.

The public GitHub artifact contains the same editorial HTML and affiliate
URLs already exposed on the public page; it never includes authentication,
feed URLs, private product catalogs or WordPress account data.
"""
import hashlib
import json
import sys
import urllib.parse
from pathlib import Path

from scripts.wp_publish import MARKER, PublishError, normalized_base, wp_request

TARGETS = {
    "creatine": (25455, "xfit-os-kreatin-poradce"),
    "whey": (25456, "xfit-os-syrovatkovy-protein-porovnani"),
}
MAX_BODY_BYTES = 400_000


def snapshot(kind, *, wp_read=wp_request, output=None):
    if kind not in TARGETS:
        raise PublishError("Unsupported adviser backup target")
    post_id, slug = TARGETS[kind]
    base = normalized_base()
    post = wp_read(base, f"posts/{post_id}?context=edit&_fields=id,slug,status,content,link,modified_gmt")
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != post_id or post.get("slug") != slug
            or post.get("status") != "publish"):
        raise PublishError("Adviser source identity or status mismatch")
    url = urllib.parse.urlsplit(post.get("link") or "")
    if (url.scheme != "https" or url.hostname not in ("xfit.cz", "www.xfit.cz")
            or url.path.rstrip("/") != "/" + slug or url.port
            or url.username or url.password or url.query or url.fragment):
        raise PublishError("Unexpected adviser public URL")
    raw = (post.get("content") or {}).get("raw")
    if (not isinstance(raw, str) or MARKER not in raw
            or not 1000 <= len(raw.encode("utf-8")) <= MAX_BODY_BYTES):
        raise PublishError("Missing safe owned WordPress source")
    modified = post.get("modified_gmt")
    if not isinstance(modified, str) or not modified:
        raise PublishError("Missing source modified timestamp")
    artifact = output or Path(f"reports/backups/xfit-{kind}-before-refresh.json")
    if artifact.exists():
        raise PublishError("Existing adviser backup cannot be overwritten")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps({
        "schema": 1, "post_id": post_id, "slug": slug,
        "original_raw": raw, "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "modified_gmt": modified, "remote_writes": 0,
        "purpose": "adviser-refresh",
    }, ensure_ascii=False), encoding="utf-8")
    return {"state": "ADVISER_PREWRITE_BACKUP_READY", "post_id": post_id,
            "kind": kind, "remote_writes": 0}


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise PublishError("Usage: python -m scripts.xfit_adviser_backup creatine|whey")
        print(json.dumps(snapshot(sys.argv[1])))
    except (PublishError, OSError, ValueError, TypeError) as error:
        print("XFIT_ADVISER_BACKUP_ERROR: " + type(error).__name__, file=sys.stderr)
        sys.exit(2)
