# Xfit — rozpočtový rozcestník v obou produktových poradcích (2026-11-07)

## Co se mění pro návštěvníka

Kreatinový poradce přidává rozpočtové volby **do 500 / 1000 / 1500 Kč**,
syrovátkový poradce **do 750 / 1200 / 2000 Kč**. V každém limitu se zobrazí
počet položek v **aktuálním omezeném výběru** a nejnižší jednotková cena
za 100 g prášku mezi vybranými položkami, které nepřekračují cenový strop.
Odkaz je pouze kotva na existující produktovou kartu; neexistují žádné nové
affiliate URL ani události.

Záměrně se neoznačuje jako nejlevnější produkt na celém trhu a neřeší
zásoby, gramáž skutečných bílkovin ani čistotu kreatinu. Nulová nabídka
znamená jen to, že se do limitu nevejde nic **z právě zobrazených karet**.
Bez doporučení další útraty a s výslovnou cestou nekoupit nic.

## Neměnné podmínky

- Kontrolovaná feedová data, rozumná cena a jednotková cena, 1:1 shoda
  kotvy s kartou a stejné pořadí karet jako dosud.
- Obě stránky nadále používají WP REST release a veřejné readback ověření.
  Všechny zdrojové odkazy, provize, sponsor atributy, pořadí produktů a
  redakční/vědecká tvrzení zůstávají beze změny.
- Nativní HTML `details/summary` bez JavaScriptu, formuláře a cookies.
- Žádná data ani odpovědi návštěvníka se neodesílají. Rozcestník není
  provozní měření GA4 a nezvyšuje sám o sobě ověřené konverze.
- Po merge kontrolovat výsledek `XFIT Creatine Advisor Live` a
  `XFIT Whey Advisor Live`, přesné URL / slugs a veřejný text.
  Kód/CI není důkazem publikace.

## Rollback

Revert commit měnící `scripts/xfit_budget_choices.py` a obě volání
`budget_choices`, poté zopakovat schválené produkční release s
WP readback. Žádný kontakt s dalšími stránkami a žádné hromadné změny.
