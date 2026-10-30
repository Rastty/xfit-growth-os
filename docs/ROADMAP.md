# Xfit Growth OS — cílový graf práce

## Hlavní metrika

Kvalifikované organické návštěvy → užitečná práce s poradcem → affiliate proklik → ověřené affiliate objednávky a výnos. Počty vytvořených článků ani commitů nejsou obchodní výsledek.

## P0 — základní infrastruktura
- [x] Oddělený GitHub repozitář; funkční zápis z připojeného asistenta.
- [x] První nativní REST API publisher, čtení public API, bezpečnostní testy a GitHub workflows jako kód.
- [x] WordPress API authentication, draft test and public release verification (live first guide).
- [x] GSC/GA4 exports received and analyzed (private report; not committed to public repo).\n- [x] Per-article backup and in-place Pilates revision, verified live (WP post 3660).\n- [ ] Full WP archive backup and source x landing-page performance inventory before bulk cleanup.
- [ ] Hosting deployment cesta pro poradce JS/CSS.

## P1 — obsah a SEO
- [ ] Paginovaný audit archivu: duplicity, tenký obsah, neaktuální informace, interní odkazy, rizikové odchozí domény a kanibalizace.
- [ ] Návrh informační architektury pro potřeby návštěvníků, nikoli pouze chronologické články.
- [x] First existing Google-opportunity Pilates article revised in place, backup stored and live-verified; see GitHub Actions run 41089083374.\n- [ ] Follow-on existing landing improvements after GA4 source/medium x landing-page report; **no bulk archive deletion**.

## P2 — první poradce
- [ ] Protein selector: cíl, alergeny a omezení, rozpočet, cena za 100 g bílkovin, jednoduché vysvětlení volby.
- [ ] Feed normalizer: nabídky, EAN/SKU, cena, dostupnost, merchant, affiliate deeplink, updated_at.
- [ ] Validace s člověkem tam, kde by šlo o zdravotní doporučení; nevyrábět zázračná tvrzení.
- [ ] Responsive UI, přístupnost, bezpečné odkazy, měření kliknutí bez citlivých údajů.

## P3 — škálování
- [ ] Kreatin advisor a výběr domácí posilovny.
- [ ] Rozšíření na další typy vybavení podle GSC + konverzí.
- [ ] Periodické aktualizace produktových feedů s monitoringem a rollback.

## Stavový automat

\`discovered → specified → coded → tested → WP/hosting deployed → public verified → measured → improved\`

Přeskočit nelze \`public verified\`. Na veřejný web jde pouze připravený obsah označený pro vlastní namespace Xfit OS.

## Přísné oddělení

Tento repozitář a jeho workflows **nikdy** nemění ani nečtou interní plánovací dokumenty Prometheus. Žádné společné fronty, nové projekty ani sdílené produkční klíče.

## Analytické priority po 30. 10. 2026

Viz `docs/GROWTH_PLAN_AFTER_EXPORTS.md`. Organická návštěvnost v GA4 musí být rozlišena podle `Session source/medium` (nikoli pouze `Session manual source`); Google Search Console nepopisuje Seznam. Neuchovávat privátní exporty v tomto veřejném repozitáři.
