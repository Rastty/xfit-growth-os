#!/usr/bin/env python3
"""XFIT: publish one reviewed, pinned, noncommercial education article per run.

The queue lives in the *protected main branch*. This runner cannot generate or
approve content, and the AI coding agents cannot edit the queue or ready files.
Each entry pins an exact Git blob SHA, owns only a new xfit-os-* WordPress post,
and is idempotent. No older WP article is overwritten; no affiliate links.
"""
import argparse
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from scripts.wp_publish import (
    MARKER, PublishError, existing_content, normalized_base, publish,
    validate_document, wp_request
)
from scripts.xfit_editorial_gate import check_document

SITE = "https://xfit.cz"
MANIFEST = "content/auto-ready/queue-v1.json"
REPORT = Path("reports/auto-editorial-release-receipt.json")
PATH_RE = re.compile(r"content/auto-ready/(xfit-os-[a-z0-9-]+)\.json\Z")
ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{9,79}\Z")
TRUSTED_HOSTS = {
    "xfit.cz", "www.xfit.cz", "ods.od.nih.gov",
    "food.ec.europa.eu", "www.efsa.europa.eu",
    "efsa.europa.eu", "pmc.ncbi.nlm.nih.gov",
}
# The autonomous queue intentionally excludes sensitive fitness/clinical advice;
# those subjects go through the regular source-bound editorial review.
MEDICAL_TOPICS = re.compile(
    r"(diagn[oó]z|vyl[eé][cč]|l[eé][cč]b|t[eě]hoten|"
    r"hormon[aá]ln|cukrovk|inzul[ií]n|zran[eě]n|"
    r"d[aá]vkov[aá]n[ií]|p[rř]ed[eé]pis|ledvinov|jatern[ií] onemocn)",
    re.I
)


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.unsafe = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "iframe", "form", "object", "embed", "img", "svg", "input"):
            self.unsafe.append(tag)
        if any(name.lower().startswith("on") for name, _ in attrs):
            self.unsafe.append("inline_event")
        if tag == "a":
            self.links.append(a.get("href", ""))


def blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def prepare_queue(manifest_path=MANIFEST, root=Path(".")):
    path = root / manifest_path
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != 1
            or manifest.get("site") != SITE
            or manifest.get("policy") != "one_pinned_educational_post_per_run"):
        raise PublishError("Unsupported autonomous queue contract")
    entries = manifest.get("articles")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 12:
        raise PublishError("Queue must contain 1 to 12 pinned articles")
    seen = set()
    prepared = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"slug", "path", "git_blob_sha", "marker"}:
            raise PublishError("Queue entry fields are incomplete or unexpected")
        slug, rel, expected, marker = (entry[k] for k in ("slug", "path", "git_blob_sha", "marker"))
        if (not isinstance(rel, str) or not PATH_RE.fullmatch(rel)
                or not isinstance(slug, str) or PATH_RE.fullmatch(rel).group(1) != slug
                or slug in seen or not isinstance(expected, str)
                or not re.fullmatch("[a-f0-9]{40}", expected)
                or not isinstance(marker, str) or not ID_RE.fullmatch(marker)):
            raise PublishError("Unsafe or duplicate pinned queue identity")
        seen.add(slug)
        file_path = root / rel
        if file_path.is_symlink():
            raise PublishError("Symlinked queue file is not allowed")
        raw = file_path.read_bytes()
        if len(raw) > 40000 or blob_sha(raw) != expected:
            raise PublishError("Pinned article Git blob SHA mismatch")
        source = json.loads(raw)
        if not isinstance(source, dict):
            raise PublishError("Pinned article must be an object")
        if set(source) - {"slug", "title", "excerpt", "content"}:
            raise PublishError("Autonomous release cannot use pinned legacy WP IDs or extra fields")
        doc = validate_document(source)
        if doc["slug"] != slug:
            raise PublishError("Queue and document slug mismatch")
        if doc["content"].count('data-xfit-auto-release="' + marker + '"') != 1:
            raise PublishError("Exact public release marker is missing or duplicated")
        if MEDICAL_TOPICS.search(doc["content"]):
            raise PublishError("Sensitive medical topics require human-reviewed release path")
        parser = Anchors()
        parser.feed(doc["content"])
        if parser.unsafe:
            raise PublishError("Active HTML/media not allowed in autonomous educational release")
        if len(parser.links) < 2 or len(parser.links) > 16:
            raise PublishError("Unbounded or missing educational links")
        for url in parser.links:
            parsed = urllib.parse.urlsplit(url)
            if (parsed.scheme != "https" or parsed.hostname not in TRUSTED_HOSTS
                    or parsed.username or parsed.password or parsed.port or parsed.query
                    or parsed.fragment and parsed.hostname not in ("xfit.cz", "www.xfit.cz")):
                raise PublishError("Non-approved external link in autonomous queue")
        editorial = check_document(doc)
        if editorial["commerce"] or editorial["word_count"] < 450:
            raise PublishError("Autonomous release requires substantive noncommercial education")
        prepared.append({"slug": slug, "marker": marker,
                         "doc": doc, "word_count": editorial["word_count"],
                         "git_blob_sha": expected})
    return prepared


def existing_owned_post(slug):
    base = normalized_base()
    params = urllib.parse.urlencode({
        "slug": slug, "status": "any", "context": "edit",
        "per_page": 10, "_fields": "id,slug,status,content,link,title"
    })
    posts = wp_request(base, "posts?" + params)
    if not isinstance(posts, list):
        raise PublishError("WordPress post lookup did not return a list")
    matched = [p for p in posts if p.get("slug") == slug]
    if len(matched) > 1:
        raise PublishError("Duplicate owned slug in WordPress")
    return matched[0] if matched else None


def check_public_marker(url, marker):
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or u.hostname not in ("xfit.cz", "www.xfit.cz"):
        raise PublishError("Public URL outside XFIT domain")
    req = urllib.request.Request(url, headers={
        "User-Agent": "XfitAutonomousEditorialReadback/1.0",
        "Cache-Control": "no-cache"
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            redirect = urllib.parse.urlsplit(res.geturl())
            if (redirect.scheme != "https"
                    or redirect.hostname not in ("xfit.cz", "www.xfit.cz")
                    or res.status != 200):
                raise PublishError("Public origin redirect or HTTP status is unexpected")
            html = res.read(2000000).decode("utf-8", errors="replace")
    except (OSError, ValueError) as exc:
        raise PublishError("Public marker readback failed: " + type(exc).__name__) from exc
    signature = 'data-xfit-auto-release="' + marker + '"'
    if html.count(signature) != 1:
        raise PublishError("Public marker missing or duplicated; cache may be stale")
    return True


def publish_one(prepared, *, lookup=existing_owned_post,
                writer=publish, public_check=check_public_marker):
    """Returns one sanitized receipt. No article updates, only new posts."""
    for entry in prepared:
        doc, slug = entry["doc"], entry["slug"]
        found = lookup(slug)
        desired = doc["content"].strip()
        if found is not None:
            content = (found.get("content") or {}).get("raw", "")
            if (found.get("status") == "publish" and isinstance(content, str)
                    and MARKER in content and content.strip() == desired):
                # A previously published article still requires public proof.
                public_check(found.get("link", ""), entry["marker"])
                continue
            # A previous WP POST may have succeeded but readback failed.
            # Fail closed instead of rewriting or creating a duplicate.
            raise PublishError("Existing WordPress post differs from pinned queue; manual review required: " + slug)
        result = writer(doc, live=True)
        if result.get("state") != "live_verified" or result.get("slug") != slug:
            raise PublishError("WordPress write not independently verified")
        public_check(result.get("url", ""), entry["marker"])
        return {"status": "PUBLIC_VERIFIED_NEW_POST", "slug": slug,
                "post_id": result.get("post_id"), "url": result.get("url"),
                "marker": entry["marker"], "new_posts": 1}
    return {"status": "ALL_PINNED_ARTICLES_PUBLIC_VERIFIED", "new_posts": 0,
            "verified_articles": len(prepared)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--preview", action="store_true")
    options.add_argument("--publish-one", action="store_true")
    args = parser.parse_args(argv)
    try:
        prepared = prepare_queue()
        if args.preview:
            receipt = {"status": "PREVIEW_PASSED_NO_WORDPRESS_WRITES", "new_posts": 0,
                       "eligible_count": len(prepared),
                       "slugs": [a["slug"] for a in prepared]}
        else:
            receipt = publish_one(prepared)
        exit_code = 0
    except (PublishError, ValueError, OSError, json.JSONDecodeError) as exc:
        receipt = {"status": "BLOCKED_MANUAL_REVIEW", "new_posts": None,
                   "reason": (type(exc).__name__ + ": " + str(exc))[:220]}
        exit_code = 2
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
