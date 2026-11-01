#!/usr/bin/env python3
"""Autonomous, bounded XFIT editorial author->validate->WordPress release.

The model never gets WP credentials. The release job loads only a strict JSON
proposal and a read-only target snapshot from artifacts; code comes from
reviewed main. Existing posts use exact raw-content + GMT preflight and
selective rollback. Never bulk-delete, change titles of legacy posts, make
affiliate offers, publish medical advice or rewrite unapproved URLs.
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from scripts.wp_publish import (
    MARKER, PublishError, normalized_base, publish, validate_document,
    wp_request
)
from scripts.xfit_editorial_gate import check_document

CONFIG = Path("config/xfit-ai-editorial-targets-v1.json")
TARGET = Path("reports/ai-editorial-target.json")
PROPOSAL = Path("reports/ai-editorial-proposal.json")
RECEIPT = Path("reports/ai-editorial-receipt.json")
HOSTS = {"xfit.cz", "www.xfit.cz"}
SENSITIVE = re.compile(
    r"(?i)(diagn[oó]z|vyl[eé][cč]|l[eé][cč]b|t[eě]hoten|"
    r"rakovin|cukrovk|inzul[ií]n|p[rř]edepis|n[eé]moc|"
    r"d[aá]vkov[aá]n[ií] pacient|zran[eě]n|z[aá]zra[cč]n)"
)
ACTIVE = re.compile(r"<\s*/?\s*(?:script|iframe|style|svg|form|input|object|embed|img|video|audio)\b|on[a-z]+\s*=|javascript\s*:", re.I)
SLUG = re.compile(r"(?:xfit-os-)?[a-z0-9]+(?:-[a-z0-9]+)+\Z")
MARKER_RE = re.compile(r"xfit-ai-[a-z0-9-]{9,75}\Z")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
        self.active = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "iframe", "style", "form", "svg", "input", "img", "object", "embed"):
            self.active = True
        for name, value in attrs:
            if name.lower().startswith("on"):
                self.active = True
            if tag == "a" and name == "href":
                self.urls.append(value)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def config_targets():
    obj = json.loads(CONFIG.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or obj.get("schema_version") != 1 or obj.get("site") != "https://xfit.cz":
        raise PublishError("Unknown approved editorial target configuration")
    items = obj.get("targets")
    if not isinstance(items, list) or not 1 <= len(items) <= 16:
        raise PublishError("Invalid editorial target inventory")
    slugs = set()
    for t in items:
        if (not isinstance(t, dict) or t.get("kind") not in ("create", "enhance")
                or not isinstance(t.get("slug"), str)
                or not SLUG.fullmatch(t["slug"])
                or t["slug"] in slugs
                or not isinstance(t.get("marker"), str)
                or not MARKER_RE.fullmatch(t["marker"])
                or not isinstance(t.get("brief"), str)
                or not 60 <= len(t["brief"]) <= 2000
                or not isinstance(t.get("allowed_links"), list)
                or not 2 <= len(t["allowed_links"]) <= 6
                or any(not isinstance(u, str) or not u.startswith("https://") for u in t["allowed_links"])):
            raise PublishError("Invalid editorial target fields")
        if t["kind"] == "create" and (not t["slug"].startswith("xfit-os-") or
                not 500 <= t.get("min_words", 0) <= 850):
            raise PublishError("Unscoped new page")
        if t["kind"] == "enhance" and (type(t.get("post_id")) is not int or
                t["post_id"] <= 0 or not 180 <= t.get("max_add_words", 0) <= 400):
            raise PublishError("Existing page must have one exact allowlisted WordPress ID")
        slugs.add(t["slug"])
    return items


def read_wp_post(post_id):
    base = normalized_base()
    path = ("posts/" + str(post_id) +
            "?context=edit&_fields=id,slug,status,content,link,modified_gmt,title")
    post = wp_request(base, path)
    if not isinstance(post, dict) or post.get("id") != post_id:
        raise PublishError("Pinned WordPress article unavailable")
    return post


def list_by_slug(slug):
    path = "posts?" + urllib.parse.urlencode({
        "slug": slug, "status": "any", "context": "edit", "per_page": 10,
        "_fields": "id,slug,status,content,link"
    })
    found = wp_request(normalized_base(), path)
    if not isinstance(found, list):
        raise PublishError("WordPress list query failed")
    return [p for p in found if p.get("slug") == slug]


def raw_content(post):
    data = post.get("content")
    if not isinstance(data, dict) or not isinstance(data.get("raw"), str):
        raise PublishError("Raw source WordPress content unavailable")
    return data["raw"]


def public_proof(url, marker, *, kind):
    parsed = urllib.parse.urlsplit(url or "")
    if parsed.scheme != "https" or parsed.hostname not in HOSTS:
        raise PublishError("Unexpected public XFIT address")
    field = "data-xfit-ai-edit" if kind == "enhance" else "data-xfit-ai-create"
    signature = field + '="' + marker + '"'
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "XfitAutomatedEditorialPublicProof/1.0",
                "Cache-Control": "no-cache"
            })
            with urllib.request.urlopen(req, timeout=25) as res:
                final = urllib.parse.urlsplit(res.geturl())
                if final.scheme != "https" or final.hostname not in HOSTS or res.status != 200:
                    raise PublishError("Public HTTP origin redirect not approved")
                text = res.read(2000000).decode("utf-8", errors="replace")
            if text.count(signature) == 1:
                return True
        except (OSError, ValueError) as exc:
            if attempt == 2:
                raise PublishError("External public HTTP readback failed: " + type(exc).__name__) from exc
        if attempt < 2:
            time.sleep(3)
    raise PublishError("Exact published marker not visible or duplicated on public website")


def select_target():
    """No publication; read-only WP inventory. Zero model calls when exhausted."""
    for t in config_targets():
        if t["kind"] == "enhance":
            post = read_wp_post(t["post_id"])
            if post.get("slug") != t["slug"] or post.get("status") != "publish":
                raise PublishError("Approved legacy post identity/status changed")
            source = raw_content(post)
            signature = 'data-xfit-ai-edit="' + t["marker"] + '"'
            if signature in source:
                public_proof(post.get("link"), t["marker"], kind="enhance")
                continue
            if len(source.encode()) > 125000 or not 500 <= len(source) <= 125000:
                raise PublishError("Existing post exceeds approved snapshot size")
            modified = post.get("modified_gmt")
            if not isinstance(modified, str) or len(modified) < 15:
                raise PublishError("Missing WordPress source GMT date")
            title = post.get("title", {})
            title = html.unescape(title.get("raw", "") if isinstance(title, dict) else "")
            target = {
                **t, "status": "READY_FOR_RESTRICTED_AI_AUTHOR",
                "source_sha256": digest(source), "source_modified_gmt": modified,
                "source_title": title[:180],
                "source_excerpt": re.sub(r"<[^>]*>", " ", source)[:1300],
            }
        else:
            found = list_by_slug(t["slug"])
            if len(found) > 1:
                raise PublishError("Multiple posts share the future autonomous slug")
            if len(found) == 1:
                post = found[0]
                signature = 'data-xfit-ai-create="' + t["marker"] + '"'
                if post.get("status") == "publish" and signature in raw_content(post):
                    public_proof(post.get("link"), t["marker"], kind="create")
                    continue
                raise PublishError("New-page slug collision or uncertain previous WordPress write")
            target = {**t, "status": "READY_FOR_RESTRICTED_AI_AUTHOR"}
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(json.dumps(target, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"status": "TARGET_SELECTED", "kind":t["kind"], "slug":t["slug"]}
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text('{"status":"NO_APPROVED_TARGET"}\n', encoding="utf-8")
    return {"status": "NO_APPROVED_TARGET"}


def approved_target():
    target = json.loads(TARGET.read_text(encoding="utf-8"))
    if not isinstance(target, dict) or target.get("status") != "READY_FOR_RESTRICTED_AI_AUTHOR":
        raise PublishError("No approved selected target")
    matches = [t for t in config_targets()
               if t["slug"] == target.get("slug") and t["kind"] == target.get("kind")]
    if len(matches) != 1:
        raise PublishError("Target not found in reviewed site policy")
    baseline = matches[0]
    if any(target.get(k) != v for k, v in baseline.items()):
        raise PublishError("Target content altered after selection")
    if target["kind"] == "enhance":
        if (target.get("post_id") != baseline["post_id"]
                or not isinstance(target.get("source_sha256"), str)
                or not re.fullmatch("[a-f0-9]{64}", target["source_sha256"])
                or not isinstance(target.get("source_modified_gmt"), str)):
            raise PublishError("Unauthenticated existing post source hash")
    return target


def validate_proposal(target=None):
    target = target or approved_target()
    raw = PROPOSAL.read_bytes()
    if not 200 <= len(raw) <= 17000:
        raise PublishError("AI proposal outside bounded payload size")
    proposal = json.loads(raw)
    if not isinstance(proposal, dict):
        raise PublishError("AI proposal must be a JSON object")
    kind = target["kind"]
    expected_fields = ({"kind", "slug", "marker", "section_html"} if kind == "enhance"
                       else {"kind", "slug", "marker", "title", "excerpt", "content"})
    if set(proposal) != expected_fields or any(proposal.get(k) != target[k] for k in ("kind", "slug", "marker")):
        raise PublishError("AI proposal identity drift or unexpected fields")
    body = proposal["section_html"] if kind == "enhance" else proposal["content"]
    field = "data-xfit-ai-edit" if kind == "enhance" else "data-xfit-ai-create"
    signature = field + '="' + target["marker"] + '"'
    if (not isinstance(body, str)
            or body.count(signature) != 1
            or not body.startswith('<section ' + signature + '>')
            or not body.rstrip().endswith("</section>")
            or len(body.encode()) > 15000
            or ACTIVE.search(body) or SENSITIVE.search(body)
            or "<!--" in body or "[shortcode" in body):
        raise PublishError("Unsafe or malformed AI generated section")
    parser = Links()
    parser.feed(body)
    if parser.active or not 1 <= len(parser.urls) <= 6:
        raise PublishError("AI section has forbidden HTML or no supporting links")
    allowed = set(target["allowed_links"])
    if any(url not in allowed for url in parser.urls):
        raise PublishError("AI proposed unapproved or affiliate destination")
    visible = re.sub(r"<[^>]*>", " ", body)
    words = len(re.findall(r"\b[\wÀ-ž]+\b", html.unescape(visible)))
    if kind == "enhance":
        if not 130 <= words <= target["max_add_words"]:
            raise PublishError("Existing article change too thin or too large")
        if "section_html" not in proposal or "<h2" not in body or "<li" not in body:
            raise PublishError("Existing article needs usable new section with concrete steps")
    else:
        if not isinstance(proposal["title"], str) or not isinstance(proposal["excerpt"], str):
            raise PublishError("Invalid AI title/excerpt")
        if not target["slug"].startswith("xfit-os-") or words < target["min_words"] or words > 1350:
            raise PublishError("New page outside quality and volume bounds")
        doc = validate_document({
            "slug":target["slug"], "title":proposal["title"],
            "excerpt":proposal["excerpt"], "content":body
        })
        check_document(doc)
        if "<h2" not in body or "<li" not in body:
            raise PublishError("AI article needs structured practical steps")
        if not any(u.startswith("https://food.ec.europa.eu/") or u.startswith("https://ods.od.nih.gov/") for u in parser.urls):
            raise PublishError("No independent trusted source")
    return proposal


def _restore_if_safe(post_id, original, newly_written, source_sha):
    """Rollback only when no other WordPress editor has touched the new body."""
    try:
        current = read_wp_post(post_id)
        if raw_content(current) != newly_written or digest(original) != source_sha:
            return "ROLLBACK_BLOCKED_CONCURRENT_EDIT"
        wp_request(normalized_base(), "posts/" + str(post_id), payload={"content":original})
        verified = read_wp_post(post_id)
        return "ROLLBACK_VERIFIED" if raw_content(verified) == original else "ROLLBACK_UNCONFIRMED"
    except (PublishError, ValueError, OSError):
        return "ROLLBACK_ERROR_MANUAL_REVIEW"


def publish_target():
    target = approved_target()
    proposal = validate_proposal(target)
    kind, slug = target["kind"], target["slug"]
    if kind == "create":
        if list_by_slug(slug):
            raise PublishError("Post appeared after source selection; no duplicate publish")
        doc = validate_document({"slug":slug,"title":proposal["title"],
                                 "excerpt":proposal["excerpt"],"content":proposal["content"]})
        result = publish(doc, live=True)
        if result.get("state") != "live_verified" or result.get("slug") != slug:
            raise PublishError("WordPress did not confirm verified new page")
        public_proof(result["url"], target["marker"], kind=kind)
        return {"status":"PUBLIC_VERIFIED_NEW_AI_ARTICLE","slug":slug,
                "url":result["url"],"post_id":result["post_id"],"writes":1}
    post = read_wp_post(target["post_id"])
    if post.get("slug") != slug or post.get("status") != "publish":
        raise PublishError("Existing article drifted to another slug/status")
    original = raw_content(post)
    sig = 'data-xfit-ai-edit="' + target["marker"] + '"'
    if (digest(original) != target["source_sha256"]
            or post.get("modified_gmt") != target["source_modified_gmt"]
            or sig in original):
        raise PublishError("Exact WordPress source changed since AI review; no overwrite")
    section = proposal["section_html"].strip() + "\n"
    # Preserve all existing text and theme markup byte-for-byte, apart from
    # the newly inserted section. Do not edit the title, slug, tags or meta.
    if original.startswith(MARKER + "\n"):
        updated = MARKER + "\n" + section + original[len(MARKER) + 1:]
    else:
        updated = section + original
    if updated.count(sig) != 1 or len(updated) > len(original) + 17000:
        raise PublishError("Unsafe generated post body")
    wp_request(normalized_base(), "posts/" + str(target["post_id"]), payload={"content":updated})
    try:
        read = read_wp_post(target["post_id"])
        if (read.get("status") != "publish" or raw_content(read) != updated
                or read.get("slug") != slug):
            raise PublishError("WordPress update readback does not match exact source-bound insertion")
        public_proof(read.get("link"), target["marker"], kind=kind)
    except (PublishError, OSError, ValueError) as exc:
        rollback = _restore_if_safe(target["post_id"], original, updated, target["source_sha256"])
        raise PublishError("Readback failure; " + rollback + "; " + str(exc)) from exc
    return {"status":"PUBLIC_VERIFIED_AI_EXISTING_ARTICLE_UPDATE",
            "slug":slug,"url":read.get("link"),"post_id":target["post_id"],
            "original_sha256":target["source_sha256"],"writes":1,
            "rollback":"Original WP revision preserved; exact-source rollback available"}


def write_receipt(receipt):
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["select", "validate", "publish"])
    args = parser.parse_args(argv)
    try:
        result = {
            "select":select_target,
            "validate":lambda: {
                "status":"AI_EDITORIAL_VALIDATED_NO_WRITES",
                "slug":validate_proposal()["slug"],"writes":0},
            "publish":publish_target,
        }[args.mode]()
        code=0
    except (PublishError, ValueError, OSError, json.JSONDecodeError, TypeError) as exc:
        result={"status":"BLOCKED_MANUAL_REVIEW","reason":(type(exc).__name__+": "+str(exc))[:260],
                "writes":"UNKNOWN" if args.mode=="publish" else 0}
        code=2
    write_receipt(result)
    return code


if __name__=="__main__":
    sys.exit(main())
