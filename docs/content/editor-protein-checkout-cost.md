# Issue #4: porovnání ceny včetně dopravy

Audit záměru: `/xfit-os-protein-guide/`, WP 25451, pomáhá vybrat protein
podle potřeby, etikety a rozpočtu. Místní podklad počítá cenu za bílkoviny,
ale dopravu uvádí zvlášť bez postupu. Při nákupu jediného balení může
doprava obrátit pořadí výhodnosti nabídek.

Jediná změna: odstavec u stávajícího vzorce vysvětluje použití skutečné
částky z košíku včetně dopravy a povinných poplatků po slevách. Rozlišuje
samostatné objednávky jednoho balení a smíšené košíky, kde nelze celou
dopravu přičíst každému produktu. Odrazuje od nepotřebných doplňků kvůli
dopravě zdarma a zachovává možnost nic nekupovat. Bez nových cen,
produktů, klinických tvrzení či affiliate odkazů; podkladem je aritmetika.

Revize uchovává ID, slug, SHA-256 souboru i obsahu a přesný fragment.
Test vyžaduje nezměněný podklad, sestaví náhled pouze v paměti, prověří
editorial gate, zachování odkazů a přesnou vratnost. Početní test ukazuje
obrácení pořadí při započtení dopravy na bezrozměrných poměrech.
Rollback návrhu: odstranit revizi. Rollback náhledu: jednou nahradit
`replacement` za `original`. Budoucí vydání vyžaduje zálohu skutečného WP
obsahu a kontrolu shody; tento návrh publikaci neopravňuje.

Ověření: `python -m unittest tests.test_editor_protein_checkout_cost tests.test_editorial_gate`
a `python scripts/xfit_agent_scope.py --lane editor`.

Stav: připraveno; CI UNKNOWN; WP nenasazeno; veřejná stránka a mobilní
Chrome QA neověřeny; kliky a objednávky UNKNOWN. Vzdálené issue #4 ani web
nebyly načteny. Další fáze má ověřit diff a mobilní náhled před vydáním.
