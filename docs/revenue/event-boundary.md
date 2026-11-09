# Issue #5: bezpečné parametry událostí

`scripts/xfit_revenue_events.py` je offline validační hranice pro budoucí
měření dvou existujících poradců. Nic neodesílá, neukládá a nemění GA4.
Pomáhá připravit měření užitečnosti poradce a prokliků bez sběru jeho odpovědí.

`build_event(name, fields, analytics_consent=True)` připraví pouze:

- `advisor_start` a `advisor_complete`: schválený slug stránky a odpovídající
  `selection_engine` (`creatine` nebo `whey`).
- `affiliate_outbound_click`: navíc `partner=namaximum` a kladné celočíselné
  katalogové `product_id`. Identifikátor musí pocházet z katalogu, ne od uživatele.

Proklik vyžaduje také argument `verified_product_ids_by_page`: slovník schválených slugů
na `set` nebo `frozenset` kladných celočíselných ID z odděleně ověřeného
katalogu partnera NaMaximum, filtrovaného pro daného poradce.
Například pro katalog obsahující ID 392 volající předá
`verified_product_ids_by_page={"xfit-os-kreatin-poradce": frozenset({392})}`.
Jde pouze o příklad volání, nikoli
doklad aktuální nabídky. Chybějící seznam, neznámé ID i neplatné položky se
odmítnou. ID ověřené pouze pro druhého poradce se také odmítne; tím se
brání připsání chybně označeného produktového tlačítka jinému poradci.
Jde o změnu offline rozhraní: původní společný set se nyní odmítá.
Slovník musí vzniknout z ověřeného výběru produktů pro každého poradce,
ne pouhým zkopírováním celého feedu pod oba slugy. Seznam se neposílá
v parametrech události. Nesmí se vytvářet ze
samotného kliknutí nebo vstupu uživatele; tím by ověření ztratilo význam.

Souhlas musí v budoucí integraci dodat consent manager; výchozí stav nic
nepřipraví. Jakékoli další pole se odmítne, včetně URL, odpovědí, zdravotních
údajů, e-mailu a affiliate parametrů. Chybové zprávy neobsahují vstupní hodnoty.
Volající nesmí při chybě poslat původní data ani je zapisovat do logu.

Příští krok: samostatně ověřit integraci s consent managerem a skutečnými
akcemi poradce, včetně cesty „nic nekoupit“. Dokončení poradce se má zaznamenat
i při této cestě a nesmí obsahovat zvolený výsledek. Proklik není objednávka
ani potvrzená provize; chybějící události nejsou důkazem nulové tržby.
Modul kontroluje členství ID v dodaném katalogu; sám neověřuje jeho původ,
aktuálnost, skladovou dostupnost, affiliate atribuci ani deduplikaci.
Budoucí transport musí samostatně omezit automatická metadata (URL, referrer,
identifikátory); validátor kontroluje pouze zde sestavené parametry.

`summarize_funnel(events, analytics_consent=True, verified_product_ids_by_page=...)`
lokálně shrne pozorované události ve formátu `{"name": ..., "params": ...}`.
Každý záznam znovu ověří stejnou validační hranicí; při neplatném záznamu
odmítne celý souhrn. Bez výslovného souhlasu ani nezačne číst vstup.
`action_counts` obsahuje počty akcí odděleně pro oba poradce, včetně nulových
počtů. Dokončení bez nákupu má stejnou váhu jako jiné dokončení. Opakované
prokliky se počítají jednotlivě: nejde o unikátní lidi, spárované návštěvy ani
konverzní poměr. Nula znamená pouze žádnou takovou akci v dodaných záznamech;
nepotvrzuje funkční měření. `unique_visitors`, `orders` a `commission` vždy
vracejí `UNKNOWN`. Souhrn neobsahuje produktová ID a nic neodesílá ani neukládá.
Před použitím pro rozhodování je nutné ověřit úplnost a období vstupu i
skutečnou integraci; tento nástroj je sám nedokládá.

`action_data_status` výslovně rozlišuje dostupnost záznamů pro každého poradce:
`UNKNOWN` znamená, že vstup neobsahoval žádnou jeho akci; `OBSERVED_ACTIONS`
znamená alespoň jednu ověřenou vstupní akci, včetně dokončení bez nákupu.
Ani tento stav nepotvrzuje úplnost měření nebo skutečný původ vstupu.
Poradce s `UNKNOWN` nelze podle nulových počtů označit za neúspěšný ani podle
toho upřednostnit komerční nabídky. Stavy neobsahují odpovědi ani výsledek volby.

`action_observation_status` navíc uvádí stejný stav pro každou akci každého
poradce. Samotný proklik tedy označí jako `OBSERVED_ACTIONS` pouze
`affiliate_outbound_click`; start i dokončení zůstanou `UNKNOWN`, pokud pro ně
nejsou záznamy. Chybějící dokončení nelze vydávat za odchod čtenáře ani za
neúspěch cesty „nic nekoupit“. Před změnou doporučení nebo nákupních tlačítek
je potřeba ověřit měření chybějícího kroku. Ani kladný počet nedokládá úplnost
měření; nové stavy nepřidávají identifikátory ani výsledek volby.

Ověření: `python -m unittest tests.test_revenue_events tests.test_agent_scope`.
Stav: připraveno lokálně; CI, nasazení, veřejná stránka a měření neověřeny.
Prokliky/objednávky/provize: UNKNOWN. Vrácení této úpravy: vrátit diff těchto
tří souborů; žádná existující integrace se na ně zatím neodkazuje.

## CTA identifikace a první webový adaptér — 2026-11-07

`scripts/xfit_click_metadata.py` vkládá do obou produktových srovnávačů tři **necitlivé** `data-xfit-*` atributy: `engine`, `partner=namaximum` a skutečné kladné numerické katalogové `product_id`. Identifikátor pochází z ověřeného produktového feedu. Nevalidní/mimo rozsah → fail-closed před publikací. Nikdy do atributů nevkládat affiliate `a_aid`/`a_bid`, URL ani zdravotní údaje. Výsledek publikace vždy ověřit v WP REST i na veřejné stránce; samotný commit nestačí.

`assets/analytics/xfit-outbound.js` je **připravený první-party browser adaptér**, nikoli automaticky instalovaný WordPress plugin. Zachytí pouze skutečné uživatelské kliknutí na označené produktové tlačítko v jednom ze dvou schválených poradců, ověří partnera/destinaci/affiliate parametry a odešle do `gtag` událost `affiliate_outbound_click` výhradně po návratu `true` z `window.xfitGetAnalyticsConsent()`. Tato funkce **musí** být připojena ke skutečně ověřenému cookie consent manageru. **Nedefinovat ji pomocí odhadu z cookie, permanentního `true` ani předem zatrženého souhlasu.** Bez této funkce, bez `gtag` nebo bez souhlasu modul zcela mlčí. Nemanipuluje s navigací a neposílá URL ani odpovědi z poradce. Zařízení a GA4 mohou vytvářet své vlastní automatické metadatové parametry; tento adaptér nezaručuje obecnou anonymitu GA4.

**Nasazení adaptéru dosud nepotvrzeno.** Potřebujeme ověřenou cestu nahrání externího JS přes hosting / WP theme enqueue a skutečné napojení CMP + GA4. Nevkládat JavaScript do editoru jako `<script>` ani `onclick`; to obchází publikovací standardy a může být odstraněno WordPressem. Bez ověřené integrace nenazývat `affiliate_outbound_click` měřeným. Před ostrým nasazením prověřit při zamítnutém i uděleném consentu, zda událost skutečně odchází, zda nemá URL/tajné hodnoty a zda je vidět v GA4 DebugView. Testovací kliky nejsou provize.

Testy: `python -m unittest discover -s tests -v` a `node --test tests/test_outbound_analytics.cjs`. V budoucím analytickém statusu vždy odlišovat `instrumentation_code_ready`, `html_metadata_public_verified`, `consent_bridge_verified`, `ga4_event_observed`, `affial_order_or_commission_observed`. První úspěšný CI test prokazuje pouze první položku.
