# Issue #3 — odkazy v neaktivních šablonách

Připraveno lokálně 2026-11-17. Syntetický regresní případ ukazuje,
že auditor dříve započítal odkazy uvnitř HTML `template` jako interní
navigaci i externí spam. Nejde o potvrzený nález na živém článku.

Parser nyní vynechává odkazy uvnitř šablon včetně vnořených šablon
a zachovává odkazy za nimi. Nemění přesný HTML hash ani WordPress.
Nejde o prohlížečový test viditelnosti; CSS a JavaScript se nevyhodnocují.
Přínosem jsou přesnější podklady pro zachování užitečných fitness rad
a kontrolu skutečných odkazů před monetizací. Samotný příznak spamu
nebo počet odkazů neopravňuje ke smazání či přesměrování článku.

Ověření: `python -m unittest tests.test_archive_full -q` — 29 testů OK;
`python -m unittest discover -s tests -q` — 607 testů OK.
Úplný audit a aktuální živé detaily issue #3 nejsou v checkoutu dostupné.
Archiv se neskenoval, web se neprocházel a wave01 se neměnila.

Stav: připraveno, lokální testy prošly; CI UNKNOWN; WP API nenasazeno;
veřejná stránka neověřována; měřené kliknutí/objednávka UNKNOWN.
Rollback: vrátit tento patch tří souborů; stav WP se nemění.
Další krok: nezávislá kontrola diffu a vytvoření PR.
