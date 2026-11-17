"""Bounded, deterministic, read-only legacy content quality review queue.

The ranking is a *heuristic triage*, never an SEO traffic estimate or license
to auto-edit WordPress. Built from the archive scanner's classified rows, so
it adds no extra requests or side effects to the full scan.
"""

from collections import Counter
from datetime import date, datetime, timedelta, timezone
import re


MAX_OUTPUT = 70
PER_TOPIC_LIMIT = 12
COOLDOWN_DAYS = 14
STUDY_HOSTS = frozenset({
    "ods.od.nih.gov", "pubmed.ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov",
    "who.int", "efsa.europa.eu", "acsm.org",
})
MEDICAL = re.compile(r"ledvin|játr|jater|diabet|cukrovk|hormon|těhot|léčb|léčit|bezpečn|rizik|nemoc", re.I)
COMMERCIAL = re.compile(r"protein|kreatin|vitamin|doplň|hubnut|spalovač|gain|výživ|cvičen|trénink", re.I)
BUCKETS = (
    ("kreatin", re.compile(r"kreatin", re.I)),
    ("protein", re.compile(r"protein|bílkovin|syrovátk", re.I)),
    ("hubnutí", re.compile(r"hubnut|spalovač|diet|kalori", re.I)),
    ("trénink", re.compile(r"cvičen|trénink|posilov|fitness|sval", re.I)),
    ("zdraví", MEDICAL),
    ("výživa", re.compile(r"výživ|jídl|recept|strav|vitam", re.I)),
)


def _day(value):
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _topic(text):
    for name, pattern in BUCKETS:
        if pattern.search(text):
            return name
    return "ostatní"


def build_review_queue(rows, *, as_of=None):
    """Prioritize distinct older posts for human source-level investigation."""
    reference = as_of if as_of is not None else datetime.now(timezone.utc).date()
    if not isinstance(reference, date) or isinstance(reference, datetime):
        raise ValueError("as_of must be a date")
    cutoff = reference - timedelta(days=COOLDOWN_DAYS)
    eligible = []
    skipped_fresh = 0
    skipped_unknown = 0
    stats = Counter()
    for row in rows:
        if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] <= 0:
            continue
        modified = _day(row.get("modified"))
        if modified is None or modified > reference:
            skipped_unknown += 1
            continue
        if modified > cutoff:
            skipped_fresh += 1
            continue
        if row.get("suspect_spam") or row.get("suspect_offtopic"):
            # Potential policy/moderation issues need their own review lane.
            continue
        title = row.get("title") or ""
        slug = row.get("slug") or ""
        if not isinstance(title, str) or not isinstance(slug, str) or not slug:
            continue
        url = row.get("url")
        if url != "https://xfit.cz/" + slug + "/":
            # Do not queue a non-canonical or unverified destination.
            continue
        context = (title + " " + slug.replace("-", " ")).casefold()
        reasons = []
        score = 0
        promo = row.get("stale_2022_promo_mentions")
        if type(promo) is int and promo > 0:
            score += 6 + min(3, promo)
            reasons.append("expired_2022_promo_visible_in_archive")
            stats["old_promo"] += 1
        if row.get("suspect_thin"):
            score += 4
            reasons.append("short_reader_text_check_relevance_first")
        if COMMERCIAL.search(context):
            score += 2
            reasons.append("topic_matches_core_fitness_intent")
        if MEDICAL.search(context):
            score += 4
            reasons.append("health_claim_review_required")
            hosts = row.get("external_hosts") or {}
            if isinstance(hosts, dict) and not (set(hosts) & STUDY_HOSTS):
                score += 2
                reasons.append("no_recognized_scientific_host_in_archive_sample")
        if row.get("internal_link_count") == 0:
            score += 2
            reasons.append("no_observed_cross_post_internal_links")
        if (reference - modified).days >= 730:
            score += 1
            reasons.append("not_modified_for_two_years")
        if score < 6:  # Generic age/links alone should not fill the queue.
            continue
        topic = _topic(context)
        eligible.append({
            "id": row["id"], "title": title, "slug": slug,
            "url": url, "last_modified": modified.isoformat(),
            "topic": topic, "priority_score": score, "reasons": reasons,
            "body_chars": row.get("body_chars"),
            "stale_2022_promo_mentions": promo if type(promo) is int else 0,
        })
    eligible.sort(key=lambda p: (-p["priority_score"], p["last_modified"], p["id"]))
    chosen = []
    per_topic = Counter()
    for item in eligible:
        if per_topic[item["topic"]] >= PER_TOPIC_LIMIT:
            continue
        per_topic[item["topic"]] += 1
        chosen.append(item)
        if len(chosen) == MAX_OUTPUT:
            break
    return {
        "status": "HUMAN_REVIEW_ONLY", "source": "full_public_wp_archive_classification",
        "ranking_kind": "deterministic_heuristic_not_measured_traffic_or_revenue",
        "as_of_utc": reference.isoformat(), "cooldown_days": COOLDOWN_DAYS,
        "skipped_recent": skipped_fresh, "skipped_unknown_or_future_date": skipped_unknown,
        "eligible_review_candidates": len(eligible),
        "shown": len(chosen), "topic_cap": PER_TOPIC_LIMIT,
        "topic_distribution": dict(per_topic),
        "expired_promo_eligible": stats["old_promo"],
        "candidates": chosen,
        "not_covered": "GSC_clicks_GA4_landing_sessions_conversions_technical_quality_full_body_medical_review",
        "next_step": "Open live article, verify text and claims, compare to current guide, check GSC/GA4 and write a onepost rollback-safe proposal only if useful.",
        "no_wordpress_writes": True,
    }
