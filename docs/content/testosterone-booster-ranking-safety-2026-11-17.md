# XFIT: oprava zdravotně rizikového žebříčku na homepage

**Zdrojový problém (17. 11. 2026):** Homepage `https://xfit.cz/` uvádí hned
první článek `https://xfit.cz/pripravky-na-zvyseni-hladiny-testosteronu-srovnani/`
pod starým titulkem pro rok 2025. Ve veřejně čitelném těle jsou hodnocení
produktů **50 %, 60 %, 92 %, 95 %**, propagace čtyř značek, tvrzení o
zvýšení testosteronu/svalů a opakované absolutní sliby bezpečnosti. Chybí
ověřitelná metoda procentního hodnocení a důkazy o účinnosti konkrétních
směsí. Není to přijatelný důvěryhodný zdravotní obsah.

## Co měníme a proč

- Zachováme původní URL a WP článek, abychom nepřerušili již existující
  odkazy. Nadpis opravíme na nadčasový a věcný.
- Kompletně nahradíme původní nepodložený produktový žebříček vysvětlením
  rozdílu mezi doplňkem, diagnostikou hormonálního nedostatku a skutečně
  doloženým účinkem; žádná nová nákupní nabídka ani provizní odkaz.
- Čtenář dostane jasný postup, kdy **nekupovat nic**, kdy posílit tréninkové
  návyky a kdy se obrátit na lékaře. Není to personalizovaná diagnóza.
- Zdroje: [Endocrine Society](https://www.endocrine.org/clinical-practice-guidelines/testosterone-therapy),
  [NIH ODS](https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/),
  [OPSS](https://www.opss.org/article/testosterone-booster-and-sexual-enhancement-dietary-supplements),
  [Evropská komise](https://food.ec.europa.eu/food-safety/labelling-and-nutrition/nutrition-and-health-claims_en).

## Zabezpečení změny

1. Workflow načte v autentizovaném WordPressu jediný publikovaný článek
   s *přesně* stanoveným slugem, URL, původními čtyřmi názvy produktů a
   redakčním titulem. Pokud se mezitím změnil, **nepíše nic**.
2. Před jediným POST uloží **celý původní raw obsah, původní titulek,
   post ID, featured_media, datum změny a SHA-256** do 90denního artefaktu.
   Artefakt musí být úspěšně uložen dřív, než začne krok zápisu.
3. Před POST znovu načte konkrétní zmrazené ID; musí sedět kompletní
   původní obsah, titul, timestamp i metadata.
4. Jediný WP REST POST mění pouze `content` a `title`. Nevytváří další
   článek, nemaže komentáře ani média ve WordPress knihovně, nepřesměrovává.
   Původní produktové obrázky vložené v těle nezachováváme, protože by
   v opraveném nekomerčním textu podporovaly nepodložené pořadí; existující
   `featured_media` metadata zůstávají zachována.
5. Po zápisu následuje administrátorský readback a samostatná veřejná
   kontrola skutečně nového titulku a textu. Staré cachované HTML =
   **NEOVĚŘENO**; POST se nikdy automaticky neopakuje.

## Měření a rollback

- Připravená revize není automaticky živá. Publikaci lze tvrdit až při
  workflow `PUBLIC_VERIFIED`, ideálně s nezávislým veřejným přečtením.
- Při problému je zdrojem rollbacku nepozměněný původní `original_raw` a
  `original_title` v artefaktu. Návrat by byl samostatný řízený jednopostový
  WP zápis po novém porovnání identity; nikdy automaticky při timeoutu.
- GSC kliknutí, GA4 přistání, affiliate prokliky a tržby tím nejsou
  prokázány. Po vydání sledovat konkrétní URL a relevantní dotazy;
  obchodní efekt zůstává `UNKNOWN`.

Návaznost: `AGENTS.md`, `docs/EDITORIAL_STANDARD.md`, issue #4 (Editor).
