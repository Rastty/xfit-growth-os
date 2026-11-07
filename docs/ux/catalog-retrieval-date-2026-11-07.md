# Xfit: skutečné datum načtení produktových cen (2026-11-07)

## Proč

Produktové články už návštěvníkovi ukazují ceny balení, cenu za 100 g
a cenu modelové porce. Ale bez kontextu, **kdy** je Xfit z produktového
XML katalogu načetl, může čtenář pokládat cenu za aktuálně platnou.
To nesmíme tvrdit bez nezávislé kontroly obchodníka.

## Nové chování

Oba živí poradci (*kreatin*, *syrovátkový protein*) nyní těsně na
začátku zobrazují větu:

> Kdy jsme data nabídky načetli: 7. 11. 2026 (produktový XML katalog
> NaMaximum.cz). Datum označuje načtení katalogu, nikoli okamžik změny
> ceny u prodejce. Aktuální cenu, složení a dostupnost ověřte v obchodě.

*Datum je příklad formátu, nikoli ručně nastavená hodnota.* Ve skutečnosti
pochází výhradně z `fetched_at_utc` privátního normalizovaného feedu
a je převedeno do časové zóny Europe/Prague. Viditelný HTML obsah
obsahuje **pouze datum**, ne čas jednotlivých požadavků, tokeny,
produktová ID ani affiliate parametry.

Produkční CLI obou poradců odmítne publikaci, pokud neexistuje
validní čas načtení v UTC, je z budoucnosti o více než pět minut
nebo je starší než čtyři hodiny. Při chybě **žádný WordPress POST**.
Synthetic unit test fixtures bez timestampu mohou stále vygenerovat
neveřejnou ukázku, ale nesmějí projít produkčním CLI.
Dva stejné importy během stejného místního dne mají totožný
viditelný datový údaj; díky tomu se příspěvek nebude měnit
jen kvůli sekundám. Nový den přidá novou informaci o načtení
zdrojových dat a schválený každodenní release ji může aktualizovat.

Důležitý rozdíl: `fetched_at_utc` potvrzuje, **kdy my jsme zdroj
stáhli**, ale ne to, kdy obchodník změnil cenu, prodeje, sklad
nebo kdy Affial připsal provizi. Není to audit aktuální dostupnosti
ani důkaz výnosu.

## Ověření a rollback

- Unit testy: chybějící, naivní, lokální a budoucí timestamp;
  přestárlý feed; půlnoční přechod do SEČ; redakční výstup obou
  produktových poradců; stabilní datum při více bězích téhož dne.
- Produkční workflow nadále stahují reálný katalog ze zabezpečených
  Secrets, ověřují WordPress ownership a výsledný veřejný obsah.
- Mobilní Chrome ověřuje jedinou přítomnost vysvětlujícího
  data u obou poradenských URL a stávající UX / CTA integrity.
- Nejbližší běh `XFIT Public Decision Funnel Freshness` dále
  porovnává obsah obou poradenských karet a affiliate odkazy.
- Rollback: revert pomocného modulu a obou volání, znovu spustit
  autorizovaný WP release. Při revertu se stav nejprve validuje.
