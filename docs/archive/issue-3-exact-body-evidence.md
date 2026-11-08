# Issue #3 — přesné kopie musí zachovat odkazy a obrázky

Připraveno lokálně 2026-11-08. Dosavadní hash vznikal z textu bez HTML
převedeného na malá písmena. Dva články se stejným textem, ale různými
odkazy na zdroje či produkty tak dostaly označení přesné kopie. Jde o
reprodukci z kódu a syntetických testů, nikoli o doložené živé URL.

Hash nyní porovnává původní HTML včetně odkazů, obrázků a velikosti písmen.
Shodné nadpisy zůstávají samostatným signálem k posouzení. Konzervativní
porovnání může přehlédnout obsahově stejné články s rozdílným formátováním;
pomáhá však uchovat odlišné čtenářské cesty k podkladům a produktům před
chybným úklidem. Žádný nález sám neopravňuje k odstranění článku.

Ověření: `python -m unittest tests.test_archive_full` — 14 testů prošlo.
Regrese pokrývají odlišné odkazy, obrázky a velikost písmen i skutečně
shodné HTML. Kontrola archivního rozsahu a `git diff --check` prošly.
Žádné síťové požadavky, sken archivu, změny WP ani změny wave01.
Mobilní QA neprovedeno; patch mění pouze lokální auditní evidenci.
Úplný audit a živé detaily issue #3 nejsou v checkoutu dostupné.

Stav: připraveno; lokální testy prošly; CI UNKNOWN; nasazení WP API
a veřejné ověření neprovedeno; kliknutí, objednávky a dopad UNKNOWN.
Rollback: vrátit tento patch. Starší textové hashe nelze přímo porovnávat
s novými HTML hashi. Další krok: nezávislá validace diffu a vytvoření PR;
před budoucím úklidem stále ověřit návštěvnost, příchozí odkazy a zálohu.
