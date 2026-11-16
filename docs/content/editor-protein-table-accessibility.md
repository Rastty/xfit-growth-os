# Issue #4: přístupná rozhodovací tabulka proteinů

Záměr existující URL `/xfit-os-protein-guide/` (WP 25451): vybrat typ
proteinu podle potřeby, omezení a rozpočtu, případně nic nekoupit.
Lokální podklad má v úvodní tabulce tři sloupce a pět možností, ale
první buňky řádků nejsou označené jako záhlaví a tabulka nemá popisek.

Návrh přidává `caption`, `scope="col"` a `scope="row"`, aby čtečky
obrazovky mohly spojit možnosti s potřebou čtenáře a příslušným sloupcem.
Popisek vysvětluje, že jde o rozhodovací pomůcku, nikoli produktový žebříček.
Všechny původní buňky, doporučení, zdroje, možnost nekoupit a odkazy zůstávají
zachované. Nevzniká nová URL ani nové zdravotní či obchodní tvrzení.

Podklad je pouze místní ready soubor čtený bez úprav; návrh ukládá jeho
SHA-256, SHA-256 obsahu, WP ID, slug a přesný původní fragment. Vzdálené
issue, Actions, živá stránka ani webové zdroje nebyly načteny.

Ověření: cílený unittest pro tento návrh a editorial gate v paměťovém
náhledu, úplná sada unittest a ownership gate editorovy role. Test porovnává
text všech 18 buněk i odkazy a ověřuje záhlaví, popisek a přesnou vratnost.
Mobilní Chrome a skutečná čtečka obrazovky nebyly ověřeny; navazující fáze
musí zkontrolovat vykreslení záhlaví řádků tématem při šířce 375 px.

Stav: připravený lokální návrh. CI, WP nasazení a veřejná kontrola neprovedeny;
měřený přínos pro kliky/objednávky UNKNOWN. Před vydáním porovnat skutečný
WP obsah a pořídit zálohu; při rozdílu návrh automaticky neaplikovat.
Rollback náhledu: nahradit přesně jednou `replacement` za `original`.
Budoucí produkční rollback vyžaduje skutečnou předchozí WP zálohu.
