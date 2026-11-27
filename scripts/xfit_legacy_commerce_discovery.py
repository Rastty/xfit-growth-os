"""Read-only, bounded legacy buyer-intent queue for all live commerce routes.

Reuse existing bounded authenticated title search and canonical identity checks.
Only public post IDs, slugs, titles and safe structural evidence are reported.
Never auto-publish based on a title, inferred traffic, or a keyword in body.
"""
from datetime import datetime, timezone, timedelta
import json
import re
from scripts.xfit_intent_discovery import fetch_topic_posts, verified_post_identity, clean
from scripts.xfit_internal_inlinks import BodyAnchors, target_from_href
from scripts.xfit_select import folded
from scripts.xfit_verified_inlink_release import ALLOWLIST

ROOT = "https://xfit.cz/"
LANES = {
    "creatine": ("kreatin", ("kreatin",), "xfit-os-kreatin-poradce"),
    "whey": ("protein", ("protein",), "xfit-os-syrovatkovy-protein-porovnani"),
    "plant": ("plant", ("rostlinn", "hrachov", "sójov", "rýžov"), "xfit-os-rostlinne-proteiny-porovnani"),
    "mat": ("mat", ("podlož",), "xfit-os-vybaveni-na-domaci-cviceni-nabidky"),
    "band": ("band", ("odporov", "posilovací gum"), "xfit-os-vybaveni-na-domaci-cviceni-nabidky"),
}
BUY = re.compile(r"\b(?:vybrat|vyber\w*|koupit|nakoupit|nakup\w*|nejlevn\w*|"
                 r"nejleps\w*|srovn\w*|porovn\w*|cen\w*|recenz\w*)\b")
MEDICAL = re.compile(r"rizik|bezpecnost|nezadouc|vedlejs|ledvin|jatr|kreatinin|"
                     r"kontraindik|onemocn|poskoz|tehot|krev|diagnost|alerg|"
                     r"lecba|leky|bolest|zranen|rehabilit|nemoc|cukrovk|deti|"
                     r"hubnut|spalovac|testosteron")
PLANT = re.compile(r"rostlinn|vegan|hrachov|sojov|ryzov|konopn")
MILK = re.compile(r"syrovat|whey|wpc|wpi|wph|koncentrat|izolat")
JOINT = re.compile(r"kreatin|creatin")
OLD_IDS = frozenset(cfg.post_id for cfg in ALLOWLIST.values())
MAX_PER_LANE = 5
COOLDOWN_DAYS = 14


def normalized_title(row):
    title = clean((row.get("title") or {}).get("raw"))
    return title, folded(title + " " + str(row.get("slug", "")).replace("-", " "))


def route_for(text, lane):
    if MEDICAL.search(text) or not BUY.search(text):
        return False
    if lane == "creatine":
        return bool(JOINT.search(text)) and "protein" not in text
    if lane == "whey":
        return ("protein" in text and bool(MILK.search(text))
                and not PLANT.search(text) and not JOINT.search(text))
    if lane == "plant":
        return "protein" in text and bool(PLANT.search(text)) and not JOINT.search(text)
    if lane == "mat":
        return "podloz" in text and bool(re.search(r"cvic|jog|fitness|pilates", text))
    return bool(re.search(r"(?:odporov|posilovac)\w* gum", text))


def existing_route(body, source, target):
    parser = BodyAnchors()
    parser.feed(body)
    # Exact same canonical route incl relative links and fragments. The
    # inventory's older guide list omits the two new commerce pages.
    from urllib.parse import urljoin, urlsplit
    for href in parser.urls:
        try:
            u = urlsplit(urljoin(source, href))
            if (u.scheme in {"https", "http"} and u.hostname in {"xfit.cz", "www.xfit.cz"}
                    and not u.username and not u.password and u.port is None
                    and u.path.rstrip("/") == "/" + target):
                return True
        except ValueError:
            continue
    return False


def assess(rows_by_lane, *, today=None):
    today = today or datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=COOLDOWN_DAYS)
    report = {}
    seen_across = set()
    for lane, (_topic, _terms, target) in LANES.items():
        seen, matches = set(), []
        counters = {"rows": 0, "intent_match": 0, "already_linked": 0,
                    "recent_or_unknown_modified": 0, "prior_allowlist": 0}
        for row in rows_by_lane[lane]:
            if not isinstance(row, dict):
                continue
            pid, slug = row.get("id"), row.get("slug")
            if type(pid) is not int or pid <= 0 or pid in seen or not isinstance(slug, str):
                continue
            seen.add(pid)
            counters["rows"] += 1
            if slug.startswith("xfit-os-") or not verified_post_identity(row, slug):
                continue
            title, text = normalized_title(row)
            body = (row.get("content") or {}).get("raw")
            if not isinstance(body, str) or not 1500 <= len(body.encode("utf-8")) <= 400000:
                continue
            if not route_for(text, lane):
                continue
            counters["intent_match"] += 1
            if pid in OLD_IDS:
                counters["prior_allowlist"] += 1
                continue
            if existing_route(body, row["link"], target):
                counters["already_linked"] += 1
                continue
            try:
                modified = datetime.fromisoformat(row["modified"].replace("Z","+00:00")).date()
            except (ValueError, KeyError, TypeError, AttributeError):
                counters["recent_or_unknown_modified"] += 1
                continue
            if modified > cutoff:
                counters["recent_or_unknown_modified"] += 1
                continue
            # Explicit purchase/comparison title beats generic "best".
            score = 2 if re.search(r"koupit|nakoupit|cen\w*|srovn\w*|porovn\w*|vybrat",text) else 1
            matches.append({"id":pid,"slug":slug,"title":title[:160],
                            "target":ROOT+target+"/","last_modified":modified.isoformat(),
                            "explicit_purchase_score":score,
                            "early_h2_observed":bool(re.search(r"<h2(?:\s[^>]*)?>",body[:10000],re.I)),
                            "traffic":"UNKNOWN"})
        matches.sort(key=lambda c:(-c["explicit_purchase_score"],not c["early_h2_observed"],c["id"]))
        fresh = [c for c in matches if c["id"] not in seen_across][:MAX_PER_LANE]
        seen_across.update(c["id"] for c in fresh)
        report[lane] = {**counters,"eligible_review_count":len(matches),"review_candidates":fresh}
    return report


def main():
    rows, coverage = {}, {}
    # Reuse the protein title inventory for both whey and plant to avoid
    # querying generic nutrition content twice. Search new equipment terms.
    scopes = {
        "creatine": ("kreatin", ("kreatin",)),
        "whey": ("protein", ("protein",)),
        "mat": ("mat", ("podlož", "podloz")),
        "band": ("band", ("odporov", "posilovací gum", "posilovaci gum")),
    }
    for lane,(topic,terms) in scopes.items():
        merged = {}
        coverage[lane] = {}
        for term in terms:
            found, status = fetch_topic_posts(topic, search_term=term, max_pages=4)
            coverage[lane][term] = status
            for row in found:
                merged.setdefault(row["id"],row)
        rows[lane] = list(merged.values())
    rows["plant"] = rows["whey"]
    coverage["plant"] = {"same_protein_title_inventory": coverage["whey"]}
    result = {"state":"LEGACY_COMMERCE_REVIEW_QUEUE","coverage":coverage,
              "lanes":assess(rows),"traffic_evidence":"UNKNOWN",
              "review_only":True,"wordpress_writes":0,"merchant_clicks":0}
    print(json.dumps(result,ensure_ascii=False))


if __name__ == "__main__":
    main()
