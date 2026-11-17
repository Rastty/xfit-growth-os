# XFIT: upřesnění rehabilitace zad po úrazu nebo operaci (WP 5929)

## Proč právě tento článek

Z publikované stránky `https://xfit.cz/jak-pilates-pro-zada-muze-pomoci-pri-rehabilitaci-po-urazu-nebo-operaci-zad/` (původní změna 8. 5. 2023) bylo v read-only WordPress REST vidět několik opakovaných bloků, přímé pobízení k cvičení po operaci bez rozlišení omezení a nepodložené tvrzení o „našem Pilates instruktorovi“. Text jmenoval plank a superman jako obecné příklady bez předchozího klinického schválení. To je pro vyhledávací dotazy po operaci páteře riziková rada, nejen SEO problém.

Historická GSC evidence za 17. 10.–13. 11. 2026 uvádí pro tento související dotaz/URL skupinu **30 impressions, 0 clicks, průměrná pozice 8,37**. Nejde o garantovaný výnos, reprezentativní návštěvnost ani efekt revize. Primární motivace je bezpečnější rozhodnutí návštěvníka.

## Jedna cílená redakční změna

- Návštěvník okamžitě vidí rozhodnutí: po úrazu/operaci nejprve individuální klinická doporučení, nikoli generická lekce.
- Odděleny pooperační stav, neoperovaný úraz a nespecifická bolest zad; NICE guideline není vydáván za pooperační protokol.
- Neodkladné příznaky, opatrný návrat k pohybu a konkrétní otázky pro fyzioterapeuta.
- Odkazy na NHS nemocnice RNOH, CUH a NICE; bez falešných výsledků, produktů, affiliate CTA nebo nákupu.
- Zachování existující URL, bez nových stránek a bez změny titulu/permalinku/kategorií.

## Nasazení a hranice rizika

`scripts/xfit_pilates_after_surgery_5929.py` připustí jen přesné WP ID `5929`, slug, canonical, `publish` a autenticky načtený `modified_gmt`. Před zápisem vyžaduje původní charakteristická chybná tvrzení. Uloží celé originální `content.raw`, SHA a timestamp do 90denního GitHub Actions artifactu; teprve po **úspěšném uploadu backupu** směruje jediný `content`-only WordPress POST. Před POSTem znovu porovnává zdroj a timestamp s backupem, po POSTu provádí autentický i veřejný REST/HTML readback. Pokud je výsledek nejednoznačný, nikdy slepě neopakuje zápis. Záloha umožní přesné navrácení po kontrole aktuálního stavu a konfliktu změn; automatický rollback bez kontroly zde není.

Trvalý editorial gate přesně rozpoznává nové nezávislé klinické zdroje `www.rnoh.nhs.uk`, `www.cuh.nhs.uk`, `www.nice.org.uk`. Nevytváří obecnou doménovou výjimku pro libovolný web končící na `nhs.uk`.

## Ověření, dokud neběží produkce

- `python -m unittest discover -s tests -p test_pilates_after_surgery_5929.py -q`
- `python -m unittest discover -s tests -q`
- Po merge: jedna navazující GitHub Actions workflow, originální rollback artifact, `PUBLIC_VERIFIED`, veřejné URL a skutečné mobilní čtení při šířce 375 px.
- Dopad GSC/GA4, objednávky a provize: **UNKNOWN**. Článek je nekomerční a nesmí tvrdit prodejní efekt.

Další cyklus by se měl vrátit k testování použitelnosti poradenského enginu a skutečných konverzních dat, nikoli znovu přepisovat tuto URL.
