"""One GET-only WordPress REST menu capability and identity diagnosis.

Explains the previous primary-menu preflight failure without relaxing a guard,
changing any menu or displaying private menu URLs, credentials or article text.
"""
import json
import re

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts.xfit_primary_decision_menu_onepost import (
    KNOWN_HEADER, normalized_title, menu_projection,
)

def safe_failure(error):
    if not isinstance(error, PublishError):
        return "UNAVAILABLE"
    match = re.fullmatch(r"WordPress REST API returned HTTP ([1-5][0-9]{2})", str(error))
    if match:
        return "HTTP_" + match.group(1)
    if str(error).startswith("WordPress REST request failed"):
        return "TRANSPORT_UNAVAILABLE"
    return "MISSING_AUTH_OR_BASE_OR_UNKNOWN"


def probe(*, fetch=wp_request, base_reader=normalized_base):
    report = {
        "state": "GET_ONLY_MENU_PREFLIGHT",
        "wordpress_writes": 0,
        "menu_items_created": 0,
        "menu_items_updated": 0,
    }
    try:
        base = base_reader()
        menus = fetch(base, "menus?context=edit&per_page=100&_fields=id,slug,name,locations")
    except (PublishError, OSError, ValueError) as exc:
        return {**report, "state": "MENU_COLLECTION_NOT_READABLE",
                "menu_collection_failure": safe_failure(exc)}
    if not isinstance(menus, list):
        return {**report, "state": "UNEXPECTED_MENU_COLLECTION"}
    report["total_menu_count"] = len(menus)
    report["menu_collection_paginated_possible"] = len(menus) >= 100
    candidates = 0
    best_labels = 0
    location_matches = 0
    item_statuses = []
    for menu in menus[:99]:
        locs = menu.get("locations") if isinstance(menu, dict) else None
        header = isinstance(locs, list) and any(
            isinstance(loc, str) and any(
                key in loc.casefold() for key in ("header", "primary", "main"))
            for loc in locs)
        if not header or type(menu.get("id")) is not int:
            continue
        location_matches += 1
        try:
            rows = fetch(base, "menu-items?context=edit&menus=" +
                         str(menu["id"]) + "&per_page=100&_fields=id,menus,parent,menu_order,title,url,status")
            items = menu_projection(rows)
            heads = {row["title"] for row in items if row["parent"] == 0}
            found = len(KNOWN_HEADER.intersection(heads))
            best_labels = max(best_labels, found)
            if found == len(KNOWN_HEADER):
                candidates += 1
            item_statuses.append("READABLE")
        except (PublishError, OSError, ValueError, TypeError) as exc:
            item_statuses.append(safe_failure(exc))
    report.update({
        "header_or_primary_menu_locations": location_matches,
        "header_menu_item_read_states": item_statuses,
        "best_public_label_match_count": best_labels,
        "required_public_label_count": len(KNOWN_HEADER),
        "exact_header_menu_candidates": candidates,
        "state": ("EXACT_ONE_HEADER_MENU_FOUND" if candidates == 1 and len(menus) < 100
                  else "NO_SAFE_UNIQUE_HEADER_MENU"),
    })
    return report


def main():
    print(json.dumps(probe(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
