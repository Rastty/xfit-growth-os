# Issue #5: bezpečné parametry událostí

`scripts/xfit_revenue_events.py` je offline validační hranice pro budoucí
měření dvou existujících poradců. Nic neodesílá, neukládá a nemění GA4.
Pomáhá připravit měření užitečnosti poradce a prokliků bez sběru jeho odpovědí.

`build_event(name, fields, analytics_consent=True)` připraví pouze:

- `advisor_start` a `advisor_complete`: schválený slug stránky a odpovídající
  `selection_engine` (`creatine` nebo `whey`).
- `affiliate_outbound_click`: navíc `partner=namaximum` a kladné celočíselné
  katalogové `product_id`. Identifikátor musí pocházet z katalogu, ne od uživatele.

Proklik vyžaduje také argument `verified_product_ids`: `set` nebo `frozenset`
kladných celočíselných ID z odděleně ověřeného katalogu partnera NaMaximum.
Například pro katalog obsahující ID 392 volající předá
`verified_product_ids=frozenset({392})`. Jde pouze o příklad volání, nikoli
doklad aktuální nabídky. Chybějící seznam, neznámé ID i neplatné položky se
odmítnou. Seznam se neposílá v parametrech události. Nesmí se vytvářet ze
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

`summarize_funnel(events, analytics_consent=True, verified_product_ids=...)`
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

Ověření: `python -m unittest tests.test_revenue_events tests.test_agent_scope`.
Stav: připraveno lokálně; CI, nasazení, veřejná stránka a měření neověřeny.
Prokliky/objednávky/provize: UNKNOWN. Vrácení této úpravy: vrátit diff těchto
tří souborů; žádná existující integrace se na ně zatím neodkazuje.
