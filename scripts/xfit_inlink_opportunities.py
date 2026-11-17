"""Bounded, read-only editorial queue for underlinked XFIT guide topics.

This is a title-based *review queue*, not evidence that a link should be added.
Editors must inspect the source body and destination before changing WordPress.
"""

from datetime import date, datetime, timedelta, timezone
from html import unescape
import re
from urllib.parse import urlsplit

if __package__:
    from .xfit_internal_inlinks import (
        ALLOWED_HOSTS, BodyAnchors, GUIDE_SLUGS, SLUG, target_from_href,
    )
else:  # Direct CLI execution of xfit_archive_full.py.
    from xfit_internal_inlinks import (
        ALLOWED_HOSTS, BodyAnchors, GUIDE_SLUGS, SLUG, target_from_href,
    )


TARGETS = (
    "xfit-os-kreatin-nebo-protein",
    "xfit-os-cena-proteinu-podle-etikety",
)
MAX_CANDIDATES = 12
COOLDOWN_DAYS = 14
CREATINE = re.compile(r"kreatin|creatin", re.I)
PROTEIN = re.compile(r"protein", re.I)
PRICE_STRONG = re.compile(r"cena|ceny|cenou|cenově|náklad|etiket", re.I)
PRICE_CONTEXT = re.compile(r"srovn|porovn|levn|drah", re.I)
TAGS = re.compile(r"<[^>]*>")


def _modified_date(value):
    """Fail closed when freshness cannot be established from WP metadata."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10]) if len(value) >= 10 else None
    except ValueError:
        return None


def _canonical_source(post):
    slug, raw_url = post.get("slug"), post.get("link")
    if not isinstance(slug, str) or not SLUG.fullmatch(slug):
        return None
    if slug in GUIDE_SLUGS or not isinstance(raw_url, str):
        return None
    try:
        url = urlsplit(raw_url)
        if (url.scheme != "https" or url.hostname not in ALLOWED_HOSTS
                or url.username or url.password or url.port is not None
                or url.path != f"/{slug}/" or url.query or url.fragment):
            return None
    except ValueError:
        return None
    return slug


def _score(slug, title, target):
    # Use public title/slug only: mentioning a keyword somewhere in a long
    # body is not enough to recommend an internal link opportunity.
    text = f"{slug.replace('-', ' ')} {unescape(TAGS.sub(' ', title))}".casefold()
    if target == TARGETS[0]:
        return 3 if CREATINE.search(text) and PROTEIN.search(text) else 0
    if PROTEIN.search(text) and PRICE_STRONG.search(text):
        return 3
    if PROTEIN.search(text) and PRICE_CONTEXT.search(text):
        return 2
    return 0


def build_opportunities(posts, *, as_of=None):
    """Build a deterministic human-review queue from deduplicated WP posts."""
    reference = as_of if as_of is not None else datetime.now(timezone.utc).date()
    if not isinstance(reference, date) or isinstance(reference, datetime):
        raise ValueError("as_of must be a date")
    cutoff = reference - timedelta(days=COOLDOWN_DAYS)
    matches = {target: [] for target in TARGETS}
    examined = 0
    skipped_recent = 0
    for post in posts:
        if not isinstance(post, dict) or type(post.get("id")) is not int or post["id"] <= 0:
            continue
        examined += 1
        slug = _canonical_source(post)
        if slug is None:
            continue
        modified = _modified_date(post.get("modified"))
        if modified is None or modified > cutoff:
            skipped_recent += 1
            continue
        title = (post.get("title") or {}).get("rendered")
        body = (post.get("content") or {}).get("rendered")
        if not isinstance(title, str) or not isinstance(body, str):
            continue
        anchors = BodyAnchors()
        anchors.feed(body)
        already_links = {target_from_href(href, post["link"]) for href in anchors.urls}
        for target in TARGETS:
            if target in already_links:
                continue
            score = _score(slug, title, target)
            if score:
                matches[target].append({
                    "id": post["id"], "slug": slug, "last_modified": modified.isoformat(),
                    "title_relevance_tier": "strong" if score == 3 else "possible",
                    "_score": score,
                })
    groups = []
    for target in TARGETS:
        candidates = sorted(matches[target], key=lambda p: (
            -p["_score"], -date.fromisoformat(p["last_modified"]).toordinal(), p["id"]
        ))
        groups.append({
            "target_slug": target,
            "matching_source_posts": len(candidates),
            "source_candidates": [
                {key: value for key, value in p.items() if key != "_score"}
                for p in candidates[:MAX_CANDIDATES]
            ],
            "sample_truncated": len(candidates) > MAX_CANDIDATES,
        })
    return {
        "status": "HUMAN_REVIEW_ONLY",
        "scope": "older_published_post_titles_without_observed_target_body_anchor",
        "as_of_utc": reference.isoformat(),
        "cooldown_days": COOLDOWN_DAYS,
        "posts_examined": examined,
        "posts_skipped_recent_or_unknown_modified": skipped_recent,
        "targets": groups,
        "not_covered": "body_relevance_editorial_quality_GSC_traffic_page_navigation",
        "no_wordpress_writes": True,
        "editorial_gate": "Read full source and target; only insert a naturally useful contextual link after review.",
    }
