# XFIT — PROJECT_STATE (2026-11-22)

**Cíl:** Důvěryhodný český rozhodovací web pro fitness, výživu a doplňky. Čtenář → vhodná volba / nic nekupovat → aktuální nabídka → ověřený affiliate proklik → **schválená a vyplacená** provize. Zdroj pravdy: GitHub `main`, nativní WordPress REST, skutečný public GET, GSC a oddělené soukromé Affial/GA4 důkazy. **Commit ≠ produkce; HTTP 200 ≠ indexace; klik ≠ objednávka.**

## HOTOVO — TURBO cyklus #1 (22. 11. 2026, produkčně ověřeno)

- [PR #354](https://github.com/Rastty/xfit-growth-os/pull/354) **MERGED** do `main` jako `23f70d6dedbf4dd139222a71513c0f216b6ea438`. Syrovátkový poradce generovaný ze zdrojového feedu nyní uvádí **jediný nesponzorovaný odkaz** na existující [rostlinný průvodce](https://xfit.cz/xfit-os-jak-vybrat-rostlinny-protein/) přímo uvnitř upozornění na mléčnou alergii **před první affiliate CTA**. Zachován rychlý výběr na první obrazovce; žádné nové produkty, ceny, tvrzení, redirecty nebo články. Nejprve zamítnuta příliš dlouhá varianta kvůli reálnému regresnímu testu, pak zkrácena bez oslabení testu.
- [PR XFIT Code Checks #45006023122](https://github.com/Rastty/xfit-growth-os/actions/runs/45006023122) SUCCESS; [PR mobilní Chromium preview #45006023071](https://github.com/Rastty/xfit-growth-os/actions/runs/45006023071) SUCCESS pro 320/375/768 px; [main CI #45006137345](https://github.com/Rastty/xfit-growth-os/actions/runs/45006137345) SUCCESS; **998 Python unit testů** v reálném následném publikačním běhu.
- [**Skutečný WP deploy #45006137392**](https://github.com/Rastty/xfit-growth-os/actions/runs/45006137392) SUCCESS: původní WP #25456 zazálohován **před POST** jako rollback artifact **#14748191499**, čerstvý NaMaximum katalog a Affial sample prošly kontrolou; API vrátilo `api_accepted` a následný no-cache public HTML readback `live_verified` pro [syrovátkový poradce](https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/). **1 existující stránka změněna, 0 nových článků**. Nezaměňovat s okamžitou konvergencí všech běžných CDN/cache odpovědí.
- [**Samostatná mobile production QA #45006137374**](https://github.com/Rastty/xfit-growth-os/actions/runs/45006137374) SUCCESS: browser QA živých stránek i generovaných prvních obrazovek v Chromium. Publikace je ověřena; zvýšení kliknutí, Google indexace cílové stránky ani provize **nejsou** doloženy.

## OVĚŘENÝ předchozí stav (nezapisovat znovu)

- [Nový rostlinný průvodce WP #25987](https://xfit.cz/xfit-os-jak-vybrat-rostlinny-protein/) produkčně publikován [AI run #45004735787](https://github.com/Rastty/xfit-growth-os/actions/runs/45004735787), z kontextu staršího protein guide WP #25451 propojen [onepost #45005187014](https://github.com/Rastty/xfit-growth-os/actions/runs/45005187014) s backupem. Všechny původní source-pinned editorial cíle jsou vyčerpané; nevytvářet duplicitní generické proteinové/kreatinové stránky.
- Homepage, kategorie Doplňky stravy #44: dříve ověřené pořadí **začátečnický no-buy hub #25458 → whey #25456 → kreatin #25455**; sticky/category-only distribuce proběhla s backupem a public proof. Žádný další write retry.
- [Live feed/public parity #44938351811](https://github.com/Rastty/xfit-growth-os/actions/runs/44938351811): **12/12** ověřených produktových ID/variant a uvedených cen odpovídalo NaMaximum XML (1 604 položek); 16 dříve validovaných CTA. Stav pokladny, dostupnost a provize z toho **nevyplývají**.
- [Prometheus Core GSC run #45001401327](https://github.com/Rastty/prometheus-growth-os/actions/runs/45001401327), uzavřené 28denní okno **23. 10.–19. 11. 2026: 8 kliků / 2 665 zobrazení / CTR 0,30 % / průměrná pozice 21,91**. Kreatinový poradce byl `Discovered - currently not indexed`, nová rostlinná stránka nemá doložené finální Google indexování. HTTP 200 nestačí.

## BLOKACE, hranice přístupu a bezpečnost

- Správná **XFIT GA4 property** není dostupná připojenému Windsor; schválené a vyplacené **Affial** výpisy nejsou připojené. Konverze, návštěvy po změně a zisk = **UNKNOWN, nikoli 0**. Existuje privátní/offline CSV reconciliace a consent-gated měření; nezavádět další duplicitní tracking pixel ani nevystavovat osobní data do veřejného GitHubu.
- Cizí otevřené PR [#248](https://github.com/Rastty/xfit-growth-os/pull/248), [#263](https://github.com/Rastty/xfit-growth-os/pull/263), [#270](https://github.com/Rastty/xfit-growth-os/pull/270), [#271](https://github.com/Rastty/xfit-growth-os/pull/271) nebyly změněny. Legacy WP **#7468 write-held** a **#3394 karanténa**; nepřepisovat cizí práci.
- Budoucí živý WP write: konkrétní identita a zdrojový SHA/CAS, původní úplná záloha nahraná **před** jediným POST pokusem, autentizované/veřejné čtení, rollback plán. Žádné hromadné mazání, noindex ani redirect bez tvrdých podkladů a záloh.

## DALŠÍ 3 CYKLY / priority

1. **Hotovo:** bezpečný syrovátkový → rostlinný rozhodovací přechod se skutečným WP deploy a mobile QA (PR #354).
2. **Nejvyšší ekonomická priorita:** skutečná XFIT GA4 landing/source/medium + consented outbound a soukromé Affial approved/paid výsledky; bez dat neoptimalizovat podle domnělých prodejů. Nenarušit existující rozpracované revenue PR #270.
3. **Růst bez duplicit:** po finálním GSC období ověřit novou rostlinnou URL a indexaci kreatinového poradce; další úpravy pouze na jednoznačně odlišných existujících buyer-intent URL s důkazy, kontrolou kanibalizace a QA.

[Úplný historický stav před TURBO cyklem](https://github.com/Rastty/xfit-growth-os/blob/811b73d3e6743820c42631e08458a33f9a00b518/PROJECT_STATE.md).
