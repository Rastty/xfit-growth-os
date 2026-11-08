# XFIT — obnova paralelního Codex vývoje po `startup_failure`

## Zjištěné důkazy (8. 11. 2026)

Poslední běhy [42411257387](https://github.com/Rastty/xfit-growth-os/actions/runs/42411257387),
[42427487521](https://github.com/Rastty/xfit-growth-os/actions/runs/42427487521) a
[42455747094](https://github.com/Rastty/xfit-growth-os/actions/runs/42455747094)
skončily `startup_failure` prakticky okamžitě, se **0 jobs**,
0 modelovými patchi a bez autentizovaných WordPress zápisů.

## Statická konfigurace — pravděpodobná příčina

`xfit-codex-parallel.yml` volalo reusable
`xfit-codex-lane.yml` s původním caller token scope:
`contents:write` a `pull-requests:write`.
Volaný `open-pr` job však explicitně žádal také
`actions:write` pro omezené `gh workflow run xfit-checks.yml`.
GitHub podle oficiální dokumentace neumožňuje v reusable
workflow zvýšit oprávnění oproti volajícímu jobu:
https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations

Nově má právě **volající job `parallel-lanes`** explicitně
`actions:write`, `contents:write`, `pull-requests:write`.
`permission-gate` zůstává pouze s `actions:read`.
Volaný `propose` job nemá oprávnění publikovat na web;
`open-pr` smí vytvořit reviewovatelný PR a požádat
o existující **read-only Code Checks** na konkrétní větvi.

## Ověření a meze tvrzení

- Statický test v `tests/test_codex_ci_dispatch.py` hlídá
  soulad všech tří scope, minimální preflight a
  explicitní neprivilegovaný CI dispatch.
- Přidán `push` trigger pouze pro úpravu souboru
  `xfit-codex-parallel.yml`, aby bylo možné závadu
  ověřit hned při nasazení, nikoli čekat čtyři hodiny.
- Skutečný úspěch nastává až tehdy, když GitHub sestaví
  `permission-gate` a `parallel-lanes` jobs. Job může
  legitimně skončit `skipped` kvůli `XFIT_CODEX_AGENTS_ENABLED`
  nebo explicitnímu PR/oprávnění. To není důkaz
  vygenerovaného PR ani webové změny.
- Pokud run stále skončí `startup_failure` bez jobů,
  příčinou může být také interní GitHub Actions
  konfigurace/registrace, policy nebo billing.
  Nediagnostikovat ji z neexistujících job logs;
  použít workflow/run ID pro další kontrolu.
- OpenAI náklady: modelový job může být spuštěn pouze
  pokud vlastník nastavil flag a repo obsahuje klíč
  pro Action; zabudovaný preflight kontroluje otevřené
  agent-owned PR, aby se neopakovaly návrhy.
- Bez pluginů, bez zásahu do WordPressu, bez automatického
  merge a bez tvrzení o obchodním příjmu.

Rollback: revert volajícího job permission blocku i
kontrolního testu; vrátí se původní nefunkční stav,
nikoliv změna webového obsahu.
