"""Conservative Heureka DELIVERY_DATE interpretation for buyer-facing offers.

Heureka's basic XML field describes days until dispatch, not live inventory.
It is less authoritative than a separate high-frequency availability feed or
the seller's checkout. Never turn a missing/invalid field into 'in stock'.
"""

import re


EXPLICITLY_UNAVAILABLE = frozenset((
    "vyprodano", "vyprodáno", "není skladem", "neni skladem",
    "nedostupné", "nedostupne", "nedostupný", "nedostupny",
    "out of stock", "unavailable", "not available",
))


def delivery_state(item):
    """Return availability from the source without guessing today's stock.

    'up_to_week' is an XML dispatch estimate (NOT proof of stock or delivery).
    Unknown is acceptable only with a prominent per-card warning; explicitly
    unavailable, delayed >7 days and preorders are ineligible for shortlists.
    """
    if not isinstance(item, dict):
        return "unknown"
    availability = item.get("availability_raw") or ""
    if isinstance(availability, str) and any(
            word in availability.strip().casefold() for word in EXPLICITLY_UNAVAILABLE):
        return "unavailable"
    # Old catalog snapshots (and older test fixtures) lack a dedicated key.
    raw = item.get("delivery_date", item.get("stock_indicator", ""))
    if not isinstance(raw, str) or not raw.strip():
        return "unknown"
    value = raw.strip()
    if re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", value):
        # Heureka uses a date for preorder/launch, not stocked goods.
        return "preorder"
    if not re.fullmatch(r"0|[1-9][0-9]{0,2}", value):
        return "unknown"
    days = int(value)
    if days == 0:
        return "feed_stocked"
    if days <= 7:
        return "up_to_week"
    return "slow_dispatch"


def delivery_note(item):
    """Copy is about the catalog at retrieval, never a stock guarantee."""
    state = item.get("availability_state", "unknown")
    if state == "feed_stocked":
        return "Dostupnost: v XML označeno jako skladem při načtení; ověřte v obchodě."
    if state == "up_to_week":
        return "Dostupnost: XML uvádí expedici do 7 dnů; ověřte v obchodě."
    return "Dostupnost: v XML nepotvrzena; před nákupem ověřte v obchodě."
