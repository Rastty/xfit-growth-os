"""Feed-backed first-screen choices linking to their exact verified card offers.

Never invent stock, dispatch, a discount or a new affiliate destination.
Each merchant CTA must equal the corresponding lower product-card CTA.
"""

import html
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

from scripts.wp_publish import PublishError
from scripts.xfit_budget_choices import _price, money
from scripts.xfit_click_metadata import card_click_attributes


AFFIL_KEYS = {"utm_medium", "utm_campaign", "utm_source", "a_aid", "a_bid"}


def _tracked_offer(item, product_kind):
    """Accept only the already assembled NaMaximum/Affial product deeplink."""
    href = item.get("tracked_url") or item.get("affiliate_url")
    if not isinstance(href, str):
        raise PublishError("Quick pick has no verified affiliate destination")
    try:
        url = urlsplit(href)
        params = parse_qs(url.query, keep_blank_values=True)
    except ValueError as exc:
        raise PublishError("Invalid quick-pick affiliate URL") from exc
    if (url.scheme != "https" or url.hostname not in
            ("namaximum.cz", "www.namaximum.cz") or
            url.username or url.password or url.port is not None or url.fragment or
            not url.path or url.path.rstrip("/") in ("", "/") or
            url.path.startswith("//") or
            not AFFIL_KEYS.issubset(params) or
            not set(params).issubset(AFFIL_KEYS | {"variant", "data1", "data2"}) or
            any(len(values) != 1 or not values[0] for values in params.values()) or
            params["utm_medium"] != ["affiliate"] or
            params["utm_campaign"] != ["affial.com"] or
            params["utm_source"] != ["pap"] or
            ("variant" in params and params["variant"] != [item["id"]]) or
            (any(key in params for key in ("data1", "data2")) and
             (product_kind != "creatine" or
              params.get("data1") != ["xfit"] or
              params.get("data2") != ["creatine"]))):
        raise PublishError("Unverified quick-pick merchant tracking or product variant")
    return href


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
        href = _tracked_offer(item, product_kind)
        total = _price(item.get("price_czk"))
        per100 = _price(item.get("price_per_100g_powder_czk"))
        if (total > Decimal("1000000") or per100 > Decimal("1000000") or
                abs(total * Decimal(100) / Decimal(grams) - per100) > Decimal("0.01")):
            raise PublishError("Quick-pick price conflicts with feed evidence")
        ids.add(ident)
        checked.append((position, item, total, per100, href))

    cheap = min(checked, key=lambda row: (row[2], row[3], row[0]))
    unit = min(checked, key=lambda row: (row[3], row[2], row[0]))

    def card(row, kind, heading):
        position, item, total, per100, href = row
        return (
            '<div data-xfit-quick-pick="' + kind + '" style="flex:1 1 245px;min-width:0;'
            'border:1px solid #d0e0e2;border-radius:12px;padding:14px;'
            'background:#f5fbfa;overflow-wrap:anywhere;">'
            '<p><strong>' + heading + '</strong></p>'
            '<p>' + html.escape(item["title"]) + '</p>'
            '<p><strong>' + money(total) + '</strong> za ' + str(item["mass_g"]) +
            ' g · ' + money(per100) + ' / 100 g prášku</p>'
            '<p><a' + card_click_attributes(item["id"], product_kind) +
            ' data-xfit-cta="quick-pick" href="' + html.escape(href, quote=True) +
            '" rel="sponsored nofollow noopener noreferrer" target="_blank" '
            'aria-label="Ověřit cenu a dostupnost produktu ' +
            html.escape(item["title"], quote=True) +
            ' na NaMaximum.cz (nová karta)" style="display:inline-block;'
            'box-sizing:border-box;min-height:44px;padding:12px 16px;'
            'background:#116a70;color:#fff;text-decoration:none;'
            'border-radius:8px;font-weight:700;">Ověřit cenu a dostupnost</a></p>'
            '<p><small>NaMaximum.cz · nová karta · '
            '<a href="#xfit-offer-' + str(position) + '" style="display:inline-block;'
            'min-height:44px;padding:12px 0;box-sizing:border-box;">'
            'Detail balení ve srovnání</a></small></p></div>'
        )

    parts = [
        '<section id="xfit-rychly-vyber" aria-label="Rychlý výběr podle ceny">',
        '<h2>Rychlý výběr z porovnaných balení</h2>',
        '<p>Porovnejte nejnižší cenu balení a cenu za 100 g prášku. '
        'Cenu i dostupnost ověřte v obchodě.</p>',
        '<p><small>Partnerské affiliate odkazy na NaMaximum.cz: XFIT může získat provizi. '
        'Výběr neřadíme podle provize.</small></p>',
        *(['<p><strong>Cena prášku není cena čistých bílkovin.</strong> '
           'Cenu za skutečné bílkoviny zjistíte až z nutriční tabulky. '
           'Máte konkrétní etiketu? Použijte '
           '<a href="https://xfit.cz/xfit-os-cena-proteinu-podle-etikety/">'
           'postup přepočtu ceny podle nutriční etikety</a>. '
           'Bez ověřeného údaje o bílkovinách u každé varianty nelze '
           'seřadit nabídky podle ceny za čisté bílkoviny. '
           'Když protein nepotřebujete, nemusíte kupovat nic.</p>']
          if product_kind == 'whey' else []),
        '<p data-xfit-quick-pick="no-buy">Nákup není nutný: '
        '<a href="#xfit-need">zjistit, zda nepotřebuji doplněk</a>.</p>',
        '<div style="display:flex;flex-wrap:wrap;gap:12px;">',
    ]
    if cheap[0] == unit[0]:
        parts.append(card(cheap, "both", "Nejnižší cena balení i za 100 g"))
    else:
        parts.append(card(cheap, "upfront", "Nejmenší výdaj dnes"))
        parts.append(card(unit, "unit", "Nejnižší cena za 100 g"))
    parts += [
        '</div>',
        '<p><small>Srovnáváme jen ' + str(len(selected)) + ' vybraných nabídek '
        'z načteného katalogu, nikoli celý trh. Cenu, dostupnost a etiketu '
        'ověřte před nákupem u prodejce. '
        + ('Jde o cenu prášku, ne čistých bílkovin.' if product_kind == "whey"
           else 'Jde o cenu prášku, ne laboratorně potvrzenou čistotu kreatinu.')
        + '</small></p>',
        '</section>',
    ]
    return "\n".join(parts)
