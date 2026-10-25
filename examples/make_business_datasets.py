"""Generate fictional upload datasets: python -m examples.make_business_datasets."""
import argparse
import base64
from collections import Counter
import csv
from datetime import date, timedelta
import json
from pathlib import Path
import random
import shutil
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from backend.ledger import import_invoices, ledger_summary


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'examples' / 'demo_datasets'
PUBLIC = ROOT / 'frontend' / 'public' / 'demo-datasets'
FIELDS = ['invoice_id', 'customer_id', 'customer_name', 'segment', 'amount',
          'issue_date', 'due_date', 'status', 'received_amount', 'paid_date', 'currency']
PROFILES = [
    dict(slug='01_textile_wholesale', code='TEX', title='Textile wholesale',
         customers=10, history=10, open_each=4, amounts=(25000, 150000), terms=30,
         patterns=[('small', 4, 7), ('corporate', 28, 12), ('government', 65, 20)],
         cash=150000, floor=75000, payroll=220000, rent=35000, emi=25000,
         supplier=180000, sales=450000, noise=20,
         purpose='Mixed fast and slow payers, aging buckets, partial collections and customer-delay scenarios.'),
    dict(slug='02_it_services', code='ITS', title='IT services',
         customers=8, history=12, open_each=3, amounts=(30000, 180000), terms=30,
         patterns=[('small', 2, 6), ('corporate', 14, 8), ('government', 40, 15)],
         cash=600000, floor=150000, payroll=360000, rent=45000, emi=18000,
         supplier=60000, sales=650000, noise=12,
         purpose='A larger starting buffer and service retainers; test an extra expense or lower future sales.'),
    dict(slug='03_construction_supplies', code='CON', title='Construction supplies',
         customers=12, history=8, open_each=4, amounts=(15000, 90000), terms=45,
         patterns=[('corporate', 45, 20), ('small', 22, 15), ('government', 75, 20)],
         cash=100000, floor=100000, payroll=260000, rent=50000, emi=65000,
         supplier=350000, sales=550000, noise=25, concentration=True,
         purpose='One major contractor dominates receivables; compare delaying that customer with a smaller one.'),
    dict(slug='04_fmcg_distribution', code='FMC', title='FMCG distribution',
         customers=18, history=12, open_each=6, amounts=(5000, 40000), terms=14,
         patterns=[('small', 3, 5), ('small', 9, 6), ('corporate', 20, 10)],
         cash=200000, floor=80000, payroll=150000, rent=40000, emi=30000,
         supplier=240000, sales=800000, noise=18,
         purpose='More invoices, smaller ticket sizes, short credit terms and frequent partial receipts.'),
    dict(slug='05_packaging_manufacturing', code='PKG', title='Packaging manufacturing',
         customers=15, history=10, open_each=4, amounts=(20000, 140000), terms=30,
         patterns=[('corporate', 35, 14), ('small', 12, 9), ('government', 60, 20)],
         cash=250000, floor=120000, payroll=300000, rent=60000, emi=85000,
         supplier=450000, sales=700000, noise=22,
         purpose='Corporate receivables against raw-material bills and equipment EMIs; test supplier terms.'),
    dict(slug='06_logistics_services', code='LOG', title='Logistics services',
         customers=11, history=10, open_each=4, amounts=(10000, 95000), terms=30,
         patterns=[('small', 8, 10), ('corporate', 30, 22), ('government', 55, 25)],
         cash=175000, floor=90000, payroll=240000, rent=25000, emi=110000,
         supplier=160000, sales=500000, noise=30,
         purpose='Variable collection timing and fleet EMIs; test an unexpected vehicle-repair expense.'),
    dict(slug='07_staffing_agency', code='STA', title='Staffing agency',
         customers=10, history=10, open_each=4, amounts=(50000, 220000), terms=30,
         patterns=[('corporate', 35, 15), ('small', 18, 9), ('government', 65, 20)],
         cash=125000, floor=100000, payroll=700000, rent=40000, emi=15000,
         supplier=100000, sales=900000, noise=15,
         purpose='Payroll is due before many client receipts; inspect shortage drivers and collection priority.'),
    dict(slug='08_new_business_no_history', code='NEW', title='New business without payment history',
         customers=8, history=0, open_each=3, amounts=(10000, 65000), terms=30,
         patterns=[('small', 10, 8), ('corporate', 25, 12), ('government', 60, 20)],
         cash=80000, floor=50000, payroll=90000, rent=20000, emi=10000,
         supplier=70000, sales=150000, noise=25,
         purpose='No settled invoices: demonstrate segment fallback and limited evidence rather than a trained personal model.'),
]


def invoice_rows(profile, as_of, rng):
    rows = []
    for index in range(profile['customers']):
        cid = f"{profile['code']}-C{index+1:02}"
        segment, average, spread = profile['patterns'][index % len(profile['patterns'])]
        customer_name = f"Demo {profile['title']} Buyer {index+1:02}"
        multiplier = 12 if profile.get('concentration') and index == 0 else 1

        def amount():
            lower, upper = profile['amounts']
            return rng.randrange(lower, upper+1, 500)*multiplier

        def add(identifier, value, due, *, paid=None, received=0):
            terms = max(profile['terms'], (due-as_of).days+7)
            rows.append(dict(invoice_id=identifier, customer_id=cid, customer_name=customer_name,
                segment=segment, amount=value, issue_date=(due-timedelta(days=terms)).isoformat(),
                due_date=due.isoformat(), status='paid' if paid else 'open', received_amount=received,
                paid_date=paid.isoformat() if paid else '', currency='INR'))

        history = profile['history']
        if history and index == profile['customers']-1:
            history = 0  # A new customer in an otherwise established business.
        elif history and index == profile['customers']-2:
            history = 2  # A customer with insufficient personal history.
        anchor = max(35, average+spread+10)
        for number in range(history):
            due = as_of-timedelta(days=anchor+28*(history-1-number)+rng.randrange(0, 4))
            delay = max(-min(7, profile['terms']-1), average+rng.randint(-spread, spread))
            value = amount()
            add(f"DEMO-{cid}-H{number+1:03}", value, due,
                paid=due+timedelta(days=delay), received=value)

        offsets = [-105, -70, -45, -15, 0, 7, 18] if profile['history'] else [-14, -5, 0, 7, 14]
        for number in range(profile['open_each']):
            due = as_of+timedelta(days=offsets[(index+number*2) % len(offsets)])
            value = amount()
            received = value*(25 if number % 2 == 0 else 50)//100 if (index+number) % 4 == 0 else 0
            add(f"DEMO-{cid}-O{number+1:03}", value, due, received=received)
    return sorted(rows, key=lambda row: (row['issue_date'], row['invoice_id']))


def setup_values(profile, as_of):
    def obligation(identifier, name, value, day, category):
        return dict(id=identifier, name=name, amount=value, frequency='monthly', day_of_month=day, category=category)

    return dict(synthetic=True, name=f"Demo {profile['title']} (Synthetic)", as_of=as_of.isoformat(),
        opening_cash=profile['cash'], safety_floor=profile['floor'],
        obligations=[obligation('demo-payroll', 'Payroll', profile['payroll'], 1, 'salary'),
                     obligation('demo-rent', 'Rent', profile['rent'], 5, 'rent'),
                     obligation('demo-emi', 'EMI', profile['emi'], 10, 'loan'),
                     obligation('demo-tax', 'Tax provision (illustrative date)', 15000, 20, 'tax')],
        supplier_bills=[dict(id=f'demo-supplier-{number+1}', supplier=f'Demo Supplier {number+1}',
            amount=profile['supplier']*(2 if number == 0 else 1)//3,
            due_date=(as_of+timedelta(days=3 if number == 0 else 17)).isoformat(),
            is_msme=number == 0, status='open') for number in range(2)],
        monthly_sales=profile['sales'], terms_days=profile['terms'], monthly_noise_pct=profile['noise'])


def validate_upload(path, setup):
    # Pure parsing only: no signup, database writes, or modifications to an account.
    parsed = import_invoices(path.name, base64.b64encode(path.read_bytes()).decode(),
        setup['name'], setup['as_of'], setup['opening_cash'], setup['safety_floor'])
    return parsed


def write_guide(profile, setup, summary):
    lines = [f"# {setup['name']}", '', 'All companies, invoices and payment patterns are fictional.', '',
        profile['purpose'], '', f"Invoices: {summary['invoices']}. Customers: {summary['customers']}. "
        f"Paid: {summary['paid']}. Open: {summary['open']}, including {summary['partial']} partial receipts.", '',
        '## Set up and import', '',
        f"1. Create a separate demo account. Business name: **{setup['name']}**.",
        f"2. Use observation date **{setup['as_of']}**, available cash **INR {setup['opening_cash']:,}**, "
        f"and minimum cash buffer **INR {setup['safety_floor']:,}**.",
        f"3. Open **Invoices & cash > Import data**, upload `{profile['slug']}.csv` or "
        f"`{profile['slug']}.xlsx`, and enter the same setup values.",
        '4. Confirm replacement only in the intended demo workspace.', '',
        'Available cash already includes previous receipts; do not record historical receipts again. '
        'Import replaces invoices, receipt logs, customer relationship context, supplier bills and obligations. '
        'It starts future sales at zero. Saved scenario assumptions can become obsolete after an import.', '',
        '## Add these forecast inputs manually after the invoice import', '',
        'Open **Expenses & obligations > Manage expenses & plan** or '
        '**Invoices & cash > Outflows & sales**, then enter:', '',
        '| Recurring expense | Category | INR per month | Day of month |',
        '| --- | --- | ---: | ---: |']
    for row in setup['obligations']:
        lines.append(f"| {row['name']} | {row['category']} | {row['amount']:,} | {row['day_of_month']} |")
    lines += ['', 'The tax provision date is illustrative, not a verified statutory deadline.', '',
              '| Supplier | INR | Due date | Micro/small enterprise |', '| --- | ---: | --- | --- |']
    for row in setup['supplier_bills']:
        lines.append(f"| {row['supplier']} | {row['amount']:,} | {row['due_date']} | {'Yes' if row['is_msme'] else 'No'} |")
    lines += ['', f"Future monthly sales: **INR {setup['monthly_sales']:,}**. Payment terms: "
        f"**{setup['terms_days']} days**. Sales uncertainty: **{setup['monthly_noise_pct']}%**.", '',
        'These future sales mean additional invoices not already present in the uploaded file. '
        'The companion `_setup.json` is a reference for manual entry, not an uploadable invoice file.', '',
        '## What to show', '',
        '- Ledger: received versus expected money, partly paid invoices, and aging.',
        '- Customers: different payment patterns and customers with sparse/no history.',
        '- Forecast: cash uncertainty after adding the outflow/sales inputs above.',
        '- Scenario planner: choose a specific customer and test a payment delay.', '',
        'Synthetic rows exercise the pipeline; they do not establish real-world prediction accuracy. '
        'Specific shortage probabilities depend on the current model and entered assumptions.', '']
    (DIRECTORY / f"{profile['slug']}_guide.md").write_text('\n'.join(lines), encoding='utf-8')


def make_files(as_of):
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    catalog = []
    for index, profile in enumerate(PROFILES):
        rows = invoice_rows(profile, as_of, random.Random(500+index))
        setup = setup_values(profile, as_of)
        csv_path = DIRECTORY / f"{profile['slug']}.csv"
        with csv_path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        xlsx_path = DIRECTORY / f"{profile['slug']}.xlsx"
        pd.DataFrame(rows, columns=FIELDS).to_excel(xlsx_path, index=False, sheet_name='Invoices')
        business = validate_upload(csv_path, setup)
        assert validate_upload(xlsx_path, setup) == business, 'CSV/Excel imports must agree'
        counts = Counter(row['status'] for row in business['invoices'])
        summary = dict(file=csv_path.name, business_name=setup['name'], invoices=len(rows),
            customers=len(business['customers']), paid=counts['paid'], open=counts['open'],
            partial=sum(0 < row['received_amount'] < row['amount'] for row in rows),
            as_of=setup['as_of'], opening_cash=setup['opening_cash'], safety_floor=setup['safety_floor'],
            outstanding=ledger_summary(business)['outstanding'], purpose=profile['purpose'])
        assert summary['open'] and summary['partial']
        assert (summary['paid'] == 0) == (profile['history'] == 0)
        if profile.get('concentration'):
            assert ledger_summary(business)['concentration'][0]['share'] > 0.3
        (DIRECTORY / f"{profile['slug']}_setup.json").write_text(json.dumps(setup, indent=2)+'\n', encoding='utf-8')
        write_guide(profile, setup, summary)
        catalog.append(summary)
        shutil.copyfile(csv_path, PUBLIC / csv_path.name)
        shutil.copyfile(xlsx_path, PUBLIC / xlsx_path.name)

    (DIRECTORY / 'manifest.json').write_text(json.dumps(catalog, indent=2)+'\n', encoding='utf-8')
    lines = ['# CashFlow upload datasets - synthetic', '',
        f"Eight fictional businesses, observation date **{as_of}**. All money is whole INR. "
        'No personal or real customer data is included. No external dataset was copied.', '',
        'Choose one CSV **or** its equivalent Excel file for each demo account. Do not upload the ZIP, '
        'manifest, guides or setup JSON files into the invoice importer.', '',
        '| Dataset | Invoices | Paid | Open | Partial within open | Available cash INR | Safety floor INR |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in catalog:
        lines.append(f"| {row['file']} | {row['invoices']} | {row['paid']} | {row['open']} | {row['partial']} | "
                     f"{row['opening_cash']:,} | {row['safety_floor']:,} |")
    lines += ['', '## Upload', '',
        '1. Create a new demo login and finish business setup with the chosen business name, '
        'observation date, available cash and safety floor. Use the same values during import.',
        '2. Open **Invoices & cash > Import data**, select a CSV or Excel file and import it.',
        '3. Follow that dataset\'s `_guide.md` to enter recurring expenses, supplier bills and future sales. '
        'The `_setup.json` contains the same reference values; JSON plan upload is not implemented.', '',
        'Import replaces the current workspace invoices, receipt log, relationship context and outflow plan. '
        'Use one demo login per business if you want to keep them separate. Historical receipts are '
        'already reflected in the starting cash figure; do not add them to cash again.', '',
        'Invoice-only imports have no expenses and zero future sales. Add the supplied plan values '
        'before assessing liquidity shortages or testing sales/supplier scenarios. Future sales '
        'are additional unissued business, not the invoices already uploaded.', '',
        'Datasets 1-7 include paid history, a customer with two settled invoices, and a customer '
        'with no settled invoices. Dataset 8 intentionally has no paid history and demonstrates '
        'segment fallback. Synthetic data validates app behaviour, not predictive accuracy.', '',
        'The tax provision dates are illustrative owner-entered schedules, not verified legal deadlines.', '',
        '## Regenerate for another observation date', '', 'From the repository root:', '',
        '```powershell', 'python -m examples.make_business_datasets --as-of 2026-10-25', '```', '',
        'The generator overwrites this dataset pack and its public download copies. It validates every '
        'CSV and Excel file using the app importer without creating accounts or modifying stored business data.', '']
    (DIRECTORY / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
    archive_path = DIRECTORY / 'cashflow_demo_datasets.zip'
    with ZipFile(archive_path, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(DIRECTORY.iterdir()):
            if path.suffix in ('.csv', '.xlsx', '.json', '.md'):
                archive.write(path, arcname=path.name)
    shutil.copyfile(archive_path, PUBLIC / archive_path.name)
    print(f"Created {len(catalog)} datasets / {sum(row['invoices'] for row in catalog)} invoices; "
          'validated all 16 CSV/Excel imports without database writes.')
    print(f'Observation date: {as_of}. Download archive: {archive_path}')
    for row in catalog:
        print(f"{row['file']}: {row['invoices']} invoices, {row['paid']} paid, {row['open']} open, {row['partial']} partial")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of', type=date.fromisoformat, default=date(2026, 10, 25))
    make_files(parser.parse_args().as_of)
