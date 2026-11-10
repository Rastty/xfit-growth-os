# Issue #4: možnost nekoupit protein přímo v rychlé volbě

Audit záměru `/xfit-os-protein-guide/` (WP 25451): čtenář vybírá, zda
a jaký protein potřebuje. Místní podklad nabízí v rychlé tabulce pouze
produktové možnosti; cestu bez nákupu vysvětluje mimo ni. Revize přidává
jako první rozhodovací řádek možnost nepoužít doplněk, když bílkoviny
pokryje běžné jídlo. Odkazuje slovně na existující část 1 s postupem.
Nevytváří další článek ani nová zdravotní tvrzení. Podporuje rozhodnutí
před cenovým a affiliate srovnáním bez tlaku na zbytečný nákup.

Podklad je pouze místní publikační JSON. Revize uchovává ID, slug,
SHA-256 souboru i obsahu a přesný původní fragment. Vzdálené issue #4,
PR, Actions ani web nebyly načteny. Odborné zdroje nebyly znovu ověřeny.

Ověření: `python -m unittest tests.test_editor_protein_table_opt_out
tests.test_editorial_gate` a `python scripts/xfit_agent_scope.py --lane editor`.
Test kontroluje identitu podkladu, editorial gate náhledu, první volbu
bez doplňku, tři buňky řádku, zachování ostatních řádků a odkazů i rollback.
Rollback náhledu: jednou nahradit `replacement` za `original`.

Stav: připravený návrh; CI UNKNOWN; WP nenasazeno; veřejná kontrola
a mobilní Chrome QA neprovedeny; měřené kliky/objednávky UNKNOWN.
Další fáze má nezávisle validovat diff a mobilní náhled. Před případným
vydáním je nutná záloha skutečného WP obsahu a kontrola jeho shody;
při odlišném podkladu návrh automaticky neaplikovat.
