# Issue #3 — vyřazené ID znamená neúplné podklady

Připraveno lokálně 2026-11-09. Audit zahazoval záznamy bez kladného
celočíselného ID, ale mohl nadále hlásit `complete: true` a úspěšný
návratový kód. Python navíc přijímal `true` jako ID 1. Jde o reprodukci
z místního kódu, nikoli o doloženou chybu živého API.

Report i konzolový souhrn nyní uvádějí `invalid_post_id_count`. Jakýkoli
vyřazený záznam zabrání označení úplnosti a program vrátí kód 2;
platné záznamy zůstanou v částečném reportu. Boolean není platné ID.
Spolehlivější podklady pomáhají chránit užitečné fitness články a jejich
odkazy na transparentní produktové poradenství před chybným úklidem.
Samotný audit stále neopravňuje k odstranění URL.

Ověření: `python -m unittest tests.test_archive_full` — 16 testů prošlo.
Nová regrese pokrývá chybějící, nulové, záporné, textové i boolean ID
na jinak úplné stránce, zachování platného článku a konzolový souhrn.
Archivní scope gate a `git diff --check` prošly. Síť byla v testech
nahrazena; žádné požadavky na xfit.cz ani sken archivu neproběhly.
Mobilní QA neprovedeno: změna neovlivňuje vykreslení webu.
Úplný audit a živé detaily issue #3 nejsou v checkoutu dostupné.

Stav: připraveno; lokální testy prošly; CI UNKNOWN; nasazení WP API
a veřejné ověření neprovedeno; kliknutí, objednávky a dopad UNKNOWN.
Žádné změny wave01, publikování ani změny WordPressu.
Rollback: vrátit tento patch. Další krok: nezávislá validace diffu a PR;
budoucí spotřebitel auditu musí respektovat neúplnost a návratový kód 2.
