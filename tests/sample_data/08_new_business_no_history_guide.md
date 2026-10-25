# Demo New business without payment history (Synthetic)

All companies, invoices and payment patterns are fictional.

No settled invoices: demonstrate segment fallback and limited evidence rather than a trained personal model.

Invoices: 24. Customers: 8. Paid: 0. Open: 24, including 6 partial receipts.

## Set up and import

1. Create a separate demo account. Business name: **Demo New business without payment history (Synthetic)**.
2. Use observation date **2026-10-25**, available cash **INR 80,000**, and minimum cash buffer **INR 50,000**.
3. Open **Invoices & cash > Import data**, upload `08_new_business_no_history.csv` or `08_new_business_no_history.xlsx`, and enter the same setup values.
4. Confirm replacement only in the intended demo workspace.

Available cash already includes previous receipts; do not record historical receipts again. Import replaces invoices, receipt logs, customer relationship context, supplier bills and obligations. It starts future sales at zero. Saved scenario assumptions can become obsolete after an import.

## Add these forecast inputs manually after the invoice import

Open **Expenses & obligations > Manage expenses & plan** or **Invoices & cash > Outflows & sales**, then enter:

| Recurring expense | Category | INR per month | Day of month |
| --- | --- | ---: | ---: |
| Payroll | salary | 90,000 | 1 |
| Rent | rent | 20,000 | 5 |
| EMI | loan | 10,000 | 10 |
| Tax provision (illustrative date) | tax | 15,000 | 20 |

The tax provision date is illustrative, not a verified statutory deadline.

| Supplier | INR | Due date | Micro/small enterprise |
| --- | ---: | --- | --- |
| Demo Supplier 1 | 46,666 | 2026-10-28 | Yes |
| Demo Supplier 2 | 23,333 | 2026-11-11 | No |

Future monthly sales: **INR 150,000**. Payment terms: **30 days**. Sales uncertainty: **25%**.

These future sales mean additional invoices not already present in the uploaded file. The companion `_setup.json` is a reference for manual entry, not an uploadable invoice file.

## What to show

- Ledger: received versus expected money, partly paid invoices, and aging.
- Customers: different payment patterns and customers with sparse/no history.
- Forecast: cash uncertainty after adding the outflow/sales inputs above.
- Scenario planner: choose a specific customer and test a payment delay.

Synthetic rows exercise the pipeline; they do not establish real-world prediction accuracy. Specific shortage probabilities depend on the current model and entered assumptions.
