# XFIT: první-party GA4 kliky přes WebToffee 3 — omezené nasazení

## Ověřený podklad (7. 11. 2026)

- WordPress inventura: aktivní **WebToffee**, hlavní verze **3**. Důkaz: [GitHub Actions run 42371869532](https://github.com/Rastty/xfit-growth-os/actions/runs/42371869532).
- Obě veřejné stránky používají Google tag; samotná přítomnost tagu **nedokládá GA4 event ingestion ani správně nastavený consent**.
- V obou WP/source a public stránkách jsou již ověřené identifikátory 6 + 6 produktových CTA: [run 42370752238](https://github.com/Rastty/xfit-growth-os/actions/runs/42370752238).
- Před implementací **není** v HTML načten `xfit-outbound.js`, měřené kliky jsou UNKNOWN.

Dokumentované oficiální WebToffee 3 rozhraní:

- https://www.webtoffee.com/docs/gdpr-plugin/javascript-api-and-custom-hooks-for-gdpr-cookie-consent/
- https://www.webtoffee.com/docs/gdpr-plugin/implementing-google-consent-mode-v2/
- https://support.google.com/analytics/answer/16293860?hl=en

## Implementace připravená v GitHubu

`wordpress-plugin/xfit-analytics/xfit-analytics.php` je samostatný minimalistický WP plugin. Načítá **jen na dvou schválených sluzích** a jen z vlastního hostingu `assets/xfit-webtoffee-bridge.js` a `assets/xfit-outbound.js`, přes `wp_enqueue_script`, ne přes editor článku nebo inline onclick.

Bridge používá při každém prokliku živé `window.getWccConsent()` WebToffee 3. Uznává jen přesnou hodnotu `categories.analytics === true`. Při zamítnutí, odvolání souhlasu, chybě nebo chybějícím API vrací false. Neukládá žádné cookies ani odpovědi poradce.

Samotný outbound adaptér při **skutečném uživatelském kliknutí** ověřuje aktuální slug, kartu, kladné katalogové ID, oficiální HTTPS doménu, affiliate parametry, `rel=sponsored` a **přesnou shodu katalogového ID s jediným parametrem `variant`**. Read-only audit skutečných veřejných karet v GitHub Actions běhu 42865679992 ověřil 6/6 shod u kreatinu a 6/6 u whey. U odkazu bez varianty nebo s nesouladem adaptér událost neodešle, ale nákupní navigaci neblokuje. Tato kontrola nepotvrzuje GA4 ingest, skutečnou objednávku ani provizi. Do Google tagu odesílá `affiliate_outbound_click` pouze se čtyřmi parametry: `page`, `selection_engine`, `partner`, `product_id`. Neposílá odchozí URL, UTM na vstupní stránce, email, zdravotní odpovědi, affiliate ID ani jakýkoliv údaj o nákupu. Nepřerušuje navigaci. Klik není nákup ani provize.

## Instalační brána (není automatické produkční nasazení)

`XFIT Consent-Gated Analytics Plugin Package` vytváří instalační ZIP z kontrolovaného GitHubu jako artefakt Actions. Bez ověřeného oprávnění pro nahrání souborů do WP/hostingu jej workflow **samo neinstaluje**. Rutinní WordPress REST API aplikace v tomto projektu umí publikovat články, nikoli bezpečně instalovat libovolný nový PHP plugin. Nenahrazovat instalaci vložením scriptu do článku.

Jednorázové bezpečné zprovoznění po úspěšném CI:

1. Stáhnout ZIP artefakt z úspěšného workflow `XFIT Consent-Gated Analytics Plugin Package` (rozbalit artefakt pokud jej GitHub automaticky zabalí; samotný soubor pro WP je `xfit-analytics-0.1.1.zip`).
2. Ve WordPressu **Pluginy → Instalace pluginů → Nahrát plugin**, vybrat ZIP a aktivovat; ideálně nejprve staging a ověřit kompatibilitu WebToffee 3.
3. Potvrdit v produkčním preflightu zdroje skriptů a ověřit browserem jejich HTTP 200 a pořadí. Ověřit skutečnou konfiguraci WebToffee GCM, konzoli a Tag Assistant. Po odmítnutí analytického souhlasu nesmí být odeslána žádná naše custom `affiliate_outbound_click` událost; po souhlasu ji odeslat kontrolovaným skutečným kliknutím.
4. GA4 DebugView potvrzuje událost se čtyřmi schválenými parametry. Prověřit, že GA4 / jiné analytické requesty respektují souhlas, včetně jeho odvolání, a nespouštějí předčasně nezakázané měření. Zajistit, že consent manager a GA4 jsou nakonfigurované právně vhodným způsobem.
5. V Affial nezávisle ověřit skutečné partnerské prokliky a případné připsané objednávky/provize, bez automatického vydávání GA4 kliků za tržby.

**Do ukončení kroků 2–4: `ga4_event_observed=UNKNOWN`, `consent_bridge_verified=UNKNOWN`, `orders=UNKNOWN`, `commission=UNKNOWN`.**

## Testy a rollback

- `python -m unittest discover -s tests -v`
- `node --test tests/test_outbound_analytics.cjs tests/test_webtoffee_bridge.cjs`
- `python -m scripts.build_xfit_wp_plugin` (jen lokální ZIP, žádný WP zápis)
- ZIP balení obsahuje pouze 3 schválené first-party soubory a po dvou kompilacích je byte-identické.

Rollback při poškození UX nebo nesprávné consent integraci: ve WordPressu deaktivovat `XFIT Verified Affiliate Click Analytics`. Produktové stránky, ceny i affiliate odkazy zůstávají nedotčené. Samotné vypnutí pluginu nemaže již uložená GA4 data.

Žádné produktové soubory, GA4 klíče ani WP credentials nedávat do veřejného GitHubu. Veškeré produkční důkazy musí vycházet z veřejné stránky a/nebo skutečného GA4 či Affial záznamu.
