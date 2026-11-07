"""Compare verified upfront spend vs CZK per 100 g of *powder*.

A deterministic, no-JavaScript decision aid on existing Xfit commercial
pages. Every anchor resolves only to one of the already selected and ranked
WordPress product cards, never to a new merchant or affiliate URL.
"""
import html
from decimal import Decimal

from scripts.wp_publish import PublishError
from scripts.xfit_budget_choices import _price, money


def price_tradeoff(selected, *, product_kind):
    """Render concrete current-price trade-off using only displayed offers."""
    if product_kind not in ("creatine", "whey"):
        raise PublishError("Unknown supplement selection kind")
    if not isinstance(selected, list) or not 2 <= len(selected) <= 12:
        raise PublishError("Price trade-off needs a bounded verified shortlist")
    values = []
    identities = set()
    for n, item in enumerate(selected, start=1):
        if not isinstance(item, dict):
            raise PublishError("Invalid trade-off card")
        ident, name, grams = item.get("id"), item.get("title"), item.get("mass_g")
        if (not isinstance(ident, str) or not ident or ident in identities
                or not isinstance(name, str) or not name.strip()
                or type(grams) is not int or not 50 <= grams <= 10000
                or "tracked_url" not in item and "affiliate_url" not in item):
            raise PublishError("Trade-off cannot resolve a source-bound card")
        identities.add(ident)
        total = _price(item.get("price_czk"))
        unit = _price(item.get("price_per_100g_powder_czk"))
        if total > Decimal("1000000") or unit > Decimal("1000000"):
            raise PublishError("Out-of-range trade-off catalog price")
        values.append((n, item, total, unit))
    # Ties favor the lower alternative price then card order. This exactly
    # matches the two underlying independent selection priorities.
    low_pack = min(values, key=lambda row: (row[2], row[3], row[0]))
    low_unit = min(values, key=lambda row: (row[3], row[2], row[0]))
    p_n, p_item, p_total, p_unit = low_pack
    u_n, u_item, u_total, u_unit = low_unit

    parts = [
        '<h2 id="xfit-price-tradeoff">Dvě cesty k výběru podle ceny</h2>',
        '<p>V šesti zobrazených nabídkách sledujeme dvě odlišné priority: '
        'co nejnižší výdaj dnes a co nejnižší cenu za 100 g prášku. '
        'Nemusí zvítězit stejné balení.</p>',
        '<p data-xfit-tradeoff="upfront"><strong>Nejnižší výdaj při nákupu:</strong> '
        '<a href="#xfit-offer-' + str(p_n) + '">' +
        html.escape(p_item["title"]) + '</a> — ' + money(p_total) +
        ' za celé balení ' + str(p_item["mass_g"]) + ' g; ' +
        money(p_unit) + ' za 100 g prášku.</p>',
    ]
    if p_n == u_n:
        parts.append(
            '<p data-xfit-tradeoff="same"><strong>Nejnižší cena za 100 g prášku:</strong> '
            'stejné balení je v tomto výběru také nejlevnější na 100 g. '
            'Není nutné kupovat dražší balení jen kvůli jednotkové ceně.</p>'
        )
    else:
        upfront_extra = u_total - p_total
        per100_saved = p_unit - u_unit
        if upfront_extra < 0 or per100_saved < 0:
            raise PublishError("Trade-off price ordering is inconsistent")
        parts += [
            '<p data-xfit-tradeoff="unit"><strong>Nejnižší cena za 100 g prášku:</strong> '
            '<a href="#xfit-offer-' + str(u_n) + '">' +
            html.escape(u_item["title"]) + '</a> — ' + money(u_total) +
            ' za celé balení ' + str(u_item["mass_g"]) + ' g; ' +
            money(u_unit) + ' za 100 g prášku.</p>',
            '<p data-xfit-tradeoff="difference"><strong>Co to znamená pro rozpočet?</strong> '
            'Balení s nižší jednotkovou cenou stojí při nákupu o ' +
            money(upfront_extra) + ' více; za každých 100 g baleného prášku '
            'má cenový rozdíl ' + money(per100_saved) +
            ' oproti nejlevnějšímu celému balení. '
            'Jde o srovnání ceny, nikoli o zaručenou úsporu: '
            'záleží na skutečně spotřebovaném množství.</p>',
        ]
    caveat = (
        'Nejde o cenu čistých bílkovin: tu zjistíte až z výživové etikety. '
        if product_kind == "whey" else
        'Nejde o důkaz obsahu či čistoty kreatinu: ty je třeba ověřit na obalu. '
    )
    parts.append(
        '<p><small>Obě možnosti vycházejí pouze z aktuálně vybraných '
        'produktů v tomto přehledu, nikoli z celého trhu. ' +
        caveat +
        'Ceny, složení a dostupnost před nákupem ověřte u prodejce; '
        'pokud doplněk nepotřebujete, nekupujte jej.</small></p>'
    )
    return "\n".join(parts)
