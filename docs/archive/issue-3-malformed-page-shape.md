# Issue #3 — objekt JSON není konec archivu

Připraveno lokálně 2026-11-15. Audit přijímal odpověď bez kontroly,
že jde o seznam objektů článků. Prázdný JSON objekt `{}` na poslední
stránce tak mohl vést k `complete: true`; jiné vadné tvary mohly přerušit
program bez uložení částečného reportu. Reprodukce vychází z kódu
a syntetických testů, nikoli z pozorované odpovědi živého webu.

Audit nyní odmítne chybný tvar celé stránky před přidáním záznamů.
Zachová předchozí stránky, uvede číslo odmítnuté stránky a `ValueError`,
označí report jako neúplný a vrátí kód 2. Skutečný prázdný seznam
zůstává podporován. Nejde o úplnou validaci všech polí článku.

Přínos: podklady pro úklid nezamění chybnou odpověď za dokončený
přehled. To pomáhá chránit užitečné české fitness návody a jejich
cesty k transparentnímu produktovému poradenství. Samotný audit
neopravňuje k odstranění URL; dopad na čtenáře a monetizaci je UNKNOWN.

Ověření: `python -m unittest tests.test_archive_full` — 22 testů prošlo.
Nové regrese pokrývají objekt, null, řetězec, vadné položky seznamu,
zachování částečných dat a platný prázdný seznam. Síťové načítání je
nahrazeno v testech. Úplný audit ani živé detaily issue #3 nejsou lokálně
dostupné. Žádný sken archivu, síťové požadavky, změny WP ani wave01.
Mobilní QA neprovedeno: patch nemění vykreslení stránky.

Stav: připraveno a lokálně otestováno; CI UNKNOWN; nasazení WP API
a veřejné ověření neprovedeno; měřené kliknutí/objednávky UNKNOWN.
Rollback: vrátit tento tří-souborový patch; stav WordPressu se nezměnil.
Další krok: nezávislá validace diffu a vytvoření PR. Budoucí úklid
stále vyžaduje traffic/index evidenci, kontrolu odkazů a zálohu.
