# XFIT: skutečné interní odkazy z archivu do šesti průvodců

## Co přidáváme

Týdenní read-only `XFIT Full Archive Audit` už načítá publikované články z
WordPress REST. Nově ze stejných ověřovaných HTML těl vyhodnotí, **z kolika
jedinečných článků vede skutečný `<a href>` odkaz na každý ze šesti hlavních
průvodců XFIT**. Neprovádí další HTTP požadavky ani žádné WordPress změny.

V artefaktu `reports/xfit-archive-full-audit.json` je nový objekt
`guide_inlink_coverage`. U každého z šesti průvodců obsahuje počet zdrojových
článků a nanejvýš 12 identifikátorů a veřejných slugů zdrojů pro ruční
kontrolu. Při dvou odkazech z jednoho článku se počítá jeden zdroj. Stejně tak
se neduplikuje opakovaný WP post při posunuté stránkované inventuře. Ignorují
se self-linky, komentáře, `<template>`, `<script>`, cizí domény a podvržené
hosty. Dotazové parametry ani affiliate tokeny se neukládají do výstupu.

V logu běhu je jen agregovaný počet odkazujících článků pro každý cíl a stav
úplnosti. **Pokud sken skončí předčasně, `PARTIAL_SCAN_NO_ABSENCE_CONCLUSIONS`**:
nepovažovat nízké nebo nulové počty za důkaz, že chybí odkazy. Ani úplný REST
sken není atomický a může při nových publikacích přeskočit některé ID.

## Interpretace, nikoli automatická SEO oprava

- `source_post_count = 0` znamená jen **nenalezen v tělech naskenovaných
  publikovaných příspěvků**. Neznamená to osiřelý web, nulové externí odkazy,
  absenci v menu, stránkách, sitemap ani neindexaci v Googlu.
- Nejprve zkontrolovat konkrétní zdroje a jejich téma. Přidat odkaz jen tam,
  kde skutečně řeší navazující otázku a pomůže návštěvníkovi.
- U dvou poradenských URL označených GSC jako `Discovered – currently not
  indexed` dne 16. 11. 2026 toto poskytne **nový druh interního důkazu**, ne
  záruku indexace ani měřený SEO růst.
- Nespoléhat na automatické doplňování odkazů, nevracet se pořád ke stejným
  článkům. Případný další obsahový zásah vybírat podle nové GSC evidence,
  relevance zdroje a dosažitelnosti pro člověka.

## Ověření a provoz

```bash
python -m unittest tests.test_xfit_internal_inlinks tests.test_archive_full -q
python scripts/xfit_archive_full.py --help
```

Po aktualizaci workflow se při změně auditního skriptu, testu nebo workflow
na `main` spustí jednorázová read-only inventura; navíc nadále běží každou
neděli a podporuje manuální `workflow_dispatch`. Sběr celého archivu může
trvat několik minut. Při plánovaném a push běhu platí stejná serializační
skupina `xfit-wp-heavy-reads` bez rušení rozběhnuté úlohy.

Nejde o nově publikovanou stránku,
změnu navigace, vynucenou Google indexaci ani konverzní atribuci.

**Rollback:** revertovat přidaný import, pole `guide_inlink_coverage` a nový
pomocný modul; ostatní výstupy archivačního auditu zůstanou nezměněné.
