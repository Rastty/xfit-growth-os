# XFIT — modelové náklady na porci prášku

## Změna pro návštěvníka (7. listopadu 2026)

Obě původní, komerčně transparentní srovnávací stránky nově vedle
ceny balení a ceny za 100 g prášku uvádějí matematický přepočet na
**modelové porce**. U kreatinu se počítá **3 g prášku**, u syrovátkového
proteinu **30 g prášku**. Jedná se pouze o přehledné cenové měřítko,
nikoli o doporučení užívat doplněk ani o závaznou porci výrobce.

Počet celých porcí = `mass_g // model_grams`.
Orientační náklad za modelovou porci =
`catalog_price_czk * model_grams / mass_g`, zaokrouhlený na haléře
metodou `ROUND_HALF_UP`. Zbytek prášku se nepřipočítává k počtu
celých porcí, ale **není** vymyšleně rozpočítán jen mezi ně.

Hmotnost balení je stávající validovaný údaj odvozený z názvu
produktové varianty ve feedu, nikoli ručně domyšlený obsah bílkovin.
Cena pochází ze stejné ověřené nabídky jako nákupní tlačítko.
Nesdělujeme čistotu kreatinu, reálné gramy proteinů, účinek ani
aktuální sklad. Každý údaj je označen jako přibližný výpočet.
Výstup přidává **pouhý HTML odstavec** k existující kartě:
žádné nové affiliate URL, cookies, analytické události nebo údaje
návštěvníka.

## Rollout, důkazy a limity

CI: `python -m unittest discover -s tests -v`.
Po merge se oba přísně source-bound publisher workflows spustí
na změnu `scripts/xfit_model_portions.py`, aktualizují pouze
vlastní WordPress posty **25455** a **25456** a musí projít
redakční kvalitou, autentizovaným readbackem a veřejnou kontrolou.

Mobilní QA na šířce 375 px nově ověřuje jeden modelový řádek na
každé skutečné produktové kartě v obou poradcích, explicitní
vysvětlení a stávající přístupnost včetně rozpočtů a CTA.
Před potvrzeným `live_verified` a browser PASS netvrdit, že je
tato nová funkce na produkci.

Projektová analytika je oddělená: absence přihlášeného
consent-gated analytického pluginu znamená, že skutečné affiliate
kliky, objednávky a provize zůstávají **UNKNOWN**.

Rollback: revert call-site změn a modulu, znovu spustit oba
autorizované WP workflows; žádná práva, data ani pluginy
nejsou tímto změněny.
