# XFIT druhá vlna přesného intent interního prolinkování

První produkční vlna [run 43722244539](https://github.com/Rastty/xfit-growth-os/actions/runs/43722244539): WordPress 10854 a 10738 `PUBLIC_VERIFIED`; článek 7363 `UNRESOLVED_OR_DRIFTED`, obsah beze změny, bez retry. Následná read-only diagnostika [run 43722689086](https://github.com/Rastty/xfit-growth-os/actions/runs/43722689086) potvrdila nepřítomnost markeru i cílového odkazu jak ve standardním, tak v cache-busted API GET. Nejde o veřejnou cache; WP uvádí poslední změnu 2023. 7363 nebyl opakovaně zapsán.

Samostatná druhá vlna cílí **dvě jiné existující URL** z publikovaného read-only intent discovery výstupu 10. 11. 2026:

- WP 9772 — výběr kreatinu monohydrátu; přesný cíl `/xfit-os-kreatin-poradce/`
- WP 7195 — výběr proteinu do nápojů; přesný cíl `/xfit-os-syrovatkovy-protein-porovnani/`

Oba texty jsou úzce relevantní a nepředstírají ověřenou dostupnost, nejnižší cenu na trhu ani zdravotní doporučení. Cílové články, názvy, kanonické slugs a statusy se vždy kontrolují bezprostředně před změnou. Workflow před první úpravou uchová celé původní HTML obou článků na 90 dnů jako rollback artefakt. Pak lze u každého článku provést nanejvýš jeden POST; ověřuje se přesné source SHA a nezávislé veřejné zobrazení. Zjištěný drift nebo nezměněný readback zastaví běh bez automatického retry. Žádné pluginy, nové články, redirecty ani mazání.

Výsledek publikace uvádějte až dle GitHub Actions evidence (`PUBLIC_VERIFIED` vs `UNRESOLVED`), nikoli dle sloučeného PR.
