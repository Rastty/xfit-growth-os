"""Fast, feed-backed above-the-fold choices for existing XFIT adviser cards.

Never invent stock, dispatch, a discount or a new affiliate destination.
The only purchase-related links are local anchors to verified product cards.
"""

import html
from decimal import Decimal

from scripts.wp_publish import PublishError
from scripts.xfit_budget_choices import _price, money


def quick_pick(selected, *, product_kind):
    if product_kind not in ("creatine", "whey"):
        raise PublishError("Unsupported quick-pick product type")
    if not isinstance(selected, list) or not 2 <= len(selected) <= 12:
        raise PublishError("Quick pick requires a bounded verified shortlist")
    checked = []
    ids = set()
    for position, item in enumerate(selected, 1):
        if not isinstance(item, dict):
            raise PublishError("Invalid quick-pick product")
        ident, title, grams = item.get("id"), item.get("title"), item.get("mass_g")
        if (not isinstance(ident, str) or not ident or ident in ids or
                not isinstance(title, str) or not title.strip() or
                type(grams) is not int or not 50 <= grams <= 10000 or
                not (item.get("tracked_url") or item.get("affiliate_url"))):
            raise PublishError("Quick pick cannot resolve a verified product card")
        total = _price(item.get("price_czk"))
        per100 = _price(item.get("price_per_100g_powder_czk"))
        if (total > Decimal("1000000") or per100 > Decimal("1000000") or
                abs(total * Decimal(100) / Decimal(grams) - per100) > Decimal("0.01")):
            raise PublishError("Quick-pick price conflicts with feed evidence")
        ids.add(ident)
        checked.append((position, item, total, per100))

    cheap = min(checked, key=lambda row: (row[2], row[3], row[0]))
    unit = min(checked, key=lambda row: (row[3], row[2], row[0]))

    def card(row, kind, heading):
        position, item, total, per100 = row
        return (
            '<div data-xfit-quick-pick="' + kind + '" style="flex:1 1 245px;min-width:0;'
            'border:1px solid #d0e0e2;border-radius:12px;padding:14px;'
            'background:#f5fbfa;overflow-wrap:anywhere;">'
            '<p><strong>' + heading + '</strong></p>'
            '<p>' + html.escape(item["title"]) + '</p>'
            '<p><strong>' + money(total) + '</strong> za ' + str(item["mass_g"]) +
            ' g · ' + money(per100) + ' / 100 g prášku</p>'
            '<p><a href="#xfit-offer-' + str(position) + '" style="display:inline-block;'
            'box-sizing:border-box;min-height:44px;padding:12px 16px;'
            'background:#116a70;color:#fff;text-decoration:none;'
            'border-radius:8px;font-weight:700;">Zobrazit balení</a></p></div>'
        )

    parts = [
        '<section id="xfit-rychly-vyber" aria-label="Rychlý výběr podle ceny">',
        '<h2>Rychlý výběr z porovnaných balení</h2>',
        '<p>Chcete zaplatit co nejméně za celé balení, nebo získat nejnižší '
        'cenu za 100 g prášku? Vyberte prioritu a přejděte ke konkrétní nabídce.</p>',
        '<div style="display:flex;flex-wrap:wrap;gap:12px;">',
    ]
    if cheap[0] == unit[0]:
        parts.append(card(cheap, "both", "Nejnižší cena balení i za 100 g"))
    else:
        parts.append(card(cheap, "upfront", "Nejmenší výdaj dnes"))
        parts.append(card(unit, "unit", "Nejnižší cena za 100 g"))
    parts += [
        '</div>',
        '<p data-xfit-quick-pick="no-buy">Nejste si jistí, že doplněk potřebujete? '
        '<a href="#xfit-need">Nejdřív zjistit, zda nekoupit nic</a>.</p>',
        '<p><small>Srovnáváme jen ' + str(len(selected)) + ' vybraných nabídek '
        'z načteného katalogu, nikoli celý trh. Cenu, dostupnost a etiketu '
        'ověřte před nákupem u prodejce. '
        + ('Jde o cenu prášku, ne čistých bílkovin.' if product_kind == "whey"
           else 'Jde o cenu prášku, ne laboratorně potvrzenou čistotu kreatinu.')
        + '</small></p>',
        '</section>',
    ]
    return "\n".join(parts)
