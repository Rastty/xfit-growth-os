# XFIT: jednorázové dokončení nedokončené kuponové vlny — WordPress 11600

## Zjištění z běhu 42403149740 (7. 11. 2026)

Stará vlnová úloha `XFIT Expired Coupon Cleanup` zveřejnila účetní
doklad `coupon_wave_partial`: osm článků, 24 starých promo bloků
`5NM2022`; **sedm článků / 21 shortcode bloků již bylo opraveno**.
Článek WordPress **ID 11600** zůstal v původním stavu a běh
skončil chybou během `write_request`. Žádný nejistý post
nebyl vykázán. Starší issue #30 eviduje odlišný problém
s ID 11888 z 1. 11.; toto je jiný, přesně datovaný recovery cíl.

## Minimalizace rizika

Nová úloha je jednorázová a má **pouze jediný pevně zadaný post ID 11600**.
Nepoužívá původní hledání až osmi dalších příspěvků.
Je schopna odstranit pouze přesně **tři** schválené staré
`[su_button ...]...5NM2022[/su_button]` bloky,
při zachování celého dalšího textu a všech ostatních URL.
Nemaže články, nenastavuje přesměrování, nemění permalinky,
pluginy, témata ani aktuální nabídky.

Postup: ověřený WordPress read-only obsah a identita →
snapshot zdrojového obsahu a SHA-256 před/po →
**povinný rollback artefakt na GitHub Actions (90 dní)** →
ověření, že se zdroj od snapshotu nezměnil →
**nejvýše jeden** `POST /wp-json/wp/v2/posts/11600` pouze s
novým `content` → autorizované čtení a porovnání
SHA-256 → HTTP 200 veřejného kanonického článku bez
starého kódu. Když WordPress odpoví chybou i po uložení,
skript **neopakuje POST**, nýbrž bezpečně ověří skutečný stav.

Pokud se post mezitím změnil, nemá tři přesné bloky,
změnil identitu nebo není možné doložit veřejný výsledek,
běh skončí stavem `BLOCKED_MANUAL_REVIEW`,
`UNRESOLVED_UNCHANGED` nebo `API_VERIFIED_PUBLIC_STALE`.
Takový stav se nesmí považovat za úspěšnou publikaci.

## Hodnocení effort/effect

Odstranění zastaralé slevové pobídky má přímý přínos pro
důvěryhodnost a návštěvnické rozhodování, je v rámci
doložené existující kuponové chyby a lze je vrátit.
Nevyžaduje nové marketingové kampaně, hledání affiliate
programů nebo tvorbu duplicitního článku.

Workflow: `.github/workflows/xfit-coupon-post-11600-recovery.yml`.
Po merge se spustí automaticky; nemá trvalý rozvrh.
Testy: `tests/test_coupon_recovery.py` a celý projektový CI.
Záloha: `xfit-onepost-11600-rollback-<GitHub-run-id>`.
Na obsah 7 již opravených článků tento běh **nesahá**.

## Rozlišení důkazů

`PUBLIC_VERIFIED` s `posts_changed:1` je důkaz jedné
konkrétní změny článku 11600, ne osmi nových aktualizací.
`ALREADY_CLEAN_NO_WRITE` znamená nula nových zásahů.
Trvání chybového běhu, vytvoření zálohy ani úspěšné testy
nejsou samy o sobě publikací.

Vše bez jakéhokoli WordPress pluginu.
