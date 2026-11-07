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
    """Return accessible, no-script budget chooser for the selected offers.

    Indexes MUST correspond to the existing xfit-offer-N anchors, not new
    affiliate redirects. For each limit, choose the lowest unit cost that
    fits, breaking ties by actual total price and original card order.
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
        '<p>Vyberte si svůj cenový limit. U každého ukazujeme nabídku '
        's nejnižší cenou za 100 g prášku, která se do něj vejde. '
        'Vycházíme jen z výrobků již uvedených níže, ne z celého trhu. '
        'Ceny se mohou změnit.</p>',
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
        number, item, total, per100 = min(
            possible, key=lambda row: (row[3], row[2], row[0])
        )
        # Use a same-page anchor; the catalog product destination and tracking
        # remain exclusively in the original verified sponsored CTA.
        result.append(
            '<p><strong>V limitu do ' + str(limit) + ' Kč má nejnižší jednotkovou cenu:</strong> '
            '<a href="#xfit-offer-' + str(number) + '">' +
            html.escape(item["title"]) + '</a> — ' + money(total) +
            ' za balení ' + str(item["mass_g"]) + ' g; ' +
            money(per100) + ' za 100 g prášku. '
            'Před případným nákupem ověřte etiketu, cenu a dostupnost '
            'u prodejce.</p></details>'
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
