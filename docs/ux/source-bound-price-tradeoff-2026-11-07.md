# Xfit: skutečný finanční rozdíl mezi levným balením a levnými 100 g (7. 11. 2026)

## Problém a návrh

Kreatinový a proteinový poradce už nabízely nezávislé volby
„nejnižší výdaj při nákupu“ versus „nejnižší cena za 100 g prášku“,
ale **bez vyčíslení rozdílu**. Uživatel musel přeskakovat mezi
kartami a sám dopočítat, kolik zaplatí navíc za balení
s nižší jednotkovou cenou.

Nyní v úvodu obou poradenských stránek pro **skutečně vybrané
ověřené produkty** zobrazujeme:

- konkrétní název balení, cenu celého balení, gramáž a Kč/100 g
  u nejlevnějšího balení,
- stejný údaj u balení s nejlepší jednotkovou cenou,
- rozdíl vstupního výdaje v Kč a rozdíl ceny na 100 g,
- upozornění, že jednotková cena není zaručená celková
  úspora; záleží na spotřebovaném množství.

Pokud vyhraje stejné balení v obou kategoriích, v HTML
se objeví **jen jeden odkaz** a jednoduché vysvětlení.

## Matematika a omezení

Oba vítězové se určují nezávisle z **již zobrazovaných** karet:

- minimální celková cena `(price_czk, unit, card_position)`,
- minimální cena/100 g `(unit, price_czk, card_position)`.

`extra_paid = unit_winner.total - upfront_winner.total`

`unit_difference = upfront_winner.price_per_100g - unit_winner.price_per_100g`

Ceny a gramáže musí pocházet z ověřeného NaMaximum XML,
nikoli z marketingového názvu výrobku nebo domnělé slevy.
Vstupní data přísně odmítají NaN/Infinity, chybnou
gramáž, duplicitní identitu a neplatné či chybějící ceny.

Důležité: u whey jde o **hmotnost prášku**, nikoli cenu
skutečných bílkovin; u kreatinu o **hmotnost balení**,
nikoli laboratorně potvrzenou čistotu. Pořadí se
nezměnilo, nepřibyly produkty ani affiliate URL.
Interní odkazy vedou pouze na stávající `#xfit-offer-N`.

## Release a testy

- `scripts/xfit_price_tradeoff.py` deterministický modul;
  zapojený do obou existujících produktových průvodců.
- `tests/test_price_tradeoff.py` přesná aritmetika,
  odlišný a shodný vítěz, HMTL escaping, fail closed a
  konečné karty obou průvodců.
- Mobilní Chromium 375px ověřuje právě dvě různé
  vnitřní kotvy nebo jeden vítězný odkaz, správně
  lokalizovanou Kč částku a nulové nové merchant linky.
- Při merge stávající autentizovaná GitHub Actions
  workflow publikují do WordPress post IDs 25455/25456
  a vyžadují `api_accepted` + `live_verified`.
- Rollback: revert modulu a jeho volání, schválené
  WP release opakovat a ověřit veřejnou stránku.

**Žádné nové WordPress pluginy, cookies, tracking,
obcházení oprávnění, testovací affiliate kliky ani tvrzení
o zisku.**
