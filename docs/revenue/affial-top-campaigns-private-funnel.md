# XFIT — Affial Top kampane: soukromý důkaz kliků a provizí

Affial oficiálně uvádí export souhrnného reportu **TOP kampane** do CSV s položkami *Názov*, *Počet prodejů*, *Provize*, *Prokliky*. Skutečné hlavičky CSV se mohou lišit podle jazyka a nastavení.

Zdroje:
- https://www.affial.com/top-kampane-nova-funkcia-v-administracii/
- https://www.affial.com/navod-affial/
- https://help.affial.com/article/10-vyplata

## Postup

1. V Affial otevřete **Top kampane**, nastavte období a kampaň NaMaximum a exportujte CSV. Ověřte skutečný text názvu kampaně, sloupce a měnu (Affial eviduje provize v EUR).
2. CSV uložte jen do soukromé složky počítače, **nikdy do veřejného GitHubu, PR, issue ani Actions artefaktu**.
3. Lokálně z kořene repozitáře spusťte (Windows PowerShell, skutečné názvy mapujte podle CSV):

```powershell
python -m scripts.xfit_affial_top_campaigns `
  --file "C:\\Soukrome\\affial-top-campaigns.csv" `
  --campaign "NaMaximum" `
  --campaign-column "Názov" `
  --clicks-column "Prokliky" `
  --commission-count-column "Počet prodejů" `
  --commission-eur-column "Provize" `
  --expected-currency EUR
```

**Pozor:** Názvy jsou jen příklad z dostupné oficiální dokumentace, nikoli ověřená hlavička vašeho účtu. Pokud CSV obsahuje měnu, přidejte například parametr --currency-column "Měna"; bez něj je EUR jen explicitní tvrzení operátora, ne nezávislý důkaz z CSV.

## Co se smí vyvozovat

- network_report_clicks = **agregované prokliky kampaně**, nikoli ověřeně unikátní kliky ani návštěvníci XFIT.
- network_report_commission_transactions = počet provizních transakcí v reportu, nikoli nutně schválené objednávky.
- network_report_commission_total_eur = vykázaná suma v EUR v exportu; **bez statusů neznáme schválenou část**.
- site_attribution = **UNKNOWN**: stejnou síťovou kampaň mohou propagovat další weby nebo kanály. Bez přesného XFIT kanálu nejde výsledek přiřadit konkrétně webu.
- paid_commission_eur = **UNKNOWN**: pro potvrzení výplaty je nutný zvláštní doklad z Affial Platby nebo banky.
- time_window a source_completeness = **UNKNOWN**: z obsahu exportu nelze ověřit všechny použité filtry ani historickou úplnost.

Import úmyslně odmítá duplicitní řádek přesné kampaně, nejednoznačné / chybějící hlavičky, jiné měny, neplatné číselné údaje a neznámý formát. Neobsahuje síťové požadavky, zákaznická data, WordPress zápisy ani affiliate kliknutí. **Nevypočítává konverzní poměr** z neověřených kliků.

Pokud potřebujete skutečně **schválené / čekající / zamítnuté** provize, použijte samostatný CSV nástroj scripts.xfit_affial_csv_reconcile a průvodce docs/revenue/affial-private-commission-evidence.md.

Testy používají pouze smyšlené hodnoty: python -m unittest tests/test_affial_top_campaigns.py -v
