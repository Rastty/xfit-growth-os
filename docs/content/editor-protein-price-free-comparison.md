# Issue #4: cenové srovnání bez smyšlených cen

Audit záměru: `/xfit-os-protein-guide/`, WP 25451, pomáhá vybrat protein
podle potřeby a rozpočtu. Lokální článek již vysvětluje cenu za bílkoviny,
ale tabulka používá ilustrační ceny, které nejsou ověřenými nabídkami.
Návrh nahrazuje pouze tuto tabulku a její vysvětlivku. Nevytváří další URL.

Modelové hmotnosti a koncentrace zůstávají výslovně hypotetické. Z nich
plyne 648 a 800 g bílkovin a přesný cenový práh 800/648. Zaokrouhlených
23,5 % je pouze vysvětlení rozdílu; rozhodovací vzorec používá přesný poměr.
Čtenář dosadí skutečné ceny, posoudí dopravu a omezení srovnání nebo nic
nekoupí. Nejde o nový klinický claim; důkazem je aritmetika. Existující
odkazy, zdroje a cesta k affiliate srovnání zůstávají zachovány.

Revize uchovává ID, slug, SHA-256 lokálního souboru i obsahu a přesný
nahrazovaný fragment. Test odmítne změněný podklad, sestaví náhled pouze
v paměti, spustí editorial gate a ověří vratnost i matematickou hranici.
Rollback návrhu: odstranit revizi; rollback náhledu: nahradit přesně jednou
`replacement` za `original`. Před budoucím vydáním je nutná vlastní záloha
skutečného WP obsahu a kontrola shody; návrh není publikační oprávnění.

Ověření: `python -m unittest tests.test_editor_protein_price_free_comparison
tests.test_editor_protein_equal_portions tests.test_editor_protein_label_portion
tests.test_editorial_gate` a `python scripts/xfit_agent_scope.py --lane editor`.

Připraveno jako návrh. CI UNKNOWN; WP nenasazeno; veřejná stránka ani
mobilní Chrome QA neověřeny; kliky/objednávky UNKNOWN. Vzdálené issue #4,
web ani produkční endpointy nebyly načteny. Další fáze má ověřit diff a
mobilní náhled před případným vydáním.
