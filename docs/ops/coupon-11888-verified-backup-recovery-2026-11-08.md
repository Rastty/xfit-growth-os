# Xfit: dokončení archivního kuponu WP 11888 — 8. listopadu 2026

## Proč právě tento zásah

[Issue #30](https://github.com/Rastty/xfit-growth-os/issues/30) a
[skutečný 1.11. běh 41292398911](https://github.com/Rastty/xfit-growth-os/actions/runs/41292398911)
dokládají 7 úspěšných změn, **21 odstraněných starých bloků**, ale
jeden nezměněný článek **WP ID 11888** ve stavu
`write_request / unchanged`.

Originální GitHub Actions rollback artefakt
**13077688224** (`xfit-expired-coupon-rollback-41292398911`) byl znovu
stažen a ověřen: přesná permalink URL
`https://xfit.cz/nejnovejsi-vyzkum-ktery-kreatin-je-nejucinnejsi-pro-fitness-v-roce-2022/`,
původní SHA-256 `9ba46c6319b124cc708acbba32f7aa9e53abf6871a999bea4555799c7f597f37`,
cílový SHA-256 `e10d06a0a2bebe3f7ac3b6500515b4cb91f6aa36cf3514d0500902ac672cd496`.
Přesný původní text obsahoval **3** `5NM2022` bloky
`[su_button...][/su_button]`; po odstranění už žádný výskyt
`5NM2022` nezůstává. Nejde o mazání článku ani přesměrování
staré URL.

## Bezpečné provedení

- Jen jedno natvrdo povolené WP ID 11888, slug, kanonická HTTPS URL.
- Čerstvý read-only `posts/11888?context=edit`, status `publish`.
- Když je zdroj stále přesně na původním SHA-256, připraví se
  odebrání tří výhradně starých promo shortcodů.
- Když je zdroj již přesně na cílovém SHA-256, je to
  `ALREADY_CLEAN_NO_WRITE` a jen se ověří veřejná stránka.
- Když došlo k jakékoli jiné změně od 1. listopadu,
  běh se **bez zápisu bezpečně zastaví**; nepřepisovat
  cizí redakční obsah ani experimentovat s dalšími změnami.
- Před případným zápisem vždy nové úplné zálohované HTML,
  SHA-256 a povinný GitHub Actions rollback artifact (90 dní).
- Nejvýše **jeden** WordPress REST POST měnící jen `content`,
  bez opakování ani při timeoutu; poté autentizovaný GET a
  porovnání celého cílového SHA-256.
- Samostatný veřejný HTTP GET musí dostat 200 na přesné
  kanonické stránce, jejíž HTML již neobsahuje starý kód.

## Evidence a reporting

`PUBLIC_VERIFIED` = jedna konkrétní **aktualizace existující
stránky**, tři odstraněné bloky a nula nových článků.
`ALREADY_CLEAN_NO_WRITE` = nula nových zásahů.
`UNRESOLVED_UNCHANGED`, `BLOCKED_MANUAL_REVIEW` nebo
`API_VERIFIED_PUBLIC_STALE` nesmějí být vykazovány jako
úspěšné publikace.

Tento one-off workflow nemá pravidelný rozvrh ani
zásah do ostatních historických článků. Případné rollbacky
musí zkontrolovat dnešní stav a nekopírovat starou zálohu
přes novější práci redaktorů.

**0 nových WordPress pluginů, 0 změn affiliate URL,
0 zdravotních/klinických tvrzení.**
