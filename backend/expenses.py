"""Scheduled outflows, kept separate from bank-confirmed spending."""
from collections import defaultdict
from datetime import date, timedelta
from engine.schedules import monthly_occurrences


def summary(business):
    as_of = date.fromisoformat(business['as_of'])
    obligations = business.get('obligations', [])
    recurring = monthly_occurrences(obligations, business['as_of'], 90)
    upcoming = list(recurring)
    overdue = []
    for bill in business.get('supplier_bills', []):
        if bill.get('status', 'open') != 'open':
            continue
        offset = (date.fromisoformat(bill['due_date'])-as_of).days
        row = dict(id=bill['id'], name=bill.get('supplier', 'Supplier bill'), amount=bill['amount'],
                   date=bill['due_date'], category='supplier', kind='supplier', days_until=offset)
        if offset < 0:
            overdue.append(row)
        elif offset < 90:
            upcoming.append(row)
    upcoming.sort(key=lambda row: (row['date'], row['kind'], row['name'], row['id']))
    overdue.sort(key=lambda row: (row['date'], row['id']))
    categories, calendar_months = defaultdict(int), defaultdict(int)
    for obligation in obligations:
        categories[obligation.get('category', 'other')] += obligation.get('amount', 0)
    for row in upcoming:
        calendar_months[row['date'][:7]] += row['amount']
    definitions = []
    for obligation in obligations:
        next_occurrence = next((row for row in recurring if row['id'] == obligation['id']), None)
        definitions.append(dict(obligation, category=obligation.get('category', 'other'),
                                next_due=next_occurrence['date'] if next_occurrence else None))
    definitions.sort(key=lambda row: (row['next_due'] or '9999', row['name']))
    return dict(as_of=business['as_of'], through=(as_of+timedelta(days=89)).isoformat(),
        recurring_monthly_total=sum(row.get('amount', 0) for row in obligations),
        recurring_count=len(obligations), next_7_days=sum(row['amount'] for row in upcoming if row['days_until'] < 7),
        next_30_days=sum(row['amount'] for row in upcoming if row['days_until'] < 30),
        overdue_supplier_total=sum(row['amount'] for row in overdue),
        recurring_categories=dict(sorted(categories.items())), calendar_month_totals=dict(sorted(calendar_months.items())),
        obligations=definitions, upcoming=upcoming, overdue_suppliers=overdue)
