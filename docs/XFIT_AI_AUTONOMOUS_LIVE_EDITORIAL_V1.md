# XFIT: skutečný autonomní AI obsahový cyklus (v1)

## Co poběží bez ručního „schvaluji“

Každý plánovaný běh (šestkrát denně, nejvýše jedno publikování za běh) zvolí **jeden** dosud nevyřízený přesně určený úkol z `config/xfit-ai-editorial-targets-v1.json`. Pokud je fronta vyčerpaná, **neutrácí žádný token** a neprovádí žádný WordPress zápis. U vybraného úkolu pak proběhnou tyto oddělené fáze:

1. **Výběr / WP kontrola (read-only):** autentizované REST API zjistí přesné ID, slug, původní surový obsah a čas poslední editace; do další fáze se předá pouze SHA-256, ověřená identita, stručný kontext a redakční zadání. WP heslo se nepředává.
2. **AI autor:** oficiální `openai/codex-action@v1` vytvoří pouze **jeden JSON návrh**; nemá WP credentials, GitHub write token ani oprávnění přepsat řídicí skript. Přímé síťové vyhledávání a použití neověřených produktů nejsou součástí této verze.
3. **Nezávislý QA gate:** původní kód z chráněné `main` větve v samostatném kroku ověří identitu zadání, povolené odkazy, HTML, rozsah, originalitu rozhodovacího bloku a přísný redakční standard. Zdravotní diagnózy, léčba, dávkování a neověřené affiliate produkty jsou vyřazeny.
4. **Publikační job** se samostatnými WordPress hesly provede stejné QA. U nových článků vydává jen nové stránky pod `xfit-os-*`; u existujících výslovně povolených článků zachová **celý původní obsah** a vloží jednu novou konkrétní sekci. Před zápisem ověří přesný hash a `post_modified_gmt` původního obsahu.
5. **WordPress a public readback**: po zápisu ověří surový text článku a přesný unikátní marker na veřejné stránce. Při neúspěchu pokusí o selektivní rollback **pouze když** původní zápis nebyl dalšími editory změněn; jinak skončí `BLOCKED_MANUAL_REVIEW`. Výsledek uloží do GitHub Actions artifact.

Veškeré činnosti se zastavují, pokud nestačí důkazy k bezpečné publikaci. CI GREEN není důkaz živé publikace.

## Rozsah pilotu

- **Zlepšení existujících:** vlastní kalkulační průvodce o ceně proteinu (WP ID 25541), následně přesně pinovaný článek o Pilates (WP ID 3660). Žádné plošné přepisování 12 tisíc původních článků, žádné změny titulku, slugů, kanonických URL, kategorií či redirectů.
- **Nové články:** přesné výpočty a spotřebitelské rozhodování z fixního seznamu, např. porovnání proteinových tyčinek, ceny připraveného nápoje a výběr podložky.
- **Maximálně 1 obsahový zásah za běh**, 6 možností denně. Tím je limitována škoda při chybě i spotřeba API.
- **Nepodporované:** komplexní medicínské rady a léčba, personalizovaná výživa, automatické převzetí zdravotních tvrzení z e-shopů, produktové recenze bez testů, feed ceny bez validace, SEO mass-delete, automatický merge jakýchkoli Codex PR.

## Proč dvě různé AI větve

Dosavadní čtyři Codex lane (UX, archiv, editor, revenue) nadále dělají **návrhy změn kódu** a PR. Nová lane dělá **pouze obsahové JSON návrhy**, bez změn kódu nebo práv k produkci. Následný publikační job uvažuje výhradně o tomto omezeném JSON podle schválené konfigurace.

## Monitoring a nouzové vypnutí

GitHub Actions → **XFIT AI Author and Source-Bound Live Publisher**. Očekávané stavové štítky:

- `TARGET_SELECTED` a `AI_EDITORIAL_VALIDATED_NO_WRITES` = připravená, ale ještě nevydaná AI práce.
- `PUBLIC_VERIFIED_NEW_AI_ARTICLE` / `PUBLIC_VERIFIED_AI_EXISTING_ARTICLE_UPDATE` = skutečný WordPress zápis + veřejné ověření.
- `NO_APPROVED_TARGET` = bezpečně vyčerpaná fronta; nic se nevydalo a model nebyl volán.
- `BLOCKED_MANUAL_REVIEW` = problém, který nelze překrýt dalším pokusem bez vyšetření.

Na pozastavení stačí deaktivovat workflow v GitHub Actions; revize WordPress zůstávají zachované.

## Známé limity

- Technická validace sama nedokáže zaručit pravdivost všech jazykových či faktických tvrzení. Proto má pilot **předem vybrané, nízkorizikové a nadčasové** úlohy s kontrolovanými odkazy.
- Cíl je dlouhodobý cyklus problem → draft → validate → publish → measure, ale současná verze **nemá neomezené generování témat podle GSC/GA4**, ani ověřené komise Affial. Když připravené úlohy dojdou, automatika je nesmí nahradit nekvalitním SEO obsahem.
- Při prvním nasazení se musí potvrdit skutečné LIVE evidence, nestačí dokončení GitHub workflow.

Viz `scripts/xfit_ai_editorial.py`, `tests/test_ai_editorial.py` a `.github/workflows/xfit-ai-editorial-live.yml`.
