"""Czech, transparent model-portion arithmetic for verified XFIT catalog cards.

This uses only the package's catalog price and inferred powder mass. It is
NOT a serving instruction, actual protein content, purity or stock evidence.
No personal answers or browser analytics are involved.
"""
from decimal import Decimal, ROUND_HALF_UP

from scripts.wp_publish import PublishError
from scripts.xfit_budget_choices import _price, money

MODEL_GRAMS = {"creatine": 3, "whey": 30}


def model_portion_line(offer, engine):
    """Explain count of complete hypothetical powder portions and price.

    Cost is the linear model price per gram times sample grams, not total
    price divided by rounded full portions: that would incorrectly count
    unused remainder as if consumed. Always use source price and mass.
    """
    if engine not in MODEL_GRAMS:
        raise PublishError("Unsupported model-portion engine")
    if not isinstance(offer, dict):
        raise PublishError("Incomplete model portion source")

    mass = offer.get("mass_g")
    if type(mass) is not int or not 50 <= mass <= 10000:
        raise PublishError("Invalid known powder package mass")
    price = _price(offer.get("price_czk"))
    grams = MODEL_GRAMS[engine]
    count = mass // grams
    if count < 1:
        raise PublishError("Package too small for model portion")
    cost = (price * Decimal(grams) / Decimal(mass)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return (
        '<p class="xfit-model-portion">'
        '<strong>Modelové porce po ' + str(grams) + ' g prášku:</strong> ' +
        str(count) + ' celých porcí v balení · přibližná cena ' +
        money(cost) + ' za ' + str(grams) +
        ' g prášku.</p>'
    )


def model_portion_intro(engine):
    if engine == "creatine":
        return (
            '<p><strong>Co stojí modelová porce?</strong> U produktů níže '
            'ukazujeme počet celých modelových porcí po 3 g prášku a '
            'jejich matematickou cenu podle ceny a gramáže balení. '
            'Nejde o doporučené denní dávkování, ověřenou čistotu kreatinu '
            'ani o záruku aktuální ceny či dostupnosti u prodejce.</p>'
        )
    if engine == "whey":
        return (
            '<p><strong>Co stojí modelová porce?</strong> U produktů níže '
            'ukazujeme počet celých modelových porcí po 30 g syrovátkového '
            'prášku a jejich matematickou cenu podle ceny a gramáže balení. '
            'Porce 30 g prášku není 30 g skutečných bílkovin; '
            'nejde o doporučenou dávku ani záruku aktuální ceny či skladu.</p>'
        )
    raise PublishError("Unsupported model-portion engine")
