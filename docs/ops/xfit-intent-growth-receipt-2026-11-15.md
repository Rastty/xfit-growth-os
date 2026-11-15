# XFIT — produkční evidence a vstupní GSC stav, 15. 11. 2026

**Produkčně ověřeno:** 4 stávající články s přesně jedním kontextovým interním proklikem do poradce. **Neověřeno / beze změny:** WP 7363 po jediném POST; následná read-only kontrola našla shodný původní HTML hash i po cache-busted GET, bez veřejné změny, bez opakovaného zápisu.

| Stav | Článek WP | Cíl | Actions evidence |
| --- | ---: | --- | --- |
| PUBLIC_VERIFIED | 10854 | Kreatinový poradce | [43722244539](https://github.com/Rastty/xfit-growth-os/actions/runs/43722244539) |
| PUBLIC_VERIFIED | 10738 | Kreatinový poradce | [43722244539](https://github.com/Rastty/xfit-growth-os/actions/runs/43722244539) |
| UNRESOLVED_OR_DRIFTED (beze změny) | 7363 | Syrovátkové srovnání | [43722244539](https://github.com/Rastty/xfit-growth-os/actions/runs/43722244539), [read-only 43722689086](https://github.com/Rastty/xfit-growth-os/actions/runs/43722689086) |
| PUBLIC_VERIFIED | 9772 | Kreatinový poradce | [43722983627](https://github.com/Rastty/xfit-growth-os/actions/runs/43722983627) |
| PUBLIC_VERIFIED | 7195 | Syrovátkové srovnání | [43722983627](https://github.com/Rastty/xfit-growth-os/actions/runs/43722983627) |

Originální HTML všech pěti zdrojů bylo uloženo před zápisem do Actions artifact ID `14164184099` a `14165216907`, s expirací 13. 2. 2027. Každý publikovaný článek má nezávislý veřejný readback; nebyly založeny nové URL, mazány stránky ani instalovány pluginy.

## Skutečný GSC baseline před efektem zásahů

Prometheus [XFIT GSC read-only run 43722262547](https://github.com/Rastty/prometheus-growth-os/actions/runs/43722262547), uzavřené období 16. 10. – 12. 11. 2026:

- 9 organických kliknutí z Googlu, 1 250 zobrazení, CTR 0,72 %, průměrná pozice 31,37 (agregace celého webu).
- `xfit-os-kreatin-poradce`: **Discovered - currently not indexed**, proto nový obsahový interní odkaz může pomoci objevení/crawl prioritě, ale není důkazem, že Google stránku zaindexuje.
- `xfit-os-syrovatkovy-protein-porovnani`: **Submitted and indexed** (inspekce URL, nikoliv záruka návštěvnosti).

Tato čísla jsou **baseline před nasazením prolinkování**, nikoli dosažené zlepšení. Po čase na recrawl porovnat stejná uzavřená 28denní GSC okna a sledovat kliknutí/zobrazení zdrojových i cílových URL, indexaci kreatinového poradce, GA4 `advisor_start`, partner outbound a teprve pak schválené/proplacené Affial provize. `UNKNOWN` provize nepočítat jako nulu ani jako výdělek.

Strojově čitelný source-backed přehled vedle: `xfit-intent-growth-receipt-2026-11-15.json`. Sdílení postupu do Prometheus Core vyžaduje samostatné převzetí; tímto dokumentem se Core nemění.
