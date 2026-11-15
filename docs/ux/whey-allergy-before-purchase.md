# Issue #2: viditelné upozornění před nákupem syrovátky

## Přínos a rozsah

Poradce dříve zobrazil rychlé partnerské odkazy před upozorněním na
mléčnou alergii, které bylo ve sbaleném `<details>`. Existující upozornění
je nyní samostatný viditelný odstavec před první nákupní možností.
Text o veganské stravě a konzultaci zdravotních omezení zůstává v rozcestníku.
Nevznikají nová zdravotní tvrzení ani duplicitní upozornění.
Řazení, ceny, produktové URL a affiliate metadata se nemění.

## Ověření

- 36 cílených testů prošlo: `python -m unittest tests.test_whey_guide
  tests.test_creatine_guide tests.test_ux_no_purchase
  tests.test_ux_guide_navigation tests.test_ux_card_wrapping
  tests.test_ux_checkout_budget`.
- Regresní test kontroluje jediné upozornění mimo `<details>` před prvním
  sponzorovaným odkazem a zachování informace o alergenech v izolátu.
- Kontrola UX scope a `git diff --check` prošly.
- Lokální headless Chromium se nespustilo ani s profilem v `/tmp`;
  screenshot a kontrola šířky 375 px tedy nejsou ověřené.
  Testovací HTML používá syntetický katalog a CSP zakazující síťové zdroje.

## Stav a další krok

Připraveno a lokálně testováno. CI, nasazení WP API a veřejná stránka
neověřeny. Dopad na kliknutí a objednávky: UNKNOWN.
Žádné publikování ani požadavky na xfit.cz.
Další fáze má ověřit diff a mobilní zobrazení lokálně na 375 px.
Rollback: vrátit tento patch generátoru a jeho regresní test;
žádná produkční data se v této fázi nezměnila.
