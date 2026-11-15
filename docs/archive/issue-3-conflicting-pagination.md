# Issue #3 — rozporné verze článku během stránkování

Připraveno lokálně 2026-11-10. Audit dříve ponechal první výskyt ID
a ignoroval další verzi i při změně obsahu nebo URL. Mohl přitom hlásit
`complete: true`. Reprodukce je syntetická; postižené živé URL nejsou známy.

Audit nyní porovnává opakované záznamy všech načtených polí. Rozdílné
verze zachovají první záznam pro částečný report, ale nastaví neúplnost
a návratový kód 2. Report i stručný výstup uvádějí počet konfliktních ID;
report přidává vzorek nejvýše 30 ID. Shodné opakování zůstává podporováno.
Počet konfliktů vyjadřuje články, nikoli počet jejich opakovaných verzí.

Přínos: podklady pro úklid nezamlčí změněné fitness návody, zdroje či
produktové odkazy. To podporuje ochranu užitečných cest čtenáře před
rozhodováním podle zastaralé verze. Nejde o atomický snapshot ani povolení
k odstranění článku. Dopad na návštěvnost a monetizaci je UNKNOWN.

Ověření: `python -m unittest tests.test_archive_full` — 20 testů prošlo.
Regrese pokrývají změnu odkazu v obsahu, permalinku a času změny,
shodné opakování, jedinečnost počtu konfliktů a návratový kód/report.
Archivní scope gate a `git diff --check` prošly.
Úplný audit a živé detaily issue #3 nejsou v checkoutu dostupné.
Žádné síťové požadavky, sken archivu, změny WP ani mobilní QA;
patch mění pouze místní auditní nástroj.

Stav: připraveno a lokálně otestováno; CI UNKNOWN; nasazení WP API
a ověření veřejné stránky neprovedeno; kliknutí/objednávky UNKNOWN.
Rollback: vrátit tento tří-souborový patch, žádný stav WP se nezměnil.
Další krok: nezávislá validace diffu a vytvoření PR. Spotřebitelé reportu
musí respektovat neúplnost; skutečný úklid nadále vyžaduje traffic/index
evidenci, kontrolu odkazů a zálohu pro rollback.
