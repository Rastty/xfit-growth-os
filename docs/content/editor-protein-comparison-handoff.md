# Issue #4: srozumitelný přechod k produktovému srovnání

Audit záměru: existující `/xfit-os-protein-guide/` (WP 25451) pomáhá
vybrat protein podle potřeb a skutečných nákladů. Lokální podklad rozlišuje
cenu prášku a bílkovin, ale nákupní odkaz pojmenovává jen „cenu a balení“.
Revize zpřesňuje přímo text odkazu a před nákupem vyžaduje kontrolu etikety,
přepočet podle části 3, dopravu a alergeny. Chybějící složení je důvod
vyžádat si etiketu, nikoli odhadovat výhodnost. Zachovává možnost nic
nekoupit i affiliate disclosure. Nepřidává URL, nabídky ani klinické tvrzení.

Podkladem je pouze místní publikační JSON; žádné ověření živých nabídek.
Revize uchovává ID, slug, SHA-256 souboru i obsahu a původní fragment.
Test kontroluje shodu podkladu, editorial gate náhledu v paměti, zachování
odkazů a přesný rollback. Rollback návrhu: odstranit nový revizní JSON;
rollback náhledu: jednou nahradit `replacement` za `original`.
Před případným vydáním je nutná záloha skutečného WP obsahu a kontrola shody.

Lokální ověření: `python -m unittest tests.test_editor_protein_comparison_handoff
tests.test_editor_protein_price_free_comparison tests.test_editor_protein_equal_portions
tests.test_editor_protein_label_portion tests.test_editorial_gate`
a `python scripts/xfit_agent_scope.py --lane editor`.

Připraveno jako návrh; CI UNKNOWN; WP nenasazeno; veřejná stránka a mobilní
Chrome QA neověřeny; kliky/objednávky UNKNOWN. Web, vzdálené issue #4,
PR ani Actions nebyly načteny. Další fáze má ověřit diff a mobilní náhled;
tento návrh neopravňuje k publikaci.
