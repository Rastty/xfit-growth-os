# Issue #4: náklady na kreatin bez smyšlené ceny

Audit záměru `/xfit-os-doplnky-pro-zacatecniky/`: začátečník má rozhodnout,
zda doplněk vůbec potřebuje a jak posoudit náklady. Místní zdroj v rozpočtové
sekci používá hypotetickou cenu kreatinu a denní náklad. Návrh nahrazuje
pouze tento blok postupem podle skutečné ceny a etikety, bez další URL.

Příklad 500 ÷ 3 rozlišuje 166 celých porcí a zbytek 2 g. Vzorec ceny
poměrně rozpočítává celý obsah. Jde o aritmetiku, nikoli doporučenou dávku,
klinický claim nebo nabídku. U směsí nelze zaměnit hmotnost prášku za kreatin.
Možnost nic nekoupit zůstává přímo u rozhodnutí. Přínos monetizaci spočívá
v transparentním posouzení nákupu; nové affiliate odkazy ani pořadí nevznikají.

Revize uchovává slug, SHA-256 souboru i obsahu a přesný původní fragment.
Lokální zdroj nemá WP ID; dokumentace uvádí průvodce jako WP 25458,
ale před případným vydáním je nutné ověřit skutečnou identitu a obsah,
zálohovat jej a při neshodě návrh neaplikovat. Návrat náhledu: přesně jednou
nahradit `replacement` za `original`. Návrat budoucí WP změny vyžaduje zálohu.

Ověření: cílené unittest testy náhledu, identity, vratnosti, početního příkladu
a editorial gate; dále kompletní unittest sada a kontrola editor scope.
Náhled vzniká pouze v paměti. Nezávislé zdroje článku zůstávají zachovány,
na webu nebyly znovu kontrolovány. Vzdálené issue, PR ani Actions nebyly načteny.

Stav: připravený návrh; CI UNKNOWN; WP nenasazeno; veřejná stránka ani
mobilní Chrome QA neověřeny; měřené kliky/objednávky UNKNOWN. Další fáze
musí nezávisle validovat diff a před vydáním provést mobilní kontrolu.
