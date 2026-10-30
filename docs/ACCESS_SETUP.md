# Xfit — přístup a bezpečné publikování

## 1) WordPress REST API (bez WPVibe)

Nejprve vytvoř samostatného WP uživatele **Editor** pro automatizaci (upravovat články a stránky, nikoli instalovat pluginy). U něj v Profilu → **Aplikační hesla** vytvoř odvolatelné heslo.

**Nikdy neukládej heslo do GitHub souborů, issues, PR, ani do konverzace.** V repozitáři otevři Settings → Secrets and variables → Actions → New repository secret a přidej:

| Secret | Hodnota |
|---|---|
| WP_BASE_URL | https://xfit.cz |
| WP_USERNAME | uživatelské jméno odděleného WP Editor účtu |
| WP_APP_PASSWORD | aplikační heslo z WordPressu |

Doporučení: ulož WP_BASE_URL jako Actions variable a nastav secret pouze pro jméno a aplikační heslo. Workflow aktuálně umí načíst WP_BASE_URL také jako secret. Omezení API musí být ověřena read-back testem; HTTP Basic Authentication používej pouze přes HTTPS.

## 2) GitHub

Repozitář může být soukromý; je-li veřejný, neukládej do něj neveřejná obchodní data nebo produkty vyžadující důvěrnost. V žádném případě neukládej reálná hesla do commitu. Udržuj write přístup pouze pro Xfit a nijak nepřipojuj Prometheus.

## 3) Hosting

Pro interaktivní JS/CSS poradce vyžadujeme dostupný způsob nasazování kódu (Git deployment, SSH/SFTP nebo CI/CD hosting provider). **Neukládej zatím SSH klíče, dokud nebude stanovena cílová cesta a rollback.** WP REST API umí vytvořit/aktualizovat obsah, ale ne samo o sobě bezpečně nasadit kompletní vlastní frontend.

## 4) Partner programy

Pošli názvy partnerů a popis formátu feedů; affiliate ID a neveřejné feed URL/tokeny ukládej jako GitHub Secrets. Dohodni licenci a interval aktualizace feedů. Než feed napojíme, neprezentujeme ilustrační produkty jako dostupné nabídky.

## 5) První smoke test

1. Na GitHubu otevři Actions → **XFIT Publish** → Run workflow.
2. Zvol existující soubor v \`content/ready/\` a režim \`draft\` (výchozí).
3. Workflow provede unit testy, zapíše návrh přes nativní WP API a ověří read-back.
4. Až následně přepneme připravený obsah na publikovaný stav.
5. Pro skutečný live release je nutné veřejně ověřit URL a její obsah.

**Důležité:** Bez 3 proměnných WP nelze publikovat. Vždy rozlišuj \`committed\`, \`api_accepted\`, \`live_verified\`.
