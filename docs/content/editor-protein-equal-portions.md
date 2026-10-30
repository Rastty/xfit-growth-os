# Issue #4: srovnatelná cena za porci bílkovin

Audit záměru: `/xfit-os-protein-guide/`, WP 25451, pomáhá vybrat protein
podle potřeby, etikety a rozpočtu. Lokální podklad vysvětluje cenu za
100 g bílkovin i převod prášku na bílkoviny. Neupozorňuje však přímo na
nesrovnatelné prodejní ceny „za porci“ při odlišných velikostech porcí.

Jediná změna: dva odstavce propojují tyto výpočty pro srovnání nákladů
na stejné množství bílkovin. Příklad používá pouze hmotnosti a podíly,
žádné ceny ani reálné produkty. Výpočet neurčuje vhodnou dávku či
kvalitu výrobku. Čtenář může odmítnout zdánlivě levnější nabídku nebo
nekoupit nic, pokud příjem pokryje jídlem. Affiliate odkazy a pořadí
produktů se nemění. Nejde o nový klinický claim; důkazem je aritmetika.

Revize uchovává ID, slug, SHA-256 místního souboru i obsahu a přesný
nahrazovaný fragment. Test vyžaduje shodu zdroje, jediný výskyt cíle,
editorial gate náhledu a přesnou vratnost. Náhled vzniká pouze v paměti.
Rollback návrhu: odstranit tuto revizi; rollback náhledu: nahradit jednou
`replacement` za `original`. Případná budoucí publikace vyžaduje vlastní
zálohu skutečného WP obsahu a kontrolu shody, nikoli slepé použití návrhu.

Lokální ověření:
`python -m unittest tests.test_editor_protein_equal_portions tests.test_editor_protein_label_portion tests.test_editorial_gate`
a `python scripts/xfit_agent_scope.py --lane editor`.

Připraveno jako návrh. CI UNKNOWN; WP nenasazeno; veřejná stránka
neověřena; měřené kliky/objednávky UNKNOWN. Web, vzdálené issue #4,
analytika ani produkční endpointy nebyly načteny. Mobilní Chrome QA
neprovedeno; navazující fáze musí ověřit náhled na mobilu před vydáním.
