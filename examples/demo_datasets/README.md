# CashFlow upload datasets - synthetic

Eight fictional businesses, observation date **2026-10-25**. All money is whole INR. No personal or real customer data is included. No external dataset was copied.

Choose one CSV **or** its equivalent Excel file for each demo account. Do not upload the ZIP, manifest, guides or setup JSON files into the invoice importer.

| Dataset | Invoices | Paid | Open | Partial within open | Available cash INR | Safety floor INR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 01_textile_wholesale.csv | 122 | 82 | 40 | 10 | 150,000 | 75,000 |
| 02_it_services.csv | 98 | 74 | 24 | 6 | 600,000 | 150,000 |
| 03_construction_supplies.csv | 130 | 82 | 48 | 12 | 100,000 | 100,000 |
| 04_fmcg_distribution.csv | 302 | 194 | 108 | 27 | 200,000 | 80,000 |
| 05_packaging_manufacturing.csv | 192 | 132 | 60 | 15 | 250,000 | 120,000 |
| 06_logistics_services.csv | 136 | 92 | 44 | 11 | 175,000 | 90,000 |
| 07_staffing_agency.csv | 122 | 82 | 40 | 10 | 125,000 | 100,000 |
| 08_new_business_no_history.csv | 24 | 0 | 24 | 6 | 80,000 | 50,000 |

## Upload

1. Create a new demo login and finish business setup with the chosen business name, observation date, available cash and safety floor. Use the same values during import.
2. Open **Invoices & cash > Import data**, select a CSV or Excel file and import it.
3. Follow that dataset's `_guide.md` to enter recurring expenses, supplier bills and future sales. The `_setup.json` contains the same reference values; JSON plan upload is not implemented.

Import replaces the current workspace invoices, receipt log, relationship context and outflow plan. Use one demo login per business if you want to keep them separate. Historical receipts are already reflected in the starting cash figure; do not add them to cash again.

Invoice-only imports have no expenses and zero future sales. Add the supplied plan values before assessing liquidity shortages or testing sales/supplier scenarios. Future sales are additional unissued business, not the invoices already uploaded.

Datasets 1-7 include paid history, a customer with two settled invoices, and a customer with no settled invoices. Dataset 8 intentionally has no paid history and demonstrates segment fallback. Synthetic data validates app behaviour, not predictive accuracy.

The tax provision dates are illustrative owner-entered schedules, not verified legal deadlines.

## Regenerate for another observation date

From the repository root:

```powershell
python -m examples.make_business_datasets --as-of 2026-10-25
```

The generator overwrites this dataset pack and its public download copies. It validates every CSV and Excel file using the app importer without creating accounts or modifying stored business data.
