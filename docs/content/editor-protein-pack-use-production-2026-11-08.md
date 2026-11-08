# Xfit.cz — bezpečné vydání výpočtu využití velkého balení proteinu

**Účel:** Vylepšit stávající průvodce na
https://xfit.cz/xfit-os-protein-guide/ (WP ID 25451) o praktický
výpočet, zda člověk vůbec využije větší balení před koncem
použitelnosti. Nenavádět ke koupi jen kvůli nižší ceně za 100 g.

## Schválený redakční podklad

Autonomní editor vytvořil PR #63 a soubor
`content/revisions/editor-protein-pack-use.json`, který zachycuje
pouze přesný původní list item a jednu nahrazující pasáž.
Příklad: 1 000 g ÷ 25 g = 40 modelových porcí;
při dvou použitích týdně 20 týdnů. **Nejde o doporučenou dávku,
frekvenci užívání, garanci trvanlivosti ani reálný produkt.**
Čtenář musí ověřit etiketu a podmínky po otevření,
a může zvolit menší balení nebo nekoupit nic.

## Technické hranice

- Scriptem se smí změnit **jen přesně tento jeden fragment**
  v živém článku WP 25451, bez změny statusu, názvu,
  URL, ostatních pasáží, affiliate odkazů nebo obrázků.
- Živý WordPress dokument je hlavním zdrojem pravdy; pokud
  obsahuje další dříve přidané sekce, zůstávají zachovány.
  Nikdy nepřepisovat WordPress zastaralým `content/ready` JSON.
- Před jediným zápisem se kontroluje pevná identita, status
  `publish`, autorská značka, přesný výskyt staré pasáže,
  absence nové pasáže, checksum, čas změny a redakční gate.
- Povinná záloha celého zdrojového HTML a SHA-256 se před
  zápisem uloží jako GitHub Actions artifact (90 dní).
- Je povolen nejvýše **jeden** `POST` s `content`.
  I při chybě odpovědi následuje pouze přihlášený GET
  a porovnání přesného výsledného hash.
- Nezávislý veřejný HTTP GET ověřuje novou konkrétní radu.
  Bez potvrzení se nevykazuje `PUBLIC_VERIFIED`.
- Schválené workflow má jen jednorázový `push` trigger
  při přidání vlastního YAML a případný ruční dispatch.
  Nemá nekonečný opakovaný publikační běh.

## Evidence výstupu

`PUBLIC_VERIFIED`: jedna skutečně upravená veřejná stránka,
nula nových článků. `ALREADY_APPLIED_NO_WRITE`: žádná nová
úprava. `UNRESOLVED_UNCHANGED`, `BLOCKED_MANUAL_REVIEW`
nebo `API_VERIFIED_PUBLIC_STALE`: netvrdit úspěšnou publikaci.

## Rollback

V GitHub Actions vyhledat zálohu
`xfit-protein-pack-25451-rollback-<run_id>`, porovnat aktuální
WordPress obsah, a pouze při nezměněném pozdějším stavu
vrátit zálohovaný fragment prostřednictvím autorizovaného
a opět verifikovaného WordPress zápisu. Neprovádět
bezmyšlenkovité obnovení celého článku po dalších úpravách.

**Nejsou potřebné WordPress pluginy, nové účty ani ruční
klikání na webu.**
