"""Generate synthetic invoice files: python -m examples.make_jury_demo --as-of 2026-10-25."""
import argparse
import csv
from datetime import date, timedelta
import json
from pathlib import Path
import random


def make_files(as_of):
    rng = random.Random(42)
    directory = Path(__file__).resolve().parent
    customers = [
        ('C101', 'Demo Fast Retail', 'small', [-3, 0, 2, 1, 3, 0]),
        ('C102', 'Demo Repeat Textiles', 'corporate', [7, 12, 9, 15, 11, 8]),
        ('C103', 'Demo Wholesale', 'corporate', [22, 28, 35, 30, 24, 32]),
        ('C104', 'Demo Institutional Buyer', 'government', [40, 55, 65, 45, 60, 52]),
        ('C105', 'Demo New Traders', 'small', []),
        ('C106', 'Demo Service Partners', 'small', [3, 5, 10, 7, 4, 6]),
    ]
    rows = []
    def add(iid, customer, amount, due, status='open', received=0, paid=None):
        cid, name, segment, _ = customer
        rows.append(dict(invoice_id=iid, customer_id=cid, customer_name=name, segment=segment,
            amount=amount, issue_date=(due-timedelta(days=30)).isoformat(), due_date=due.isoformat(),
            status=status, received_amount=received, paid_date=paid.isoformat() if paid else '', currency='INR'))
    for customer in customers:
        for index, delay in enumerate(customer[3]):
            due = as_of-timedelta(days=230-index*30)
            amount = rng.randrange(25000, 125001, 5000)
            add(f'DEMO-H-{customer[0]}-{index+1:02}', customer, amount, due, 'paid', amount, due+timedelta(days=delay))
    outstanding = [
        (0, -10, 65000, 0), (0, 10, 45000, 0),
        (1, -20, 180000, 60000), (1, 15, 90000, 0),
        (2, -45, 150000, 0), (2, -5, 80000, 0),
        (3, -90, 240000, 0), (3, -25, 160000, 40000),
        (4, 30, 75000, 0), (4, -8, 40000, 0),
        (5, 0, 35000, 0), (5, 7, 55000, 0),
    ]
    for index, (customer_index, due_offset, amount, received) in enumerate(outstanding):
        add(f'DEMO-O-{index+1:03}', customers[customer_index], amount, as_of+timedelta(days=due_offset), received=received)
    csv_path = directory / 'jury_invoices.csv'
    with csv_path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    import pandas as pd
    xlsx_path = directory / 'jury_invoices.xlsx'
    pd.DataFrame(rows).to_excel(xlsx_path, index=False)
    setup = dict(synthetic=True, name='Demo Textile Supplies (Synthetic)', as_of=as_of.isoformat(),
        opening_cash=100000, safety_floor=50000,
        obligations=[
            dict(id='demo-payroll', name='Payroll', amount=180000, day_of_month=1, category='salary'),
            dict(id='demo-rent', name='Office rent', amount=30000, day_of_month=5, category='rent'),
            dict(id='demo-emi', name='Equipment EMI', amount=25000, day_of_month=10, category='loan'),
            dict(id='demo-tax', name='Tax provision (demo date)', amount=35000, day_of_month=20, category='tax'),
        ], supplier_bills=[
            dict(id='demo-bill-1', supplier='Demo Fabric Supplier', amount=85000,
                 due_date=(as_of+timedelta(days=3)).isoformat(), is_msme=True, status='open'),
            dict(id='demo-bill-2', supplier='Demo Packaging Supplier', amount=45000,
                 due_date=(as_of+timedelta(days=12)).isoformat(), is_msme=False, status='open'),
        ], monthly_sales=300000, terms_days=30, monthly_noise_pct=15)
    (directory / 'jury_setup.json').write_text(json.dumps(setup, indent=2)+'\n', encoding='utf-8')
    print(f'Created {csv_path.name} and {xlsx_path.name}: {len(rows)} invoices, {len(customers)} fictional customers.')
    print(f'Observation date: {as_of}. Paid: 30. Open: 12 (including 2 partial receipts).')
    print('Synthetic demo only. No rows were copied from a third-party dataset. No account was modified.')
    return csv_path, setup


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of', type=date.fromisoformat, default=date(2026, 10, 25))
    args = parser.parse_args()
    make_files(args.as_of)
