# XFIT: pozorování první obrazovky a reklam — read-only

## Proč to měříme

Ve skutečném desktopovém prohlížeči 19. 11. 2026 byly na obou
produktových poradcích pozorovány velké horní reklamní rámce z
`pagead2.googlesyndication.com` (přibližně 124 px kreatin, 280 px whey při
výšce viewportu 936 px), nesouvisející reklamní návrhy blízko úvodu a
spodní cookie pruh o výšce 82 px. Podrobnosti a hranice pozorování jsou
v [UX issue #2](https://github.com/Rastty/xfit-growth-os/issues/2).
Stávající 375px QA testovalo obsah a interakce, ale nebylo možné z jeho
PASS vyvozovat, že první obrazovku nic nepřekrývá.

## Nový důkaz z produkčního Chromium QA

`tests/live_page_qa.cjs` nejprve otevře přesné existující URL při 375 × 812,
počká na běžné načtení a **před posunem na produktovou fotografii**
jednorázově změří:

- počet geometricky viditelných reklamních iframe Google v prvním viewportu;
- počet a maximální výšku širokých reklamních iframe zasahujících jeho horní
  okraj (px a procento výšky viewportu);
- výšku viditelného spodního cookie pruhu (px a procento viewportu);
- počáteční vertikální polohu prvního H1;
- omezené varovné kategorie `TALL_TOP_EDGE_GOOGLE_AD_FRAME`,
  `TALL_BOTTOM_COOKIE_BANNER` a `H1_BELOW_INITIAL_VIEWPORT`.

Prahy jsou diagnostické: horní reklamní rámec alespoň 15 % výšky,
spodní cookie pruh alespoň 10 % výšky, nebo H1 začínající až pod prvním
viewportem. Nejsou to právní ani konverzní limity.

Pořídí samostatný `creatine-first-screen.png` a `whey-first-screen.png` do
sedmidenního screenshot artefaktu `xfit-mobile-qa-screenshots`, pokud to
prohlížeč umožní. Dosavadní `*-mobile.png` screenshoty produktových karet
zůstávají. Agregované počty a stavy jsou ve výpisu workflow
`XFIT Mobile Content QA` pod `firstScreen` / `firstScreenScreenshot`.

## Interpretace a hranice

Jde o **jedno časové pozorování DOM geometrie**, nikoli o důkaz, že každý
návštěvník vidí reklamu, že došlo k reklamní impresi, kliknutí, schválenému
consentu, tržbě nebo poklesu konverze. Neznámý nebo nulový iframe není
potvrzením vypnuté reklamy. Dynamické reklamní formáty se mohou měnit podle
zařízení, času a cookie stavu. Žádný reklamní, affiliate ani cookie prvek
se nekliká. Do veřejných logů nejdou URL iframe, reklamní ID, produktové
identifikátory, affiliate parametry ani údaje návštěvníků.

Reklamní varování **neblokují** release. Existující obsahové, přístupnostní
a produktové kontroly nadále selhávají při skutečné regresi.

## Bezpečná následná akce

Správce reklamního účtu může v AdSense → Ads → Edit site → Auto ads settings
otestovat `Overlay formats` / `Anchor ads`, `Intent-driven formats` /
`Ad intents` nebo `Page exclusions` pro přesné dva poradce. Google podporuje
vyloučení jednotlivých stránek a nastavení formátů:

- https://support.google.com/adsense/answer/9305577?hl=en
- https://support.google.com/adsense/answer/9262311?hl=en-GB

Po schválené změně porovnat více mobilních QA běhů a skutečné, souhlasem
podmíněné ukazatele kvality návštěv. Úbytek reklamního prostoru **nemusí**
znamenat finanční zlepšení; AdSense ani affiliate výnos zde nejsou měřeny.
Při nežádoucím dopadu vrátit konkrétní AdSense nastavení; tento PR nemění
WordPress, reklamní účet ani produktové nabídky.
