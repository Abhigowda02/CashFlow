# Jury demonstration invoice list — synthetic

All companies, invoices and payment patterns in these files are fictional.
They demonstrate application behaviour, not accuracy on real businesses.
No rows were downloaded or copied from an external dataset.

For eight additional businesses (1,126 invoices), use the
[business dataset pack](demo_datasets/README.md) or
[download all CSV/Excel files and setup guides](demo_datasets/cashflow_demo_datasets.zip).
These use the same invoice importer and include separate setup values for each business.

## Files

- `jury_invoices.csv`: ready to upload using the existing invoice importer.
- `jury_invoices.xlsx`: the same invoice rows in Excel format.
- `jury_setup.json`: reference values for manual setup, not an additional upload format.
- `make_jury_demo.py`: reproducible generator; Python command below.

There are 42 invoices, six customers, 30 fully paid invoices and 12 open invoices.
Two open invoices have partial receipts. Seven invoices are overdue, one is due
on the observation date, and four are future due. History includes early, punctual,
moderately late and very late settlements. Demo New Traders has no paid history,
so the Customers screen demonstrates segment fallback.

## Import for the demo

Use a separate demo account: import replaces the selected account's workspace,
receipt log, relationship context, obligations and supplier bills.

Open **Invoices & cash → Import data**, choose either invoice file and enter:

| Field | Value |
| --- | --- |
| Business name | Demo Textile Supplies (Synthetic) |
| Observation date | 2026-10-25 |
| Available cash | 100000 |
| Safety floor | 50000 |

Keep this observation date even if the calendar date is later, or regenerate
the files for a newer date. Earlier receipts are historical and already reflected
in the entered cash balance; do not record them again.

The invoice import initially has no obligations and zero future sales. Add the
following in **Expenses & obligations → Manage expenses & plan** before presenting
the forecast:

| Recurring expense | Category | Monthly INR | Day |
| --- | --- | ---: | ---: |
| Payroll | Salary & payroll | 180000 | 1 |
| Office rent | Rent | 30000 | 5 |
| Equipment EMI | EMI & loan | 25000 | 10 |
| Tax provision (demo date) | GST, TDS & taxes | 35000 | 20 |

The tax provision is an illustrative owner-entered schedule, not a legal deadline.

Add open supplier bills:

| Supplier | INR | Due date | Micro/small enterprise |
| --- | ---: | --- | --- |
| Demo Fabric Supplier | 85000 | 2026-10-28 | Yes |
| Demo Packaging Supplier | 45000 | 2026-11-06 | No |

Set expected monthly sales to **300000**, payment terms to **30 days**, and sales
uncertainty to **15%**. These are illustrative future assumptions. If future sales
remain zero, changing the sales percentage in the simulator will have no effect.

## Suggested five-minute presentation

1. **Invoice ledger:** show received history, overdue balances, and the two partly
   paid invoices `DEMO-O-003` and `DEMO-O-008`. Expected money is separate from cash.
2. **Customers:** compare Demo Fast Retail with Demo Institutional Buyer. The
   business has enough history to attempt its own survival fit; Demo New Traders
   shows segment fallback. Show probability dates as estimates, not promises.
3. **Expenses:** show monthly commitments totalling INR 270000 and the next due dates.
4. **Forecast:** select Survival model and discuss uncertainty and the safety floor.
   Figures depend on entered assumptions and the current implementation; do not
   memorise a shortage percentage as a real-world accuracy claim.
5. **Scenario planner:** delay a customer or add an expense. Compare the scenario
   against the baseline. With the sales assumption entered, a sales decrease also works.
6. **Relationship context:** mark Demo Repeat Textiles as strategic/repeat, record
   an open service issue, and select `DEMO-O-003` as disputed. In Recommended actions,
   show why cash priority and the recommended contact approach are separate.
7. **Optional receipt:** record a small new partial receipt dated 2026-10-25 on an
   outstanding invoice, showing that cash rises while its receivable falls. Importing
   the demo again resets this experiment and any relationship context.

## Regenerate dates

From the repository root:

```powershell
python -m examples.make_jury_demo --as-of 2026-10-25
```

This overwrites the example CSV, Excel and setup JSON only. It does not import
anything or change an account. Dates in `jury_setup.json` follow the chosen date;
the tables above describe the checked-in 2026-10-25 version.

## Public reference examples found during research

- [Vertex42 invoice tracker](https://www.vertex42.com/ExcelTemplates/invoice-tracker.html):
  a public Excel/Google Sheets tracker with customer lists and invoice aging.
- [Zoho Books receivables reports](https://www.zoho.com/in/books/help/reports/receivables.html):
  example invoice-detail and aging-report fields.

These are reference links, not the origin of the synthetic rows. Their spreadsheets
or reports need column mapping before use with this application's importer.
