# Issue #4: cena bílkovin v průvodci pro začátečníky

Audit záměru: `/xfit-os-doplnky-pro-zacatecniky/` (WP 25458) pomáhá
začátečníkům rozhodnout, co potřebují a za co neutrácet. Místní podklad
v části o rozpočtu používá hypotetickou cenu proteinu. Jediná změna
nahrazuje tento rozbalovací blok postupem použitelným se skutečnou
etiketou a cenou konkrétní varianty, bez nových modelových cen.

Zůstává početní příklad 900 × 75 / 100 = 675 g bílkovin. Nový postup
rozlišuje prášek od nápoje s mlékem, zahrnuje dopravu při srovnání
samostatných objednávek jednoho balení a odmítá odhad bez etikety.
Uvádí možnost nic nekoupit a hranice výpočtu. Podkladem je aritmetika
a existující místní proteinový průvodce, nikoli nové zdravotní tvrzení.
Odkazy, affiliate vztahy a ostatní obsah se nemění.

Revize uchovává ID, slug, SHA-256 souboru i obsahu a přesný původní blok.
Test vyžaduje shodu podkladu, ověřuje výpočet, editorial gate, zachování
odkazů a přesný rollback náhledu. Náhled vzniká pouze v paměti.
Rollback návrhu: odstranit revizi. Rollback náhledu: nahradit jednou
`replacement` za `original`. Případné vydání potřebuje aktuální WP zálohu
a ověření shody; návrh sám publikaci neopravňuje.

Ověření: `python -m unittest tests.test_editor_beginner_protein_cost tests.test_editorial_gate`
a `python scripts/xfit_agent_scope.py --lane editor`.

Stav: připraveno; CI UNKNOWN; WP nenasazeno; veřejná stránka a mobilní
Chrome QA neověřeny; kliky/objednávky UNKNOWN. Web, vzdálené issue #4,
PR ani Actions nebyly načteny. Další fáze má ověřit diff a mobilní náhled.
