# Issue #4: rozhodnutí před nákupem už v úvodu

Audit záměru `/xfit-os-protein-guide/` (WP 25451): čtenář chce vybrat
protein, zjistit, zda jej potřebuje, a nepřeplatit. Místní úvod popisuje
možnosti, ale konkrétní postup je až v dalších sekcích. Návrh nahrazuje
pouze první odstavec třemi větami: jídlo a možnost nic nekoupit → volba
podle omezení a alergenů → srovnatelná cena podle etikety. Nezakládá URL
ani další sekci. Podporuje informovaný nákup místo tlaku na proklik.

Podklad: místní `content/ready/xfit-os-protein-guide.json`, části 1–3
a postup čtení etikety. Žádné nové klinické tvrzení, produkt či cena.
Stávající odborné zdroje nebyly znovu ověřeny. Revize ukládá ID, slug,
SHA-256 souboru i obsahu a přesný původní odstavec. Nedotýká se
uzamčených revizí ani publikačních souborů.

Validace: `python -m unittest tests.test_editor_protein_first_screen -q`,
`python -m unittest discover -s tests -q` a
`python scripts/xfit_agent_scope.py --lane editor`.
Test ověřuje zdroj, pořadí rozhodovacích kroků, existenci cílových sekcí,
editorial gate, zachování zbytku článku a odkazů i přesnou vratnost.

Stav: připravený návrh, bez publikace. CI, WP nasazení, veřejná kontrola
a mobilní Chrome QA neověřeny; dopad na kliky/objednávky UNKNOWN.
Web ani vzdálené issue #4 nebyly načteny. Další fáze musí porovnat návrh
se zálohou skutečného WP obsahu a ověřit mobilní zobrazení; při neshodě
zdroje jej neaplikovat automaticky. Lokální rollback náhledu: přesně
jednou nahradit `replacement` za `original`; případná WP obnova ze zálohy.
