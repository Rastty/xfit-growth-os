"""Offline, fail-closed event boundary; does not send or store analytics."""

PAGES = {
    "xfit-os-kreatin-poradce": "creatine",
    "xfit-os-syrovatkovy-protein-porovnani": "whey",
}
EVENTS = {"advisor_start", "advisor_complete", "affiliate_outbound_click"}
PARTNERS = {"namaximum"}



def _snapshot_catalogs(catalogs):
    """Validate and freeze caller-owned catalog data before reading events."""
    if (type(catalogs) is not dict
            or any(type(key) is not str or key not in PAGES for key in catalogs)):
        raise ValueError("verified catalogs must be keyed by advisor page")
    snapshot = {}
    for page, catalog in catalogs.items():
        if (type(catalog) not in (set, frozenset)
                or any(type(item) is not int or not 1 <= item <= 2**31 - 1
                       for item in catalog)):
            raise ValueError("verified catalog IDs must be an integer set")
        snapshot[page] = frozenset(catalog)
    return snapshot

def build_event(event_name, fields, *, analytics_consent=False,
                verified_product_ids_by_page=None):
    """Return minimal validated parameters, or None without explicit consent.

    Callers must supply actual observed actions, never synthetic conversions.
    Consent must come from the site's consent manager, not a default opt-in.
    Unknown keys fail closed: never forward quiz answers, URLs or user IDs.
    Clicks require IDs from the separately validated catalog for that advisor.
    """
    if type(analytics_consent) is not bool:
        raise ValueError("consent must be boolean")
    if not analytics_consent:
        return None
    if not isinstance(event_name, str) or event_name not in EVENTS:
        raise ValueError("unsupported event")
    if not isinstance(fields, dict):
        raise ValueError("fields must be a dictionary")
    expected = {"page", "selection_engine"}
    if event_name == "affiliate_outbound_click":
        expected |= {"partner", "product_id"}
    if set(fields) != expected:
        raise ValueError("unsupported or missing fields")
    page = fields["page"]
    if not isinstance(page, str) or page not in PAGES:
        raise ValueError("unsupported page")
    if fields["selection_engine"] != PAGES[page]:
        raise ValueError("page and engine do not match")
    params = {"page": page, "selection_engine": PAGES[page]}
    if event_name == "affiliate_outbound_click":
        partner = fields["partner"]
        product_id = fields["product_id"]
        if not isinstance(partner, str) or partner not in PARTNERS:
            raise ValueError("unsupported partner")
        # Only catalog item numbers, never free text or tracking URLs.
        if type(product_id) is not int or not 1 <= product_id <= 2**31 - 1:
            raise ValueError("product_id must be a positive catalog integer")
        verified_product_ids_by_page = _snapshot_catalogs(
            verified_product_ids_by_page)
        if product_id not in verified_product_ids_by_page.get(page, set()):
            raise ValueError("product is not in the verified advisor catalog")
        params.update(partner=partner, product_id=product_id)
    return {"name": event_name, "params": params}


def summarize_funnel(events, *, analytics_consent=False,
                     verified_product_ids_by_page=None):
    """Count observed actions per advisor, never infer people or earnings.

    Revalidate every record instead of trusting a previously built payload.
    Denied consent must not consume the input (which may be a lazy iterator).
    """
    if type(analytics_consent) is not bool:
        raise ValueError("consent must be boolean")
    if not analytics_consent:
        return None
    # A lazy event source may refresh or mutate caller-owned catalogs. All
    # clicks in one report must use the same independently supplied allowlist.
    if verified_product_ids_by_page is not None:
        verified_product_ids_by_page = _snapshot_catalogs(
            verified_product_ids_by_page)
    counts = {page: {name: 0 for name in sorted(EVENTS)} for page in PAGES}
    product_clicks = {page: {} for page in PAGES}
    for event in events:
        if not isinstance(event, dict) or set(event) != {"name", "params"}:
            raise ValueError("unsupported event record")
        validated = build_event(
            event["name"], event["params"], analytics_consent=True,
            verified_product_ids_by_page=verified_product_ids_by_page,
        )
        page = validated["params"]["page"]
        counts[page][validated["name"]] += 1
        if validated["name"] == "affiliate_outbound_click":
            product_id = validated["params"]["product_id"]
            product_clicks[page][product_id] = (
                product_clicks[page].get(product_id, 0) + 1
            )
    return {
        "action_counts": counts,
        # Only observed, revalidated catalog IDs; absent products are unknown,
        # not zero-interest offers. Repeated clicks remain separate actions.
        "product_click_counts": {
            page: dict(sorted(clicks.items()))
            for page, clicks in product_clicks.items()
        },
        # No records for an advisor do not establish working instrumentation
        # or zero reader interest. Observed actions do not prove completeness.
        "action_data_status": {
            page: "OBSERVED_ACTIONS" if any(actions.values()) else "UNKNOWN"
            for page, actions in counts.items()
        },
        # A click alone proves nothing about start/completion instrumentation.
        # Keep missing evidence explicit at each step before comparing advisors.
        "action_observation_status": {
            page: {
                name: "OBSERVED_ACTIONS" if count else "UNKNOWN"
                for name, count in actions.items()
            }
            for page, actions in counts.items()
        },
        "unique_visitors": "UNKNOWN",
        "orders": "UNKNOWN",
        "commission": "UNKNOWN",
    }
