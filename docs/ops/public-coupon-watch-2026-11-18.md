# XFIT — veřejná kontrola zbylých kupónů 5NM2022

## Důvod

Ve [vlně čištění](https://github.com/Rastty/xfit-growth-os/actions/runs/44282940532)
bylo šesti článkům odstraněno 18 zastaralých kupónových shortcode bloků
s ověřeným readbackem. WP články **11110** a **11090** však zůstaly při
zápisu beze změny. Opakovaný běh skončil na autentizovaném čtení `HTTP 401`
**před jakýmkoli zápisem**. Oprava autentizace je samostatný úkol pro vlastníka.

## Co nyní měříme bez administrace

`scripts/xfit_public_coupon_watch.py` kontroluje každý den **přesně dvě**
veřejné URL, jejichž oprava nebyla ověřena:

- [11110 — doporučené dávkování kreatinu](https://xfit.cz/doporucene-davkovani-a-cykly-kreatinu-pro-svalovy-rozvoj/)
- [11090 — pět důvodů pro kreatin](https://xfit.cz/5-duvodu-proc-by-mel-byt-kreatin-soucasti-tveho-stravovaciho-planu-pro-fitness/)

Kontrola vyžaduje HTTP 200, HTML, přesnou finální URL a jednoznačnou
identitu článku (kanonická URL nebo WordPress `postid-*` v `body`). Nezapočítává
výskyt jen ve skriptech, skrytých prvcích, meta datech a komentářích.
Výsledek ukládá jako malý JSON **bez těla článku, cookies, kupónových odkazů
nebo přihlašovacích údajů**. Neznámé odpovědi (`403`, `404`, přesměrování,
chybějící identita, síťová chyba) nejsou nikdy „čisté“.

| Stav | Význam |
| --- | --- |
| `EXPIRED_COUPON_VISIBLE` | Kupón je nadále v textu veřejné stránky; vyžaduje opravu. |
| `PUBLIC_NO_COUPON_OBSERVED` | V jedné veřejné odpovědi se kupón nevyskytl. Není to potvrzení WP zápisu ani globálního vyčištění cache. |
| `UNVERIFIED_*` | Stránku či identitu nešlo bezpečně ověřit; žádný zelený závěr. |

Pravidelný workflow skončí červeně, dokud nejsou **obě** veřejné stránky
ověřeně bez kupónu. JSON artifact se uloží i při chybě. Workflow nemá
`WP_USERNAME`, `WP_APP_PASSWORD` ani žádný způsob aktualizovat WordPress.

## Dokončení po opravě přístupu

1. Vlastník opraví nebo obnoví XFIT-specific WordPress aplikační heslo a
   nastavení `WP_USERNAME` / `WP_APP_PASSWORD` v GitHub Actions Secrets;
   tajné hodnoty **nesdílí do issue ani chatu**.
2. Teprve poté lze bezpečně obnovit nativní cleanup flow s povinným
   rollback artifactem, kontrolou původního hashe a následným readbackem.
3. Ověřit *oba* WP `content.raw` a veřejný HTML text. Tento nový public-only
   watch pak poskytne nezávislou kontrolu; dva zelené veřejné výsledky samy
   nedokazují opravu autentizovaného stavu ani affiliate konverzi.

Meze: Nejde o úplný scan 11 814 článků ani o náhradu návštěvnického testu
v Chrome. Tři dříve karantenizované WP ID 11945/11595/11264 zůstávají
samostatně evidovanými případy; zde jejich stav neodvozujeme.
