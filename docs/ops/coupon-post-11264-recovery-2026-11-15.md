# XFIT: selhávající kuponový článek 11264 — přesná obnova

15. 11. 2026: v běhu [43630700797](https://github.com/Rastty/xfit-growth-os/actions/runs/43630700797)
bylo ověřeně změněno 7 článků a odstraněno 21 zastaralých shortcode bloků.
Osmý článek WordPress ID **11264** zůstal podle autentizovaného readbacku beze změny:
`unchanged_failures: [{id: 11264, stage: write_request, state: unchanged}]`.
Veřejné WordPress REST API 15. 11. potvrzuje status `publish`, kanonickou adresu
`https://xfit.cz/kreatin-v-kombinaci-s-vodou-skutecny-fitness-hit-nebo-jen-marketingovy-trik/`
a tři výskyty `5NM2022` ve vykresleném HTML.

Vlnový skript teď ID 11264 vyřazuje, stejně jako dříve izolované 11595 a 11945;
**to není prohlášení, že kupon na stránce zmizel**. Jednorázový recovery workflow
ovládá přesně jednu URL a povoluje jen odstranění tří starých
`[su_button ...]...5NM2022[/su_button]` bloků, bez úprav jiného obsahu.

Postup: aktuální autentizovaný RAW, ověření přesného ID/slug/status a počtu bloků,
SHA-256 celého zdroje a nové podoby, plná 90denní záloha jako povinný Actions
artefakt, opakované předzápisové ověření, **nejvýše jeden POST**, následný
autentizovaný hash a nezávislé veřejné ověření. Při zjištění dalšího výskytu
kódu, souběžné editace nebo nezměněného výsledku proces končí chybou.
Žádné mazání, redirect, výměna affiliate ID nebo instalace pluginu.

Workflow: `.github/workflows/xfit-coupon-post-11264-recovery.yml`.
Testy: `tests/test_coupon_recovery_11264.py` plus celý regresní balík.
Úspěch v GitHub CI nebo vytvoření zálohy sám o sobě neprokazuje opravený web.
Za produkční výsledek považujeme pouze `PUBLIC_VERIFIED` a veřejný článek bez kódu.
