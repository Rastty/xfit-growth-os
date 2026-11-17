# XFIT — novější GSC důkaz a hranice technického monitoru

Podklad: [Prometheus XFIT GSC read-only run 43902699281](https://github.com/Rastty/prometheus-growth-os/actions/runs/43902699281),
**úspěšný job `capture`** dne 16. 11. 2026. Nezaměňovat se stavem
`offline=success` u novějších běhů, kde byl samotný `capture=skipped`.

GSC webový výstup za uzavřené období **17. 10. až 13. 11. 2026**:
9 kliknutí, 1 357 zobrazení, CTR přibližně 0,66 %, průměrná pozice 30,41.
Jde o celý web, nikoli o úspěch konkrétního poradce a nikoli o GA4 sessions.

## URL Inspection (stav při zdrojovém běhu)

| URL slug | Google coverage | Last crawl reported |
| --- | --- | --- |
| `xfit-os-doplnky-pro-zacatecniky` | Submitted and indexed | 10. 11. 2026 |
| `xfit-os-protein-guide` | Submitted and indexed | 10. 11. 2026 |
| `xfit-os-kreatin-poradce` | Discovered - currently not indexed | Neuvedeno |
| `xfit-os-syrovatkovy-protein-porovnani` | Submitted and indexed | 10. 11. 2026 |
| `xfit-os-kreatin-nebo-protein` | Discovered - currently not indexed | Neuvedeno |
| `xfit-os-cena-proteinu-podle-etikety` | Submitted and indexed | 12. 11. 2026 |

Vlastní read-only `xfit_indexability_preflight.py` dne 17. 11. 2026 ověřil
**6/6 HTTP 200, správný self-canonical, bez zjištěného noindex a explicitní
výskyt 6/6 v kompletně přečtených šesti dílčích WordPress sitemap XML**.
To neprokazuje zaindexování. Původně skript při každém běhu přidával
historický GSC stav z 8. 11.; od nynějška vrací
`NOT_MEASURED_BY_THIS_PREFLIGHT` a nehraje si na živou inspekci Googlu.

## Nejbližší akce podle skutečného dopadu

1. Pro dva dosud neindexované slugs **nepřepisovat stejné články opakovaně**.
   Nejprve ověřit, zda jejich unikátní rozhodovací přínos není překryt
   zaindexovanými průvodci, a zda interní odkazy ze skutečně navštěvovaných
   tematických URL vedou k relevantní části poradce. K dispozici je již
   4–6 inlinků v sedmi kontrolovaných článcích; další náhodné odkazy nejsou
   automaticky lepší.
2. Pro zaindexované stránky optimalizovat konkrétní dotazy s impresí a
   špatnou proklikovostí, nikoliv genericky navyšovat počet článků.
   Source-backed tři kandidáti z výstupu: Pilates rozdíly (96 zobrazení,
   1 klik, pozice 6,51), Pilates pro záda po úrazu (30 zobrazení,
   0 kliků, pozice 8,37), kreatin pro začátečníky (29 zobrazení,
   0 kliků, pozice 22,66). Před úpravou znovu ověřit záměr dotazu,
   medicínská tvrzení a poslední zásahy do těchto URL.
3. Pro nákupní cesty odděleně ověřit consent-gated GA4 klik a síťový
   report Affial; GSC klik není affiliate proklik ani provize.

Nevydávat rozdíl proti staršímu překrývajícímu se 28dennímu oknu za
**inkrementální efekt našich zásahů**. Novější stav může znovu změnit další
platná URL Inspection. Monitoring technického indexování zůstává nezávislý
na OAuth tokenu Promethea; nepřenášet credentials do XFIT repa.

**Produkční změny:** 0 WordPress zápisů, 0 Search Console požadavků o indexaci,
0 nových článků, 0 pluginů. Jen přesnější interní interpretace důkazů.
