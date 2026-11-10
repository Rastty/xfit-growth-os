# XFIT — soukromé ověření provizí z Affial CSV

**Účel:** oddělit skutečně *schválené provize z doloženého exportu* od prokliků, čekajících provizí a **skutečně vyplacených peněz**. Není potřeba aktivní GA4 plugin, aby šly ověřit provize již zaznamenané samotnou sítí Affial. Bez exportu však zůstává obchodní výsledek \`UNKNOWN\`.

## Co Affial skutečně potvrzuje

- Affial poskytuje v části **Reporty → Provize** filtrování a export CSV. Statusy podle Affial: **Nerozhodnuto**, **Povoleno**, **Zamítnuto**.
- \`Povoleno\` znamená schválenou provizi; **nikoli doklad, že peníze dorazily na účet**. Vyplacení probíhá zvlášť v části **Platby** s bankovním převodem.
- Affial podle vlastního návodu eviduje a vyplácí provize v **EUR**, ne v CZK. Neprovádíme automatický přepočet kurzem.

Oficiální zdroje: https://www.affial.com/navod-affial/ a https://help.affial.com/article/10-vyplata.

## Jednorázový bezpečný postup

1. Přihlaste se do svého Affial účtu. V **Reporty → Provize** vyberte konkrétní kampaň NaMaximum, období a přidejte do tabulky **stabilní unikátní ID transakce**, status a částku provize. Pokud je to možné, přidejte měnu. Exportujte do CSV.
2. Soubor neukládejte do veřejného GitHub repozitáře, GitHub Actions artefaktu, WordPressu ani jiné veřejné složky. Obsahuje citlivá obchodní data a případně údaje zákazníků. Uložte jej mimo repozitář, například do soukromého adresáře vlastního počítače.
3. Spusťte **lokálně** (z kořene repozitáře) následující příkaz. Názvy sloupců a přesný název kampaně upravte podle skutečného exportu; níže jsou **pouze příklady**, nikoli ověřené hlavičky vašeho účtu:

\`\`\`bash
python -m scripts.xfit_affial_csv_reconcile \
  --file /soukroma/cesta/affial-provize.csv \
  --campaign "NaMaximum.cz" \
  --campaign-column "Campaign" \
  --status-column "Status" \
  --amount-column "Commission" \
  --transaction-id-column "Transaction ID" \
  --expected-currency EUR
\`\`\`

Pokud export obsahuje i sloupec měny, přidejte například \`--currency-column "Currency"\` (použijte **skutečný** název). Bez sloupce měny je EUR pouze explicitním potvrzením operátora, nikoli nezávisle ověřeným údajem CSV. Pokud unikátní ID transakce není v exportu dostupné, **nenahrazujte jej číslem řádku** — nejprve upravte sloupce exportu.

## Co kontrola skutečně provede

- Čte **jen lokální CSV**, bez síťových požadavků, WordPress zápisů, GA4 událostí či partnerských prokliků.
- Filtruje pouze **přesný zadaný název kampaně**, odmítá neznámé statusy, jiné měny, chybějící či duplicitní transakční ID, neplatné/zaokrouhlovací částky, nejednoznačné sloupce a příliš velké soubory.
- Vypíše pouze souhrnné počty a částky schválených, čekajících a zamítnutých provizí **v rozsahu dodaného CSV**. Nezapisuje ani netiskne objednávky, IP, e-maily, odkazy, affiliate ID, názvy kampaní ani jednotlivé finanční řádky.
- Vždy reportuje \`paid_commission_eur: UNKNOWN_REQUIRES_SEPARATE_PAYMENT_EVIDENCE\` a \`all_time_revenue: UNKNOWN\`. Úplnost časového okna z dodaného CSV nelze prokázat jen jeho obsahem.

**Ověřená výplata** vyžaduje samostatný doklad z Affial **Platby** nebo bankovní/fakturační záznam — nikdy ji neodvozujte ze statusu \`Povoleno\`. Klik z GA4 zase nikdy není objednávka.

## Testy a bezpečnost

\`\`\`bash
python -m unittest tests/test_affial_csv_reconcile.py -v
\`\`\`

Syntetické testy nemají skutečná data; ověřují české/anglické statusy i PAP kódy, oddělení kampaní, správnou měnu, desetinné částky, duplicitní ID, kontrolu velikosti a žádný výpis osobních údajů. Nepouštějte skutečné zákaznické CSV do veřejného CI.
