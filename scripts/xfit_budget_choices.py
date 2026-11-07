"""Source-bound budget decisions for already verified XFIT product cards.

This produces only HTML anchors to offers in the same approved selection.
It never opens merchant URLs, sends analytics, guesses stock or ranks on
commission. All prices are the feed's verified retail CZK price (not protein
mass, discounts or availability).
"""
import html
from decimal import Decimal, InvalidOperation

from scripts.wp_publish import PublishError


def money(value):
    """Czech CZK formatting without rounding away relevant cents."""
    parsed = _price(value)
    return f"{parsed:,.2f}".replace(",", "\u00a0").replace(".", ",") + " Kč"


def _price(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise PublishError("Non-numeric catalog price")
    try:
        price = Decimal(str(value))
    except InvalidOperation as exc:
        raise PublishError("Invalid catalog price") from exc
    if not price.is_finite() or price <= 0:
        raise PublishError("Invalid catalog price")
    return price


def budget_choices(selected, limits, *, product_kind):
    """Return two distinct buyer goals inside accessible native budget controls.

    Within each spend limit: show the cheapest whole pack and the lowest
    price per 100 g of POWDER. Both resolve only to existing verified
    xfit-offer-N cards; no new merchant links, cookies, JS or tracking.
    When one card wins both criteria, avoid two redundant links.
    """
    if product_kind not in ("creatine", "whey"):
        raise PublishError("Unsupported product decision type")
    if not isinstance(selected, list) or len(selected) < 2:
        raise PublishError("Need multiple verified offers for budget chooser")
    if (not isinstance(limits, tuple) or not limits or
            any(type(limit) is not int or limit < 1 for limit in limits) or
            tuple(sorted(set(limits))) != limits):
        raise PublishError("Budget levels must be increasing CZK integers")
    if not all(isinstance(item, dict) and
               isinstance(item.get("title"), str) and item["title"].strip()
               for item in selected):
        raise PublishError("Invalid product identity")

    offers = []
    for position, item in enumerate(selected, start=1):
        total = _price(item.get("price_czk"))
        per100 = _price(item.get("price_per_100g_powder_czk"))
        grams = item.get("mass_g")
        if (type(grams) is not int or grams < 1 or
                "tracked_url" not in item and "affiliate_url" not in item):
            raise PublishError("Incomplete verified product card")
        offers.append((position, item, total, per100))
    if len({item[1]["id"] for item in offers}) != len(offers):
        raise PublishError("Duplicate offer IDs in budget chooser")

    result = [
        '<h2 id="xfit-vyber-podle-rozpoctu">Kolik chcete maximálně utratit?</h2>',
        '<p>Vyberte cenový limit a porovnejte dvě různé priority: '
        '<strong>co nejméně zaplatit nyní</strong> za celé balení, nebo '
        '<strong>co nejméně zaplatit za 100 g prášku</strong>. '
        'Někdy vyhraje stejný produkt. Počítáme pouze nabídky již '
        'zobrazené níže, nikoli celý trh. Ceny se mohou změnit.</p>',
    ]

    for limit in limits:
        possible = [offer for offer in offers if offer[2] <= Decimal(limit)]
        result.append(
            '<details><summary><strong>Do ' + str(limit) + ' Kč — ' +
            str(len(possible)) +
            (' nabídka' if len(possible) == 1 else
             ' nabídky' if 2 <= len(possible) <= 4 else ' nabídek') +
            ' v tomto přehledu</strong></summary>'
        )
        if not possible:
            result.append(
                '<p>V tomto omezeném výběru žádná nabídka do ' + str(limit) +
                ' Kč není. To neznamená, že na trhu žádná neexistuje. '
                'Nemusíte kvůli tomu rozpočet navyšovat ani nic kupovat.</p>'
                '</details>'
            )
            continue
        # Original card positions are the ONLY allowed destinations.
        # Deterministic tie-breakers guarantee consistent behavior across
        # repeated daily feed refreshes with the same inputs.
        cheapest_pack = min(
            possible, key=lambda row: (row[2], row[3], row[0])
        )
        cheapest_unit = min(
            possible, key=lambda row: (row[3], row[2], row[0])
        )
        pack_pos, pack, pack_total, pack_per100 = cheapest_pack
        unit_pos, unit, unit_total, unit_per100 = cheapest_unit
        result.append(
            '<p data-xfit-budget-choice="upfront"><strong>V limitu do ' +
            str(limit) + ' Kč – nejnižší cena celého balení:</strong> '
            '<a href="#xfit-offer-' + str(pack_pos) + '">' +
            html.escape(pack["title"]) + '</a> — ' + money(pack_total) +
            ' za balení ' + str(pack["mass_g"]) + ' g; ' +
            money(pack_per100) + ' za 100 g prášku.</p>'
        )
        if unit_pos == pack_pos:
            result.append(
                '<p data-xfit-budget-choice="same">V limitu do ' +
                str(limit) + ' Kč má toto stejné balení zároveň nejnižší '
                'cenu za 100 g prášku. Nemusíte vybírat mezi levnějším '
                'nákupem a jednotkovou cenou.</p>'
            )
        else:
            result.append(
                '<p data-xfit-budget-choice="unit"><strong>V limitu do ' +
                str(limit) + ' Kč – nejnižší cena za 100 g prášku:</strong> '
                '<a href="#xfit-offer-' + str(unit_pos) + '">' +
                html.escape(unit["title"]) + '</a> — ' +
                money(unit_per100) + ' za 100 g prášku; celkem ' +
                money(unit_total) + ' za balení ' +
                str(unit["mass_g"]) + ' g. '
                'Úspornější jednotková cena může vyžadovat vyšší '
                'jednorázovou útratu.</p>'
            )
        result.append('</details>')

    result.append(
        '<p><small>Rozpočtové volby vycházejí jen z nabídek uvedených '
        'v tomto přehledu, nikoli z celého trhu. Aktuální cenu, etiketu '
        'a dostupnost vždy ověřte u prodejce.</small></p>'
    )
    result.append(
        '<p><small>' + (
            'Porovnáváme hmotnost syrovátkového prášku, nikoli množství '
            'skutečných bílkovin. '
            if product_kind == "whey" else
            'Porovnáváme hmotnost prášku, nikoli laboratorně potvrzenou '
            'čistotu kreatinu. '
        ) + 'Žádný z těchto cenových limitů není doporučením, že doplněk '
        'potřebujete. Pokud jej nepotřebujete, nekupujte jej.</small></p>'
    )
    return "\n".join(result)
