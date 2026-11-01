# Issue #3 — odmítnutá stránka není konec archivu

Připraveno lokálně 2026-10-31. Funkce `fetch` měnila libovolnou HTTP 400
od druhé stránky na úspěšnou prázdnou odpověď. `main` pak mohl označit
neúplný audit jako `complete`, i když API další stránku odmítlo.
Jde o reprodukci z místního kódu, nikoli o doložený incident na živém webu.

HTTP 400 nyní přeruší načítání a existující obsluha chyby zachová částečný
report s `complete: false`, číslem odmítnuté stránky a návratovým kódem 2.
Úspěšná prázdná odpověď API se nadále zpracovává beze změny.
Spolehlivější označení neúplných podkladů pomáhá chránit užitečné fitness
články i jejich návaznost na transparentní nákupní poradenství před chybným
úklidem. Samotný audit neopravňuje k odstranění žádné stránky.

Ověření: `python -m unittest tests.test_archive_full`,
`python scripts/xfit_agent_scope.py --lane archive`, `git diff --check`.
Testy nahrazují síťové odpovědi; ověřují odmítnutí stránky i zachování
částečného reportu. Žádné požadavky na xfit.cz, sken archivu ani změny WP.
Mobilní QA nebylo provedeno; změna neovlivňuje vykreslení webu.

Stav: připraveno; lokální testy ověřeny. CI UNKNOWN; nasazení WP API
a veřejné ověření neprovedeno; dopad na kliknutí, objednávky a výnos UNKNOWN.
Úplný audit a živé detaily issue #3 nejsou v checkoutu dostupné.
Rollback: vrátit tento patch. Další krok: nezávislá validace diffu a PR.
