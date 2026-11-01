# XFIT: bezobslužné publikování schváleného vzdělávacího obsahu

**Stav:** nový nezávislý publikační kanál. Nepotřebuje nové WP pluginy ani přímý přístup Codexu k WordPress heslům.

## Účel

Články uložené v `content/auto-ready/` a výslovně připnuté k seznamu `queue-v1.json` jsou publikovány přes existující native WordPress REST API. Workflow se spouští automaticky při schváleném merge do `main` nebo třikrát denně. Každý běh může vydat **maximálně jeden nový článek**. Po vydání ověří vlastnictví, přesný veřejně viditelný marker a zaznamená evidence JSON artifact. Následující běhy jsou idempotentní.

Není to mechanismus pro automatické psaní všech budoucích článků. *Přípravu nových kvalitních podkladů* mohou nadále dělat samostatní Codex agenti, ale tento publikační kanál přijímá pouze konkrétní, testovaný, verziově připnutý obsah na schválené větvi. Tím oddělujeme generování textu od přístupu k produkčnímu WordPressu.

## Povolený rozsah

- Nové stránky výhradně ve vlastním jmenném prostoru `xfit-os-*`.
- Neobchodní vzdělávací průvodce s alespoň 450 slovy, více oddíly, kontrolou odkazů a oficiálním zdrojem.
- Žádné přímé affiliate odkazy, neověřené produkty, lékařské rozhodování či citlivé zdravotní tvrzení.
- Kód a public release marker musí odpovídat přesně schválenému Git blob SHA, zadanému v queue.
- Při konfliktu se živým článkem se **nic nepřepíše**; systém zastaví s `BLOCKED_MANUAL_REVIEW`.

Komplexnější poradci s aktuálními ověřenými produktovými daty běží v samostatných workflows `xfit-creatine-live.yml` a `xfit-whey-live.yml`, které mají vlastní zdroje, ochranu a testy.

## Proces vydání

1. Nový kvalitní a fakticky ověřený neobchodní článek vytvořit v `content/auto-ready/xfit-os-...json`.
2. Z jeho Git blob SHA připnout položku v `content/auto-ready/queue-v1.json`.
3. Dokončit PR a projít Python testy i ruční kontrolou obsahu, zejména originality, správnosti matematických výpočtů, zdrojů a mobilní čitelnosti.
4. Merge do `main` spustí workflow; žádný další WordPress admin Apply.
5. Po úspěchu workflow musí evidence obsahovat `PUBLIC_VERIFIED_NEW_POST`, ID a skutečnou adresu. HTTP 200 nebo samotné CI nejsou publikace.

Opakované běhy dokládají `ALL_PINNED_ARTICLES_PUBLIC_VERIFIED`; 0 nových zápisů je správná idempotence. Když URL po zápisu nejde číst z veřejného internetu, workflow nahlásí `BLOCKED_MANUAL_REVIEW`. Neprovádějte automatické slepé opakování POST ani rollback bez kontroly WP revizí.

## Bezpečnost a limity

- V kódu nejsou WP hesla ani affiliate secret IDs. Existující `WP_USERNAME`, `WP_APP_PASSWORD`, `WP_BASE_URL` jsou GitHub Actions Secrets.
- `xfit-auto-release.py` není samostatný AI worker. Automatické psaní dalších článků vyžaduje novou samostatnou a testovanou authoring lane a nezávislou redakční kontrolu.
- Automatický kanál nesmí mazat starý archiv, měnit canonical/noindex/redirect, přidávat affiliate tracking ani aktualizovat cizí posty.
- GitHub Actions scheduled runs mohou mít zpoždění a CI může být blokované poskytovatelem. Nepoužívejte časový plán jako důkaz úspěšného vydání.
- Public kontrola je jedna perspektiva; na rychlost indexace Google ani provize se z ní neusuzuje.
- Nouzové vypnutí: deaktivujte workflow `XFIT Autonomous Approved Editorial Publish` v GitHub Actions; již publikované články zůstávají beze změny.

## První kanárek

`xfit-os-cena-proteinu-podle-etikety` — praktický výpočet ceny bílkovin s výslovně hypotetickými čísly a oficiálními zdroji. Nikoli nová fiktivní komerční nabídka.
