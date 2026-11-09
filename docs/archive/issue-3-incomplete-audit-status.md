# Issue #3 — neúplný audit nesmí hlásit úspěch

Připraveno lokálně 2026-11-08. Reprodukce z kódu a syntetických testů:
krátká odpověď API přebila hlavičku s počtem dalších stránek a označila
audit jako úplný. Při vyčerpání nastaveného limitu stránek navíc program
vracel úspěšný návratový kód i s `complete: false`.

Krátká odpověď nyní nepotvrzuje úplnost, pokud deklarovaný počet stránek
dosud nebyl dosažen. Neúplný audit zachová částečný report a vrátí kód 2.
Krátká odpověď bez metadat i plná poslední deklarovaná stránka zůstávají
podporovány. To pomáhá zabránit úklidu na základě neúplného přehledu
užitečných fitness článků a jejich odkazů na poradenství či produkty.
Audit sám stále neopravňuje k odstranění URL; nejde o atomický snapshot.

Ověření: `python -m unittest tests.test_archive_full` — 15 testů prošlo,
včetně čtyř variant úplnosti a návratového kódu s nahrazeným načítáním.
Archivní scope gate a `git diff --check` prošly. Žádné síťové požadavky,
sken archivu, změny wave01, WP ani publikování. Mobilní QA neprovedeno:
patch mění pouze místní auditní nástroj, nikoli vykreslení stránky.
Úplný audit a živé detaily issue #3 nejsou v checkoutu dostupné.

Stav: připraveno; lokální testy prošly; CI UNKNOWN; nasazení WP API
a veřejné ověření neprovedeno; kliknutí, objednávky a dopad UNKNOWN.
Rollback: vrátit tento patch. Další krok: nezávislá validace diffu a PR;
spotřebitelé auditu musí respektovat neúplnost a návratový kód 2.
