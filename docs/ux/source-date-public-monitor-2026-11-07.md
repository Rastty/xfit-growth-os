# XFIT — čtyřhodinový monitoring načtení cenového katalogu

Související vývoj: datum načtení NaMaximum XML v obou
komerčních poradcích ([PR #48](https://github.com/Rastty/xfit-growth-os/pull/48)).

## Konkrétní riziko

Po zavedení data načtení není dostačující kontrolovat jen stejný
počet produktových karet a jejich ceny. Starší veřejný cache
může ukazovat stejné produktové karty, ale **jiné datum zdroje**
než ověřený WordPress originál. A pokud denní XML refresh
několik dní selže, nabídka může stárnout bez upozornění.

## Co čtyřhodinový audit ověřuje

`scripts/xfit_public_freshness.py` je pouze read-only:

1. V obou schválených komerčních WP postech vyžaduje přesně
   jeden identifikovaný odstavec `xfit-feed-retrieval`.
2. Datum v českém formátu musí být skutečné datum, ne textová
   napodobenina; věta musí jasně uvést, že jde o **čas
   načtení katalogu**, nikoli změnu ceny.
3. Načtení je nejvýše **dva místní kalendářní dny staré**
   (`Europe/Prague`) a nesmí být v budoucnu.
   Oproti striktnímu publisher gate (4 hodiny při každém
   nové publikaci) jde o toleranci pro případ zpoždění
   plánovaného denního běhu.
4. Stejný odstavec a datum musí být také ve veřejném
   HTML, s tolerancí pouze pro známé typografické
   substituce WordPressu.
5. Existující ceny, produkty, affiliate URL, sponzorské
   atributy a identifikátory CTA se dál ověřují beze změny.

Stavy v redigovaném reportu:

- `PUBLIC_DATE_VERIFIED`: WP zdroj i web shodné a datum dostatečně čerstvé
- `SOURCE_DATE_MISSING_OR_INVALID`: žádné nebo duplicitní datum, neúplný WP zdroj
- `SOURCE_DATE_STALE_OR_IN_FUTURE`: zdrojové datum mimo povolené okno
- `PUBLIC_DATE_MISSING_OR_DIFFERENT`: zdroj pravdivý, ale veřejný web nesouhlasí

Audit nesmí logovat surové HTML, affiliate ID, product ID nebo
soukromá XML URL. **Žádný WordPress POST ani zásah do GA4.**

Při selhání je příslušný produkční stav **neověřený**.
Napravit jen po odděleném posouzení: oprava běhu ingestu,
validace cache nebo vydání stránky přes schválený publish
workflow. Samotný audit nesmí automaticky přepisovat web.

Vrácení této změny: revert kontrolního parseru a testů.
Veřejný WordPress obsah ani přidružené reportovací účty
se touto read-only úpravou nemění.
