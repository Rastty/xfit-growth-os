"""Offline, fail-closed event boundary; does not send or store analytics."""

PAGES = {
    "xfit-os-kreatin-poradce": "creatine",
    "xfit-os-syrovatkovy-protein-porovnani": "whey",
}
EVENTS = {"advisor_start", "advisor_complete", "affiliate_outbound_click"}
PARTNERS = {"namaximum"}


def build_event(event_name, fields, *, analytics_consent=False,
                verified_product_ids=None):
    """Return minimal validated parameters, or None without explicit consent.

    Callers must supply actual observed actions, never synthetic conversions.
    Consent must come from the site's consent manager, not a default opt-in.
    Unknown keys fail closed: never forward quiz answers, URLs or user IDs.
    Clicks require catalog IDs from a separately validated merchant feed.
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
        if (type(verified_product_ids) not in (set, frozenset)
                or any(type(item) is not int or not 1 <= item <= 2**31 - 1
                       for item in verified_product_ids)):
            raise ValueError("verified catalog IDs must be an integer set")
        if product_id not in verified_product_ids:
            raise ValueError("product is not in the verified catalog")
        params.update(partner=partner, product_id=product_id)
    return {"name": event_name, "params": params}


def summarize_funnel(events, *, analytics_consent=False,
                     verified_product_ids=None):
    """Count observed actions per advisor, never infer people or earnings.

    Revalidate every record instead of trusting a previously built payload.
    Denied consent must not consume the input (which may be a lazy iterator).
    """
    if type(analytics_consent) is not bool:
        raise ValueError("consent must be boolean")
    if not analytics_consent:
        return None
    counts = {page: {name: 0 for name in sorted(EVENTS)} for page in PAGES}
    for event in events:
        if not isinstance(event, dict) or set(event) != {"name", "params"}:
            raise ValueError("unsupported event record")
        validated = build_event(
            event["name"], event["params"], analytics_consent=True,
            verified_product_ids=verified_product_ids,
        )
        counts[validated["params"]["page"]][validated["name"]] += 1
    return {
        "action_counts": counts,
        "unique_visitors": "UNKNOWN",
        "orders": "UNKNOWN",
        "commission": "UNKNOWN",
    }
