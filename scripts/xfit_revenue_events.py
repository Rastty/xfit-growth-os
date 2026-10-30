"""Offline, fail-closed event boundary; does not send or store analytics."""

PAGES = {
    "xfit-os-kreatin-poradce": "creatine",
    "xfit-os-syrovatkovy-protein-porovnani": "whey",
}
EVENTS = {"advisor_start", "advisor_complete", "affiliate_outbound_click"}
PARTNERS = {"namaximum"}


def build_event(event_name, fields, *, analytics_consent=False):
    """Return minimal validated parameters, or None without explicit consent.

    Callers must supply actual observed actions, never synthetic conversions.
    Consent must come from the site's consent manager, not a default opt-in.
    Unknown keys fail closed: never forward quiz answers, URLs or user IDs.
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
        params.update(partner=partner, product_id=product_id)
    return {"name": event_name, "params": params}
