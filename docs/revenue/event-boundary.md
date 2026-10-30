# Issue #5: bezpečné parametry událostí

`scripts/xfit_revenue_events.py` je offline validační hranice pro budoucí
měření dvou existujících poradců. Nic neodesílá, neukládá a nemění GA4.
Pomáhá připravit měření užitečnosti poradce a prokliků bez sběru jeho odpovědí.

`build_event(name, fields, analytics_consent=True)` připraví pouze:

- `advisor_start` a `advisor_complete`: schválený slug stránky a odpovídající
  `selection_engine` (`creatine` nebo `whey`).
- `affiliate_outbound_click`: navíc `partner=namaximum` a kladné celočíselné
  katalogové `product_id`. Identifikátor musí pocházet z katalogu, ne od uživatele.

Souhlas musí v budoucí integraci dodat consent manager; výchozí stav nic
nepřipraví. Jakékoli další pole se odmítne, včetně URL, odpovědí, zdravotních
údajů, e-mailu a affiliate parametrů. Chybové zprávy neobsahují vstupní hodnoty.
Volající nesmí při chybě poslat původní data ani je zapisovat do logu.

Příští krok: samostatně ověřit integraci s consent managerem a skutečnými
akcemi poradce, včetně cesty „nic nekoupit“. Dokončení poradce se má zaznamenat
i při této cestě a nesmí obsahovat zvolený výsledek. Proklik není objednávka
ani potvrzená provize; chybějící události nejsou důkazem nulové tržby.
Tento modul neověřuje existenci produktu, affiliate atribuci ani deduplikaci.
Budoucí transport musí samostatně omezit automatická metadata (URL, referrer,
identifikátory); validátor kontroluje pouze zde sestavené parametry.

Ověření: `python -m unittest tests.test_revenue_events tests.test_agent_scope`.
Stav: připraveno lokálně; CI, nasazení, veřejná stránka a měření neověřeny.
Prokliky/objednávky/provize: UNKNOWN. Vrácení změny: odstranit tyto tři soubory;
žádná existující integrace se na ně zatím neodkazuje.
