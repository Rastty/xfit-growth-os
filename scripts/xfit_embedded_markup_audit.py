#!/usr/bin/env python3
"""Read-only archive detector for full HTML documents embedded inside WP posts.

These corrupt canonicals/HTML and confuse independent public-identity proof.
This tool creates only a triage report, never a deletion or WordPress write list.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

from scripts.xfit_archive_full import MAX_PAGE, MAX_SIZE, fetch

DOCTYPE = re.compile(r"<!\s*doctype\s+html\b", re.I)
DOC_TAGS = re.compile(r"<\s*(?:/?\s*(?:html|head|body)|meta\s|title\s*>)", re.I)
CANONICAL = re.compile(r"<\s*link\b(?=[^>]*\brel\s*=\s*['\"]?canonical\b)[^>]*>", re.I)
BOGUS_CANONICAL = re.compile(r"(?:www\.)?example\.com/", re.I)
LOCAL_ASSET = re.compile(r"<\s*(?:script|link)\b[^>]*(?:src|href)\s*=\s*['\"](?:script\.js|styles\.css)['\"]", re.I)


def examine(post):
    if not isinstance(post, dict) or type(post.get("id")) is not int or post["id"] <= 0:
        raise ValueError("Post ID missing or invalid")
    body = (post.get("content") or {}).get("rendered")
    if not isinstance(body, str):
        raise ValueError("Post rendered content missing")
    slug, url = post.get("slug"), post.get("link")
    if not isinstance(slug, str) or not slug or not isinstance(url, str) or not url:
        raise ValueError("Post permalink evidence missing")
    doctype = len(DOCTYPE.findall(body))
    doc_tags = len(DOC_TAGS.findall(body))
    body_canonical = CANONICAL.findall(body)
    bogus = sum(bool(BOGUS_CANONICAL.search(tag)) for tag in body_canonical)
    assets = len(LOCAL_ASSET.findall(body))
    if not any((doctype, doc_tags, body_canonical, assets)):
        return None
    # A technology tutorial may quote one HTML tag in content. Keep low-confidence
    # snippets separate; never treat them as an automatic rewrite allowlist.
    high_confidence = bool(body_canonical) or (doctype >= 1 and doc_tags >= 2)
    score = 100*bogus + 65*len(body_canonical) + 30*doctype + 5*doc_tags + 10*assets
    return {"id": post["id"], "slug": slug, "url": url,
            "modified": post.get("modified"), "rendered_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "body_canonical_count": len(body_canonical), "bogus_canonical_count": bogus,
            "doctype_count": doctype, "document_tag_count": doc_tags,
            "relative_asset_count": assets, "review_score": score,
            "confidence": "HIGH" if high_confidence else "LOW_SNIPPET_POSSIBLE"}


def audit(*, pages, size, reader=fetch):
    if not (1 <= pages <= MAX_PAGE and 1 <= size <= MAX_SIZE):
        raise ValueError("Invalid page/size")
    seen = {}
    repeated = 0
    declared = None
    fetched = 0
    interruption = None
    for page in range(1, pages + 1):
        try:
            batch, total = reader(page, size)
            if (not isinstance(batch, list) or not isinstance(total, int) or total < 1
                    or len(batch) > size or any(not isinstance(post, dict) for post in batch)):
                raise ValueError("Invalid public archive page")
            if declared is not None and total != declared:
                raise ValueError("Total pages drifted during non-atomic pagination")
            declared = total
            for post in batch:
                candidate = examine(post)
                fingerprint = (post["id"], post.get("slug"), post.get("link"),
                               post.get("modified"),
                               hashlib.sha256(post["content"]["rendered"].encode()).hexdigest())
                if post["id"] in seen:
                    if seen[post["id"]][0] != fingerprint:
                        raise ValueError("Conflicting repeated post across pages")
                    repeated += 1
                else:
                    seen[post["id"]] = (fingerprint, candidate)
            fetched += 1
            if page >= total or len(batch) < size:
                if page < total:
                    raise ValueError("Short page before declared end of archive")
                break
        except (OSError, ValueError, TypeError, KeyError) as exc:
            interruption = {"page": page, "reason": type(exc).__name__, "details": str(exc)[:100]}
            break
    found = [value[1] for value in seen.values() if value[1] is not None]
    found.sort(key=lambda item: (-item["review_score"], item["id"]))
    high = [item for item in found if item["confidence"] == "HIGH"]
    # A top-N severity queue can hide rare, directly actionable canonical
    # conflicts when thousands of articles contain many embedded documents.
    # Preserve EVERY canonical case independently of the top-100 cutoff.
    canonical_cases = [item for item in found if item["body_canonical_count"] > 0]
    canonical_cases.sort(key=lambda item: (-item["bogus_canonical_count"],
                                               -item["body_canonical_count"],
                                               -item["review_score"], item["id"]))
    complete = interruption is None and fetched == declared
    return {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "complete": complete, "declared_total_pages": declared,
            "pages_fetched": fetched, "scanned_posts": len(seen),
            "repeated_same_record_count": repeated, "interruption": interruption,
            "high_confidence_posts": len(high), "low_confidence_snippets": len(found) - len(high),
            "affected_body_canonicals": sum(x["body_canonical_count"] for x in high),
            "bogus_example_canonicals": sum(x["bogus_canonical_count"] for x in high),
            "all_body_canonical_candidates": canonical_cases,
            "doctype_article_count": sum(x["doctype_count"] > 0 for x in found),
            "top_review_candidates": found[:100],
            "warning": "READ_ONLY_TRIAGE. Counts are not SEO impact, ranking or rewrite approvals. Inspect exact post and current source before any onepost action.",
            "wordpress_writes": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=MAX_PAGE)
    parser.add_argument("--size", type=int, default=MAX_SIZE)
    parser.add_argument("--output", default="reports/xfit-embedded-markup-audit.json")
    args = parser.parse_args()
    result = audit(pages=args.pages, size=args.size)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in (
        "top_review_candidates", "all_body_canonical_candidates", "warning")},
                     ensure_ascii=False))
    return 0 if result["complete"] else 2


if __name__ == "__main__":
    sys.exit(main())
