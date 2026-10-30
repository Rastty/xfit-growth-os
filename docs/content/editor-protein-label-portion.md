# Issue #4: převod prášku na bílkoviny

Záměr vstupní URL `/xfit-os-protein-guide/` (WP 25451): pomoci vybrat
protein podle potřeby, etikety a ceny. Místní podklad vysvětluje cenu
za skutečné bílkoviny, ale neukazuje převod chybějících bílkovin na gramy
prášku. Čtenář tak může zaměnit hmotnost odměrky za množství bílkovin.

Návrh doplňuje stávající cenovou sekci; nevytváří další URL. Obsahuje
početní příklad, přednost běžného jídla, možnost nekoupit nic a zákaz
odhadu při chybějící etiketě. Pomáhá posoudit nákup před přechodem do
stávajícího srovnání. Nemění pořadí produktů ani affiliate odkazy.

Podklad: lokální `content/ready/xfit-os-protein-guide.json`. Revize ukládá
ID, slug, SHA-256 souboru i obsahu a původní nahrazovaný fragment.
Nový výpočet je aritmetika, nikoli klinické doporučení. Dosavadní odborné
zdroje článku zůstávají zachovány; nebyly znovu ověřeny na webu.
Vzdálené znění issue #4 ani živý obsah nebyly načteny.

Ověření: `python -m unittest tests.test_editor_protein_label_portion tests.test_editorial_gate`
a `python scripts/xfit_agent_scope.py --lane editor`.
Test sestaví pouze náhled v paměti, ověří editorial gate, identitu zdroje,
početní příklad a přesnou vratnost změny. Mobilní Chrome QA neprovedeno.

Stav: připravený návrh; CI, nasazení, veřejná kontrola a měřené kliky či
objednávky UNKNOWN. Nic nebylo publikováno. Před případným vydáním musí
navazující fáze načíst a zálohovat skutečný WP obsah, porovnat jej s
podkladem a provést mobilní QA. Při odlišném obsahu návrh automaticky
neaplikovat. Návrat lokálního náhledu: nahradit přesně jednou `replacement`
za `original`; návrat případné budoucí WP změny vyžaduje skutečnou zálohu.
