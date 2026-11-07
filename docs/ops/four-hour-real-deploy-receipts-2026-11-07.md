# XFIT — čtyřhodinový report skutečných zásahů (7. 11. 2026)

## Problém

Dřívější status v issue #1 uváděl počty úspěšných a chybných
GitHub Actions. Z těchto čísel **nelze** poznat, zda se na Xfit.cz
skutečně změnil článek, přibyl nový obsah, nebo proběhly jen testy.

## Nová metodika

`scripts/xfit_status_evidence.py` čte v intervalu posledních čtyř
hodin **jen existující, jmenovitě schválená publikační GitHub workflow**.
Z jejich úspěšných běhů si vyžádá job logs, avšak započítá pouze
jednoznačné produkční potvrzení:

- `live_verified` se správným vlastním WordPress post ID,
  kanonickou URL HTTPS xfit.cz a explicitním potvrzením reálné
  změny nebo ověřeným legacy publisherem;
- `PUBLIC_VERIFIED_NEW_POST` s `new_posts:1` označí skutečnou
  novou publikaci;
- `ALL_PINNED_ARTICLES_PUBLIC_VERIFIED` s `new_posts:0`,
  `NO_APPROVED_TARGET`, `unchanged_public_verified` jsou
  doložené běhy **bez nové změny**;
- zelené CI, `api_accepted` bez následného veřejného potvrzení,
  chybějící nebo nečitelný log, selhaná publikace či nedokončený
  job **nikdy nejsou započítány jako prokázaná změna**.
  Označí se `NEOVĚŘENO`, nikoli tiše jako nula.

Stejný WordPress post v jediném běhu se počítá jen jednou.
U konkrétních komerčních poradců se navíc vynucují vlastní WP ID
25455 a 25456. K reportu se přidává veřejný odkaz na stránku
a příslušný GitHub Actions run.

U publikačních nástrojů bez důkazu, zda jde o nový nebo
existující post, je použita samostatná kategorie
**publikace nebo úprava (typ neověřen)**. To zabraňuje
nepodloženému označení za nový článek.

## Limity

Počty jsou **ověřené výsledky schválených publikačních workflow**,
nikoli nezávislý úplný audit všech ručních úprav WordPressu.
Pokud někdo upraví web přímo v administraci, status to nemusí
zachytit. Výstup neposkytuje objednávky, prokliky ani provize.

Pomocná komponenta drží neveřejné logy pouze v paměti, limituje
jejich velikost, vrací jen bezpečný kanonický odkaz, typ změny,
ID WordPressu a příslušný run. GitHub bearer token se nesmí
předat na odlišný host při stahování logů přes přesměrování.
Nedostupnost Actions API nesmí vygenerovat falešné číslo nula.

## Nasazení a ověření

`python -m unittest tests.test_status_evidence -v` a celý CI
na PR. Po merge se jednorázově spustí `XFIT Four-hour Status`,
který zveřejní report do issue #1. Bude se opakovat podle
dosavadního `13 */4 * * *` (UTC). Na WordPressu
ani v GA4 se tímto nic nemění.

Rollback: revert `scripts/xfit_status_evidence.py`,
jeho napojení do `xfit_status.py`, testů a workflow.
Již publikované stránky zůstanou beze změny.
