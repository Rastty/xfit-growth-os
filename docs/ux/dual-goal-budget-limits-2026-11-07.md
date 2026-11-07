# Xfit.cz — dvě rozhodovací priority uvnitř každého rozpočtu (2026-11-07)

## Konkrétní problém návštěvníka

Oba produktové poradce měly dvě cenové priority na úrovni CELÉHO výběru,
ale v rozbalovacích sekcích konkrétních cenových limitů ukazovaly
jen variantu s nejnižší cenou za 100 g prášku. Návštěvník, který
chce především zaplatit co nejméně nyní, tak nemohl přímo
z rozpočtové volby pokračovat ke svému správnému balení.

## Funkční změna na obou schválených stránkách

Systém zobrazí v každém limitu, pokud existují produkty:

- **Nejnižší celková cena balení**: min `(price_czk, price_per_100g, card_index)`.
- **Nejnižší cena za 100 g prášku**: min `(price_per_100g, price_czk, card_index)`.

Každá možnost je označená a má cenu celého balení, gramáž,
cenu za 100 g prášku a odkaz výhradně na již přítomnou,
ověřenou kartu `#xfit-offer-N` na téže stránce.
Není vytvořen žádný nový externí affiliate odkaz.

Pokud oba cíle vyhrají na stejném balení, objeví se jen
**jediný odkaz a výslovné vysvětlení**, nikoli duplicitní tlačítka.
Pokud se do limitu nevejde nic, systém pravdivě uvede, že
v rámci tohoto přehledu nabídka neexistuje, a netlačí ke
zvyšování limitu nebo koupi.

Native `details/summary`: funguje bez JS, neměří zdravotní
odpovědi, nepoužívá cookies ani novou WordPress infrastrukturu.
Pořadí komerčních karet ani jejich affiliate identifikátory
se nemění. Cena za 100 g **whey prášku** není cena za 100 g
čistých bílkovin; cena za 100 g **kreatinového prášku**
není laboratorní analýza čistoty. Údaje jsou výhradně z
časově kontrolovaného katalogu NaMaximum.

## Kvalita a rollback

- Regresní testy pokrývají rozdílné vítěze, stejného vítěze,
  rovnost jednotkových cen, více rozpočtů, chybějící produkty,
  neplatné ceny a duplicitní nabídky.
- Mobilní Chrome na 375px testuje všech osm existujících URL,
  obě cenové priority, platnost kotvy, nepřítomnost nových
  externích odkazů, klávesnicové ovládání a nepřetékání.
- Oba stávající live workflow se spustí změnou
  `scripts/xfit_budget_choices.py`. Produkční `post_id`
  25455 a 25456; před zápisem čerstvý feed, credential gate,
  redakční validace; po zápisu WP API readback a veřejná stránka.
- Rollback: revert změny pomocného souboru, opět spustit
  oba schválené WordPress publikační běhy a ověřit public readback.

**Žádné nové pluginy, administrátorské úkony ani tvrzení
o skutečných proklikách, objednávkách a provizích.**
