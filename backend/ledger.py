"""Tenant-scoped ledger. Cash changes only when a receipt is recorded."""
import base64
import copy
import io
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, insert, select, update
from datetime import date
from . import clock, database as db
from .gap import simulate_gap_cash

def load_business(business_id):
    with db.engine().connect() as connection:
        row = connection.execute(select(db.workspaces.c.payload).where(
            db.workspaces.c.id == business_id, db.workspaces.c.onboarded.is_(True))).first()
    if not row:
        return None
    business = json.loads(row[0])
    # Migration for existing workspaces: if as_of exists in payload, set cash_updated_on = old as_of
    migrated = False
    if 'cash_updated_on' not in business:
        business['cash_updated_on'] = business.get('as_of') or clock.today_ist().isoformat()
        migrated = True
    if 'cash_balance' not in business:
        business['cash_balance'] = business.get('opening_cash', 0)
        migrated = True
    if migrated:
        with db.transaction() as conn:
            conn.execute(update(db.workspaces).where(db.workspaces.c.id == business_id).values(payload=json.dumps(business)))
    return business


def update_cash_balance(business_id, cash_balance: int, cash_updated_on: str):
    with db.transaction() as connection:
        row = connection.execute(select(db.workspaces.c.payload).where(
            db.workspaces.c.id == business_id).with_for_update()).one()
        current = json.loads(row[0])
        current['cash_balance'] = cash_balance
        current['cash_updated_on'] = cash_updated_on
        current['opening_cash'] = cash_balance
        connection.execute(update(db.workspaces).where(db.workspaces.c.id == business_id)
                           .values(payload=json.dumps(current)))
    return current


def save_business(business, business_id):
    with db.transaction() as connection:
        connection.execute(select(db.workspaces.c.id).where(db.workspaces.c.id == business_id).with_for_update()).one()
        connection.execute(update(db.workspaces).where(db.workspaces.c.id == business_id)
                           .values(payload=json.dumps(business), onboarded=True))
        connection.execute(delete(db.receipts).where(db.receipts.c.business_id == business_id))


def update_plan(business, settings, business_id):
    with db.transaction() as connection:
        row = connection.execute(select(db.workspaces.c.payload).where(db.workspaces.c.id == business_id).with_for_update()).one()
        current = json.loads(row[0])
        current.update(settings)
        connection.execute(update(db.workspaces).where(db.workspaces.c.id == business_id).values(payload=json.dumps(current)))
    return current


def update_customer_context(customer_id, context, business_id):
    with db.transaction() as connection:
        row = connection.execute(select(db.workspaces.c.payload).where(
            db.workspaces.c.id == business_id, db.workspaces.c.onboarded.is_(True)).with_for_update()).first()
        if row is None:
            raise ValueError('Complete business setup first')
        business = json.loads(row[0])
        customer = next((item for item in business['customers'] if item['id'] == customer_id), None)
        if customer is None:
            raise ValueError('Customer not found in your business')
        eligible = {invoice['id'] for invoice in business['invoices'] if invoice['customer_id'] == customer_id
                    and invoice['status'] == 'open' and invoice['amount'] > invoice.get('received_amount', 0)}
        if not set(context['disputed_invoice_ids']).issubset(eligible):
            raise ValueError('Disputed invoices must be outstanding invoices belonging to this customer')
        customer['collection_context'] = context
        connection.execute(update(db.workspaces).where(db.workspaces.c.id == business_id).values(payload=json.dumps(business)))
        return customer


def import_invoices(filename, content, name, as_of, opening_cash, safety_floor, *, declared_currency=None):
    payload = base64.b64decode(content, validate=True)
    if len(payload) > 5_000_000:
        raise ValueError('Upload must be smaller than 5 MB')
    suffix = Path(filename).suffix.lower()
    if suffix == '.csv':
        table = pd.read_csv(io.BytesIO(payload), dtype=str, keep_default_na=False)
    elif suffix == '.xlsx':
        table = pd.read_excel(io.BytesIO(payload), dtype=str, keep_default_na=False, engine='openpyxl')
    else:
        raise ValueError('Choose a CSV or .xlsx invoice file')
    required = {'invoice_id', 'customer_id', 'amount', 'issue_date', 'due_date'}
    if not required.issubset(table.columns):
        raise ValueError('Use the invoice template. Required columns: ' + ', '.join(sorted(required)))
    if len(table) > 2000 or table.empty:
        raise ValueError('Import between 1 and 2,000 invoices per workspace')
    currencies = table['currency'].str.strip().str.upper() if 'currency' in table else pd.Series('', index=table.index)
    if not currencies.isin(['', 'INR']).all():
        raise ValueError('This workspace uses INR. Convert foreign-currency amounts before importing.')
    missing_units = currencies.eq('').any()
    if missing_units and declared_currency != 'INR':
        raise ValueError('Currency is missing. Confirm that every amount is an original invoice amount in INR; no conversion is performed.')
    as_of = pd.Timestamp(as_of).date().isoformat()
    customers, invoices, ids = {}, [], set()
    def rupees(value):
        number = float(value)
        if not pd.notna(number) or not number.is_integer() or number < 0:
            raise ValueError('Amounts must be nonnegative whole INR')
        return int(number)
    for _, row in table.iterrows():
        iid, cid = row.invoice_id.strip(), row.customer_id.strip()
        if not iid or not cid or iid in ids:
            raise ValueError('Invoice/customer IDs must be nonempty and invoice IDs unique')
        ids.add(iid)
        issue = pd.Timestamp(row.issue_date).date().isoformat()
        due = pd.Timestamp(row.due_date).date().isoformat()
        if issue > as_of or due < issue:
            raise ValueError(f'{iid}: issue must be on/before as_of and due on/after issue')
        amount = rupees(row.amount)
        status = row.get('status', 'open').strip().lower() or 'open'
        if status not in ['open', 'paid']:
            raise ValueError('Import status must be open or paid; use received_amount for partial receipts')
        received = rupees(row.get('received_amount', '') or (amount if status == 'paid' else 0))
        if received > amount:
            raise ValueError(f'{iid}: received_amount exceeds invoice amount')
        paid_date = row.get('paid_date', '').strip() or None
        if paid_date:
            paid_date = pd.Timestamp(paid_date).date().isoformat()
            if paid_date < issue or paid_date > as_of:
                raise ValueError(f'{iid}: payment date must be between issue_date and as_of')
        settled = received == amount
        if settled and amount == 0 and not paid_date:
            paid_date = issue
        if settled and not paid_date:
            raise ValueError(f'{iid}: fully received invoices require paid_date')
        if status == 'paid' and not settled:
            raise ValueError(f'{iid}: paid status requires the full received_amount')
        segment = row.get('segment', 'small').strip() or 'small'
        if segment not in ['small', 'corporate', 'government']:
            raise ValueError('Segment must be small, corporate, or government')
        customer = dict(id=cid, name=row.get('customer_name', '').strip() or cid, segment=segment)
        if cid in customers and customers[cid] != customer:
            raise ValueError(f'Conflicting customer details for {cid}')
        customers[cid] = customer
        invoices.append(dict(id=iid, customer_id=cid, amount=amount, received_amount=received,
                             issue_date=issue, due_date=due, paid_date=paid_date if settled else None,
                             status='paid' if settled else 'open'))
    business = dict(name=name, as_of=as_of, opening_cash=opening_cash, safety_floor=safety_floor,
                    cash_balance=opening_cash, cash_updated_on=as_of,
                    customers=list(customers.values()), invoices=invoices, supplier_bills=[], obligations=[],
                    sales_plan=dict(monthly_amount=0, terms_days=30, monthly_noise_pct=0),
                    data_source='imported', currency='INR', amount_unit_verified=True,
                    amount_semantics='original_invoice_amount',
                    currency_provenance='owner_confirmed_INR' if missing_units else 'row_declared_INR',
                    source_kind='owner_entered',
                    source_provenance='Owner-declared INR invoice upload; not independently verified.',
                    observation_date_source='owner_supplied')
    return business


def append_pdf_invoices(drafts, *, confirm_append, confirm_currency_inr, business_id):
    if not confirm_append:
        raise ValueError("Confirm that these reviewed invoices should be added to the existing workspace.")
    if not confirm_currency_inr:
        raise ValueError("Confirm that every reviewed invoice amount is in INR.")
    with db.transaction() as connection:
        row = connection.execute(select(db.workspaces.c.payload).where(
            db.workspaces.c.id == business_id, db.workspaces.c.onboarded.is_(True)
        ).with_for_update()).first()
        if row is None:
            raise ValueError("Complete business setup first")
        business = json.loads(row[0])
        existing_ids = {invoice["id"] for invoice in business.get("invoices", [])}
        incoming_ids = set()
        customer_by_name = {customer["name"].strip().casefold(): customer
                            for customer in business.get("customers", [])}
        customers_by_id = {customer["id"]: customer for customer in business.get("customers", [])}
        new_customers = []
        new_invoices = []
        as_of = business["as_of"]
        for draft in drafts:
            iid = draft["invoice_id"].strip()
            cid = draft["customer_id"].strip()
            customer_name = draft["customer_name"].strip()
            issue = draft["issue_date"].isoformat()
            due = draft["due_date"].isoformat()
            paid_date = draft["paid_date"].isoformat() if draft.get("paid_date") else None
            amount, received = draft["amount"], draft["received_amount"]
            if not iid or not cid or not customer_name:
                raise ValueError("Invoice ID, customer ID and customer name are required.")
            if iid in existing_ids or iid in incoming_ids:
                raise ValueError(f"Invoice {iid} already exists. Correct or remove duplicate invoice IDs.")
            incoming_ids.add(iid)
            if draft["currency"].strip().upper() != "INR":
                raise ValueError(f"{iid}: currency must be INR. Convert the amount manually before adding it.")
            if issue > as_of or due < issue:
                raise ValueError(f"{iid}: issue date must be on/before the workspace observation date and due date must be on/after issue date.")
            if amount <= 0 or received < 0 or received > amount:
                raise ValueError(f"{iid}: invoice and received amounts must be valid whole INR amounts.")
            if paid_date and (paid_date < issue or paid_date > as_of):
                raise ValueError(f"{iid}: payment date must be between issue date and workspace observation date.")
            if received == amount and not paid_date:
                raise ValueError(f"{iid}: fully received invoices require a payment date.")
            if received < amount and paid_date:
                raise ValueError(f"{iid}: a payment date is only accepted for a fully received invoice.")

            customer = customer_by_name.get(customer_name.casefold())
            if customer:
                if customer["segment"] != draft["segment"]:
                    raise ValueError(f"{iid}: customer {customer_name} already exists with a different segment.")
                cid = customer["id"]
            elif cid in customers_by_id:
                customer = customers_by_id[cid]
                if customer["name"].strip().casefold() != customer_name.casefold() or customer["segment"] != draft["segment"]:
                    raise ValueError(f"{iid}: customer ID {cid} conflicts with an existing customer.")
            else:
                customer = dict(id=cid, name=customer_name, segment=draft["segment"])
                customers_by_id[cid] = customer
                customer_by_name[customer_name.casefold()] = customer
                new_customers.append(customer)
            new_invoices.append(dict(
                id=iid, customer_id=cid, amount=amount, received_amount=received,
                issue_date=issue, due_date=due, paid_date=paid_date,
                status="paid" if received == amount else "open",
            ))

        business.setdefault("customers", []).extend(new_customers)
        business.setdefault("invoices", []).extend(new_invoices)
        business["data_source"] = "imported"
        business["currency"] = "INR"
        business["amount_unit_verified"] = True
        business["currency_provenance"] = "owner_confirmed_INR_after_PDF_review"
        business["source_kind"] = "owner_entered"
        business["source_provenance"] = "Owner-reviewed text PDF fields; not independently verified."
        connection.execute(update(db.workspaces).where(
            db.workspaces.c.id == business_id
        ).values(payload=json.dumps(business), onboarded=True))
    return business


def forecast_business(business, business_id=None):
    business = copy.deepcopy(business)
    if business_id is not None:
        business['_model_scope'] = business_id

    # Recalculate as_of = today_ist() on every request
    today = clock.today_ist()
    business['as_of'] = today.isoformat()

    cash_updated_on_str = business.get('cash_updated_on') or business.get('as_of') or today.isoformat()
    try:
        cash_updated_on = date.fromisoformat(cash_updated_on_str.split('T')[0])
    except (ValueError, TypeError):
        cash_updated_on = today

    adjusted_cash, gap_summary = simulate_gap_cash(business, cash_updated_on, today)
    business['opening_cash'] = adjusted_cash
    business['_gap_summary'] = gap_summary

    for invoice in business['invoices']:
        if invoice['status'] == 'open':
            invoice['model_amount'] = invoice['amount']
            invoice['amount'] -= invoice.get('received_amount', 0)
    return business


def record_receipt(business, invoice_id, amount, date, receipt_id, business_id):
    with db.transaction() as connection:
        row = connection.execute(select(db.workspaces.c.payload).where(db.workspaces.c.id == business_id).with_for_update()).one()
        current = json.loads(row[0])
        previous = connection.execute(select(db.receipts.c.invoice_id, db.receipts.c.amount, db.receipts.c.date)
            .where(db.receipts.c.business_id == business_id, db.receipts.c.id == receipt_id)).first()
        if previous:
            if tuple(previous) != (invoice_id, amount, date):
                raise ValueError('Receipt ID already used for a different payment')
            return current
        invoice = next((i for i in current['invoices'] if i['id'] == invoice_id), None)
        if invoice is None:
            raise ValueError('Invoice not found')
        received = invoice.get('received_amount', invoice['amount'] if invoice['status'] == 'paid' else 0)
        if amount <= 0 or amount > invoice['amount'] - received:
            raise ValueError('Receipt must be positive and not exceed the outstanding balance')
        if not invoice['issue_date'] <= date <= current['as_of']:
            raise ValueError('Receipt date must be between issue date and workspace as_of')
        invoice['received_amount'] = received + amount
        if invoice['received_amount'] == invoice['amount']:
            earlier = connection.execute(select(db.receipts.c.date).where(
                db.receipts.c.business_id == business_id, db.receipts.c.invoice_id == invoice_id)).scalars().all()
            invoice.update(status='paid', paid_date=max([date, *earlier]))
        current['opening_cash'] += amount
        current['cash_balance'] = current.get('cash_balance', current['opening_cash'] - amount) + amount
        current['cash_updated_on'] = max(current.get('cash_updated_on', date), date)
        connection.execute(insert(db.receipts).values(business_id=business_id, id=receipt_id,
                           invoice_id=invoice_id, amount=amount, date=date))
        connection.execute(update(db.workspaces).where(db.workspaces.c.id == business_id).values(payload=json.dumps(current)))
        return current


def commit_reviewed_invoices(rows, mode, business_id, keep_duplicates=False):
    """Persist owner-reviewed invoice proposals and return a small JSON summary.

    Input rows are plain dictionaries from an import review; output is a count.
    All access is scoped to ``business_id`` and no parsing or guessing occurs here.
    """
    with db.transaction() as connection:
        row = connection.execute(select(db.workspaces.c.payload).where(
            db.workspaces.c.id == business_id, db.workspaces.c.onboarded.is_(True)).with_for_update()).first()
        if row is None:
            raise ValueError('Complete business setup first')
        business = json.loads(row[0])
        incoming, ids = [], set()
        existing_ids = {invoice['id'] for invoice in business.get('invoices', [])}
        for draft in rows:
            flags = draft.get('flags') or []
            iid, customer = str(draft.get('invoice_id') or '').strip(), str(draft.get('customer_name') or draft.get('customer_id') or '').strip()
            try:
                amount = int(draft.get('amount'))
                issue, due = str(draft.get('issue_date') or ''), str(draft.get('due_date') or '')
                date.fromisoformat(issue); date.fromisoformat(due)
            except (TypeError, ValueError):
                raise ValueError('Each reviewed invoice needs whole-INR amount and ISO issue/due dates')
            if not iid or not customer or amount <= 0 or due < issue:
                raise ValueError('Each reviewed invoice needs an ID, customer, positive amount, and valid dates')
            if (iid in ids or (mode == 'append' and iid in existing_ids)) and not keep_duplicates:
                raise ValueError(f'Invoice {iid} is a duplicate; explicitly keep duplicates only after review')
            ids.add(iid)
            cid = str(draft.get('customer_id') or customer).strip()
            incoming.append(dict(id=iid, customer_id=cid, amount=amount, received_amount=int(draft.get('received_amount') or 0),
                issue_date=issue, due_date=due, paid_date=draft.get('paid_date'), status='open'))
        customers = {customer['id']: customer for customer in business.get('customers', [])}
        for item in incoming:
            customers.setdefault(item['customer_id'], dict(id=item['customer_id'], name=item['customer_id'], segment='small'))
        if mode == 'replace':
            business['invoices'] = incoming
            business['customers'] = list(customers.values())
            connection.execute(delete(db.receipts).where(db.receipts.c.business_id == business_id))
        else:
            business.setdefault('customers', []).extend(c for cid, c in customers.items() if cid not in {x['id'] for x in business.get('customers', [])})
            business.setdefault('invoices', []).extend(incoming)
        business['data_source'] = 'imported'
        connection.execute(update(db.workspaces).where(db.workspaces.c.id == business_id).values(payload=json.dumps(business)))
    return {'saved': True, 'invoice_count': len(incoming), 'mode': mode}


def edit_invoice(invoice_id, changes, business_id):
    """Apply an owner-supplied edit to one tenant-scoped invoice and return it."""
    allowed = {'due_date', 'issue_date', 'amount', 'customer_id'}
    if not changes or not set(changes).issubset(allowed):
        raise ValueError('Only invoice date, amount, and customer fields can be edited here')
    with db.transaction() as connection:
        row = connection.execute(select(db.workspaces.c.payload).where(db.workspaces.c.id == business_id).with_for_update()).one()
        business = json.loads(row[0])
        invoice = next((item for item in business['invoices'] if item['id'] == invoice_id), None)
        if invoice is None: raise ValueError('Invoice not found')
        invoice.update(changes)
        try:
            invoice['amount'] = int(invoice['amount'])
            date.fromisoformat(invoice['issue_date']); date.fromisoformat(invoice['due_date'])
        except (TypeError, ValueError): raise ValueError('Use whole-INR amount and ISO dates')
        if invoice['amount'] <= 0 or invoice['due_date'] < invoice['issue_date'] or invoice.get('received_amount', 0) > invoice['amount']:
            raise ValueError('Invoice dates or amount are invalid')
        connection.execute(update(db.workspaces).where(db.workspaces.c.id == business_id).values(payload=json.dumps(business)))
        return invoice


def delete_invoice(invoice_id, business_id):
    """Delete a tenant-scoped invoice only when it has no recorded receipt."""
    with db.transaction() as connection:
        row = connection.execute(select(db.workspaces.c.payload).where(db.workspaces.c.id == business_id).with_for_update()).one()
        business = json.loads(row[0])
        target = next((item for item in business['invoices'] if item['id'] == invoice_id), None)
        if target is None: return False
        if connection.execute(select(db.receipts.c.id).where(db.receipts.c.business_id == business_id, db.receipts.c.invoice_id == invoice_id)).first():
            raise ValueError('Invoices with recorded receipts cannot be deleted')
        business['invoices'].remove(target)
        connection.execute(update(db.workspaces).where(db.workspaces.c.id == business_id).values(payload=json.dumps(business)))
        return True


def ledger_summary(business):
    names = {c['id']: c['name'] for c in business['customers']}
    rows, buckets, customer_totals = [], dict.fromkeys(['Not due', '0–30', '31–60', '61–90', '90+'], 0), {}
    for invoice in business['invoices']:
        received = invoice.get('received_amount', invoice['amount'] if invoice['status'] == 'paid' else 0)
        outstanding = invoice['amount'] - received
        overdue = (pd.Timestamp(business['as_of']) - pd.Timestamp(invoice['due_date'])).days
        status = ('received' if outstanding == 0 else 'partly paid' if received else
                  'overdue' if overdue > 0 else 'due' if overdue == 0 else 'issued')
        bucket = 'Not due' if overdue < 0 else '0–30' if overdue <= 30 else '31–60' if overdue <= 60 else '61–90' if overdue <= 90 else '90+'
        buckets[bucket] += outstanding
        customer_totals[invoice['customer_id']] = customer_totals.get(invoice['customer_id'], 0) + outstanding
        rows.append(dict(**invoice, customer_name=names.get(invoice['customer_id'], invoice['customer_id']),
                         received=received, outstanding=outstanding, ledger_status=status, days_overdue=max(0, overdue)))
    total = sum(buckets.values())
    concentration = [dict(customer=names.get(cid, cid), amount=value, share=value/total)
                     for cid, value in sorted(customer_totals.items(), key=lambda pair: -pair[1]) if total and value]
    payable = dict.fromkeys(buckets, 0)
    for bill in business.get('supplier_bills', []):
        if bill['status'] != 'open':
            continue
        age = (pd.Timestamp(business['as_of']) - pd.Timestamp(bill['due_date'])).days
        bucket = 'Not due' if age < 0 else '0–30' if age <= 30 else '31–60' if age <= 60 else '61–90' if age <= 90 else '90+'
        payable[bucket] += bill['amount']
    return dict(invoices=rows, receivable_aging=buckets, payable_aging=payable,
                outstanding=total, received=sum(r['received'] for r in rows), concentration=concentration)
