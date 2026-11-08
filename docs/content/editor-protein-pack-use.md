# Issue #4: využijete velké balení proteinu?

Audit záměru: `/xfit-os-protein-guide/` (WP 25451) pomáhá vybrat protein
podle potřeb a skutečných nákladů. Lokální podklad varuje před velkým
balením neznámé příchutě, ale neukazuje, jak odhadnout dobu spotřeby.
Revize nahrazuje tento jediný bod seznamu jednoduchým výpočtem porcí
a týdnů podle plánovaného používání. Čtenář může zvolit menší balení
nebo nekoupit nic místo nákupu pouze podle jednotkové ceny.

Podklad: pouze místní publikační JSON, bez webu a živých nabídek.
Model 1 000 g / 25 g / dvě použití týdně je aritmetika, nikoli výrobek,
dávkování nebo údaj o trvanlivosti. Tu je nutné ověřit na konkrétním
obalu včetně pokynů po otevření. Nevzniká klinické ani cenové tvrzení.
URL, odkazy, affiliate disclosure a nadpisy zůstávají zachované.

Revizní JSON uchovává ID, slug, SHA-256 podkladu a původní fragment.
Test ověřuje shodu snapshotu, editorial gate náhledu v paměti a přesný
rollback nahrazením `replacement` za `original`. Pro zrušení návrhu
odstraňte jeho JSON. Před případným vydáním je nutná záloha skutečného
WP obsahu a kontrola shody; tento návrh neopravňuje k publikaci.

Lokální ověření: `python -m unittest discover -s tests -p 'test_editor*.py'`
a `python scripts/xfit_agent_scope.py --lane editor`.

Připraveno jako návrh; CI UNKNOWN; WP nenasazeno; veřejná stránka ani
mobilní Chrome QA neověřeny; kliky/objednávky UNKNOWN. Vzdálené issue #4,
PR a Actions nebyly načteny. Další fáze nezávisle ověří diff a mobilní náhled.
