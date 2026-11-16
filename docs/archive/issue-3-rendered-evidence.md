# Issue #3 — chybějící obsah není prázdný článek

Připraveno lokálně 2026-11-15. Syntetická regrese prokázala, že chybějící
`rendered` nebo hodnota `null` v titulku či obsahu mohly vést k úplnému
reportu a falešnému označení krátkého článku. Některé jiné typy hodnot
ukončily běh výjimkou bez reportu. Výskyt na živém webu je UNKNOWN.

Audit nyní před přijetím stránky ověřuje řetězce `title.rendered`
a `content.rendered` u všech záznamů. Při chybě zachová předchozí stránky,
označí report jako neúplný a vrátí kód 2. Skutečně prázdné řetězce
zůstávají platným podkladem. Oprava chrání užitečné fitness návody,
zdroje a produktové cesty před úklidem podle neúplné odpovědi API;
neopravňuje k odstranění žádné URL.

Ověření: nová regrese před opravou selhala; po opravě prošlo
`python -m unittest tests.test_archive_full -q` (24 testů) a
`python -m unittest discover -s tests -q` (560 testů).
Úplný audit ani živý stav issue #3 nejsou v checkoutu dostupné.
Žádný sken archivu, webové procházení, nasazení ani mobilní QA.

Stav: připraveno a lokálně otestováno; CI UNKNOWN; WP API nenasazeno;
veřejná stránka neověřována; měřené kliknutí/objednávka UNKNOWN.
Rollback: vrátit tento patch; stav WP se nemění.
Další krok: nezávisle ověřit diff a vytvořit PR.
