"""Trusted, nonpersonal analytics metadata for validated catalog product cards.

Adding data attributes does NOT record events. The separate browser adapter
must be explicitly installed with a real CMP consent bridge and GA4.
"""
import re

from scripts.wp_publish import PublishError

ENGINES = {"creatine", "whey"}
MAX_CATALOG_ID = 2**31 - 1


def card_click_attributes(product_id, engine):
    """Small, safe attributes for an offer already selected from the feed.

    Never put the URL or affiliate campaign IDs in analytics attributes.
    Invalid IDs block publication rather than inventing an identifier.
    """
    if engine not in ENGINES:
        raise PublishError("Unsupported XFIT measurement engine")
    if isinstance(product_id, bool):
        raise PublishError("Invalid numeric catalog product ID")
    value = str(product_id)
    if not re.fullmatch(r"[1-9][0-9]{0,9}", value):
        raise PublishError("Invalid numeric catalog product ID")
    if int(value) > MAX_CATALOG_ID:
        raise PublishError("Catalog product ID out of bounds")
    return (' data-xfit-engine="' + engine + '"'
            ' data-xfit-partner="namaximum"'
            ' data-xfit-product-id="' + value + '"')
