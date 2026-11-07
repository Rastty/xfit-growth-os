# Xfit — odolnost cenového katalogu vůči NaN, Infinity a chybným gramážím

## Proč

V původním feed ingestu se cena převáděla přes `float`, ale
běžná kontrola `price <= 0 or price > 1000000` nevylučuje
`NaN`, protože každé její srovnání s číslem je nepravdivé.
Neplatná položka by mohla skončit v normalizovaném katalogu
jako neportabilní JSON hodnota a později zablokovat celý
autorizovaný publikační běh nebo narušit pořadí nabídek.

## Co se mění

- `parse_price` v importeru přijímá pouze řetězcové, konečné,
  kladné ceny v CZK do 1 milionu. Odmítá NaN, Infinity,
  zaokrouhlenou nulu, absurdně dlouhé nebo nečíselné vstupy.
- `select_offers` kontroluje výstup i samostatně: není-li
  částka konečná, kladná a ve schváleném rozmezí, produkt
  se nezařadí. To chrání i před libovolným historickým
  nebo ručně vytvořeným katalogem.
- `mass_grams` ignoruje extrémně dlouhé nebo nevalidní
  číselné řetězce a nepřepočítává poškozená čísla
  na gramáž produktu.
- Neplatné produktové položky se **přeskočí**;
  ostatní ověřené nabídky zůstávají použitelnými kandidáty.
  Pokud po kontrole není dost vhodných produktů,
  stávající publikační gate změny odmítne — žádné
  náhradní/fiktivní ceny ani hazardní odhady.

## Ověření

Regresní testy pokrývají XML s jednou správnou a dvěma
neplatnými nabídkami, NaN, ±Infinity, extrémní exponenty,
nulové ceny, nepřiměřenou hmotnost, chybný cenový limit
i řazení zbývajících ověřených produktů.

Změny pomocných skriptů a testů automaticky spouštějí
oba již autorizované WordPress publikační workflow,
které ověří čerstvý XML zdroj, ownership obou kanonických
článků a veřejný readback. Samotný fix **nemusí**
změnit žádnou veřejnou stránku, pokud feed obsahuje
pouze platné nabídky; v takovém případě je korektní
stav `unchanged_public_verified`.

Žádné nové pluginy, tracking, affiliate URL ani změny
produktových rankingů nad stejnými platnými daty.

Rollback: revert validace plus oba workflow path filtry;
ověřit feed testy a následný safe WP readback.
