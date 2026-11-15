# XFIT: dostupnost při výběru kreatinu a whey — 15. 11. 2026

## Defekt / přínos

Výběrové karty obou poradců pracovaly pouze s cenou. XML již obsahovalo
`DELIVERY_DATE` nebo neformální `AVAILABILITY`, ale návštěvník neviděl, zda je
dodací údaj známý. To může vést k prokliku na dlouho nedostupné zboží.

Oficiální základní specifikace: https://sluzby.heureka.cz/napoveda/xml-feed/.
`DELIVERY_DATE=0` znamená v základním katalogu „skladem“, `1–7` délku
expedice v dnech, `8+` delší čekání, datum označuje předobjednávku.
Základní XML není živá skladová evidence; dostupnostní XML může mít přednost.

## Změna

- Na ingestu oddělit dva zdrojové tagy, aby neznámá textová hodnota
  `AVAILABILITY` nikdy nebyla falešně číselným `DELIVERY_DATE`.
- Vyřadit pouze výslovně nedostupné nabídky, předobjednávky a uvedenou
  expedici delší než 7 dní. Neznámou dostupnost **nevydávat za skladem**,
  ale výslovně označit přímo na produktové kartě.
- U každé affiliate karty uvést zdrojový stav s výhradou k aktuálnosti,
  bez cenových/objednávkových příslibů.
- Nezměnit affiliate URL, výši provize, zdravotní doporučení ani pořadí
  stávajících způsobilých produktů podle ceny. Na každý automatický refresh
  přidat izolovanou archivní kopii celého původního WP HTML před možným POST.

## Nasazení a bezpečnost

Změny v `scripts/xfit_whey_guide.py`, `scripts/xfit_creatine_guide.py`
spouštějí jejich **existující** samostatné WordPress workflow na `main`.
Pokud po vyřazení nedostupných položek zůstane méně než dvě odlišné
produktové rodiny, release skončí bez zápisu; starou stránku je pak nutné
samostatně přezkoumat kvůli starým nabídkám. Žádné automatické opakování
nejistého POSTu.

Před každým možným zápisem ukládá `xfit_adviser_backup.py` kompletní
autentizovaný původní body a hash, jako run-specific GitHub Actions artefakt
s retenční dobou 7 dní. Artefakt nevkládá do veřejného commitu přístupové
údaje, XML ani tajný URL token. Při opravě se původní obsah obnovuje pouze
z přesně odpovídajícího `post_id` a původního hashe, nativním WordPress
REST API, po kontrole aktuálního postu a **nikdy** slepým opakováním zápisu.

## Důkaz

Kód + unit testy + reálný mobilní Chrome pro oba poradce (375 px);
`PUBLIC_VERIFIED` až po autentizovaném WP readbacku a veřejném GET.
Skutečné dnešní skladové množství, uskutečněné kliky, objednávky a
vyplacené provize: **UNKNOWN** bez samostatných důkazů.
