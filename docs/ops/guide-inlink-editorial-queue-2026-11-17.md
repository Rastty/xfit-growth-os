# XFIT: kandidáti na nové zdroje interních odkazů

Plný read-only audit již doložil pouze **4 různé zdrojové články** s odkazy
do každého z průvodců `xfit-os-kreatin-nebo-protein` a
`xfit-os-cena-proteinu-podle-etikety`. Nižší počet není důkaz SEO chyby.

Navazující pole `guide_inlink_editorial_queue` ve stejném artefaktu nabízí
maximálně 12 **nových kandidátů pro ruční kontrolu** pro každý z těchto dvou
cílů. Další vzdálené požadavky ani WordPress zápisy nepřidává.

### Pravidla výběru

- Vstupem jsou pouze deduplikované publikované příspěvky z úplného / částečného
  REST skenu. Při částečném skenu není výčet úplný.
- Zdroj musí mít platný veřejný kanonický slug a přímou URL na `xfit.cz`.
- Název nebo slug musí jasně obsahovat související téma. U kreatinu vs.
  proteinu se vyžadují **oba** pojmy; u ceny proteinu protein + cenový,
  etiketový nebo srovnávací kontext. Nehodnotí se celá relevance článku.
- Zdroj již nesmí mít skutečný odkaz v HTML těle na daného průvodce.
- Vynechají se všechny ústřední průvodce i příspěvky upravené v posledních
  14 kalendářních dnech, v budoucnosti nebo s neznámým datem úpravy.
- Zapisuje se jen ID, slug, den úpravy a síla názvové shody. Žádné query
  parametry, externí adresy ani affiliate tokeny.

### Redakční brána

`HUMAN_REVIEW_ONLY`: před každým prolinkováním otevřít *zdrojový článek*,
posoudit kontext a ověřit, že cílová stránka skutečně řeší návaznou otázku.
Pokud nejde vhodné místo přirozeně najít, **nic nepřidávat**. Výstup není
návrh na hromadné změny, záruka růstu ani důkaz, že článek nemá jiné odkazy.

### Ověření

```bash
python -m unittest tests.test_xfit_inlink_opportunities tests.test_xfit_internal_inlinks tests.test_archive_full -q
python -m unittest discover -s tests -q
python scripts/xfit_archive_full.py --help
```

Nová verze workflow po merge spustí čerstvý audit; starý artefakt zůstává
historickým snapshotem bez nového pole. Při selhání nebo neúplné stránkované
inventuře nesmí nikdo považovat absenci kandidátů za definitivní.
