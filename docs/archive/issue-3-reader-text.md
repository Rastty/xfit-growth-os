# Issue #3 — délka článku bez skriptů a šablon

Připraveno lokálně 2026-11-16. Regrese před opravou prokázala, že
400 znaků ve script, style či template skryje krátký článek před příznakem
`suspect_thin`. Jde o syntetickou reprodukci, ne nález na živé URL.

Extrakce textu nyní používá HTML parser a vynechává komentáře, skripty,
styly a obsah template včetně vnořených šablon. Zachovává český text,
HTML entity a text následující za neaktivními prvky. Přesný HTML hash
stále zahrnuje celý původní obsah. Nejde o měření viditelnosti v prohlížeči:
CSS ani WordPress shortcodes se nevyhodnocují. Dřívější délky a počty
krátkých článků proto nemusejí být přímo srovnatelné.

Přínos: kontrola kvality fitness a produktových rad nebude považovat
technický balast za užitečné vysvětlení pro čtenáře. Krátkost sama stále
neopravňuje k odstranění článku; hodnotné stručné rady mohou zůstat.
Dopad na čtenáře, kliknutí a objednávky je UNKNOWN.

Ověření: cílená sada `python -m unittest tests.test_archive_full -q`
(27 testů) a úplná `python -m unittest discover -s tests -q` (565 testů).
Kontrola archivního rozsahu a `git diff --check` prošly.
Úplný audit a živé detaily issue #3 nejsou lokálně dostupné.
Žádný sken archivu, procházení webu, změny WP či wave01 ani mobilní QA.

Stav: připraveno a lokálně otestováno; CI UNKNOWN; WP API nenasazeno;
veřejná stránka neověřována; měřený obchodní dopad UNKNOWN.
Rollback: vrátit tento tří-souborový patch, stav WP se nemění.
Další krok: nezávislá validace diffu a vytvoření PR.
