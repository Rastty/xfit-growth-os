# Xfit — 4 cíle začátečníka → další krok bez zbytečného nákupu

## Přínos

Stávající https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/
(WP 25458) má kvalitní podrobný článek a čtyři otevřitelné
situace. Ve výchozím stavu jsou všechny odpovědi schované,
včetně nejdůležitější rady: **pro začátek často nic nekupovat**.
Po přečtení situace navíc čtenář musí znovu hledat související
odborný průvodce.

Bez jakéhokoli JS, instalace WP pluginu či nového URL článku:

- první cíl **začít bez doplňků** rozbalíme pomocí
  nativního HTML5 `<details open>` a odkážeme na
  již existující rozpočet 0 Kč ve stejném článku;
- cíl síla/svaly přímo přejde do rozhodnutí
  **kreatin, protein, nebo běžné jídlo**;
- cíl redukce hmotnosti přímo odkáže na
  **orientační celkový příjem bílkovin** (nikoli na spalovače);
- omezení stravy/vegan přímo odkáže do průvodce
  **rostlinnými proteiny a alergeny**, nikoli
  do nevhodného syrovátkového srovnávače.

Všechny čtyři cesty jsou interní a již existují.
Původní klinické/nutriční informace jsou zachované;
žádné nové dávkování, cenové či účinnostní tvrzení.

## Vydání

`content/revisions/beginner-goal-handoffs-20261108.json`
obsahuje jedinou přesnou změnu čtyř navazujících detailů.
`scripts/xfit_beginner_goal_release.py` kontroluje:

- přesně schválený fragment, počet cílů, nativní
  rozbalení pouze první volby, právě 4 povolené odkazy;
- přihlášené živé WordPress ID 25458, publish stav,
  autorství a kanonickou URL;
- zachování všech ostatních živých sekcí a původních
  odkazů/obrázků (nepřepisovat zastaralým JSON);
- plnou zálohu HTML, SHA-256 a datum změny,
  uloženou povinně **před jediným POST**;
- opětovné ověření shodného obsahu před pokusem
  o zápis, po zápisu úplný SHA-256 readback a veřejné
  potvrzení přesného textu/4 odkazy/rozbalené volby.

Při driftu či nejasném výsledku se zápis **neopakuje**.
`PUBLIC_VERIFIED` znamená právě jednu změněnou stránku,
`ALREADY_APPLIED_NO_WRITE` znamená nula nových zásahů.

Jednorázový GitHub Action
`.github/workflows/xfit-beginner-goals-live.yml`
se spustí při prvním sloučení vlastního YAML na main,
nemá žádný plánovaný publikační rozvrh.

Rollback je uložen jako
`xfit-beginner-goals-25458-rollback-<run_id>` po 90 dní;
návrat změny musí opět zkontrolovat aktuální zdroj, aby
nesmazal novější editorskou práci.

## Následující kontrola

Skutečný Chrome 375px má potvrdit čtyři správné
rozhodovací cesty, otevřenou první odpověď a že se nic
nedotklo přímých partnerských odkazů. Pokud se
kontrola nezdaří, stav není dokončený.

Výsledek nejde automaticky přepočítat na
návštěvnost, prokliky nebo provize bez dalších dat.
