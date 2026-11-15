# XFIT – nákupní CTA ve dvou poradcích (15. 11. 2026)

## Problém

Na šesti produktových kartách v každém z poradců je dlouhý technický text
odkazu „Zobrazit konkrétní balení na NaMaximum.cz (nová karta)“.
Na mobilní šířce je čitelnější krátká akce, která odpovídá tomu, co si má
návštěvník před rozhodnutím skutečně ověřit.

## Zásah

- Viditelné CTA: **Ověřit cenu a dostupnost**.
- Vedle tlačítka zůstává explicitní partner a informace „nová karta“.
- Čtečky obrazovky dostávají individuální název produktu a obchod.
- Původní URL, affiliate identifikátory, variant, označení sponsored,
  product ID, pořadí nabídek a obsah zdravotních upozornění se nemění.
- Dvě existující WordPress stránky aktualizují vlastní workflow; před
  zápisem uloží plnou zálohu a po zápisu ověří veřejný výsledek.

## Ověření efektu

Přínos je **hypotéza**, nikoli doložený uplift. Stávající XFIT public
preflight nepotvrdil aktivní first-party click adapter ani skutečné
události `affiliate_outbound_click`, proto zde neuvádíme CTR ani nákupy.
Pro věrohodné A/B měření je nutná souhlasová GA4 integrace, návštěvnost
a předem definovaný časový rámec; změna je zatím jednorázová UX iterace.

Technický důkaz: unit testy s produktovými variantami a affiliate URL;
browser QA při 375 px vyžaduje správný text, produktové označení,
obchod a dostatečně velký klikací prvek. Při neúspěšném vydání se
nesmí vydávat kódový commit za publikovaný obsah.
