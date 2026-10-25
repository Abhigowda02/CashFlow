"""Validated what-if definitions and a tenant-scoped saved scenario library."""
from datetime import date, datetime, timedelta, timezone
import json
from typing import Annotated, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, insert, select

from . import database as db


class Change(BaseModel):
    model_config = ConfigDict(extra='forbid')


class CustomerDelay(Change):
    type: Literal['delay_customer']
    customer_id: str = Field(min_length=1, max_length=200)
    extra_days: int = Field(ge=1, le=180, strict=True)
    invoice_ids: list[str] | None = Field(default=None, max_length=200)


class SalesChange(Change):
    type: Literal['sales_change']
    pct: float = Field(ge=-100, le=100, strict=True, allow_inf_nan=False)
    from_date: str | None = None
    duration_days: int | None = Field(default=None, ge=1, le=90, strict=True)


class ExtraExpense(Change):
    type: Literal['extra_expense']
    amount: int = Field(gt=0, le=9_007_199_254_740_991, strict=True)
    date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    category: Literal['electricity','gas','water','rent','salary','loan_emi','tax','insurance','internet_phone','supplier_payment','maintenance','fuel_transport','other'] = 'other'
    label: str = Field(default='', max_length=80)
    repeat: Literal['once','monthly'] = 'once'
    repeat_count: int | None = Field(default=None, ge=1, le=3, strict=True)

    @field_validator('date')
    @classmethod
    def valid_date(cls, value):
        date.fromisoformat(value)
        return value


class SupplierTerms(Change):
    type: Literal['supplier_terms']
    extra_days: int = Field(ge=1, le=180, strict=True)
    direction: Literal['extend','shorten'] = 'extend'
    supplier_id: str | None = Field(default=None, max_length=200)

class Installment(BaseModel):
    date: str
    amount: int = Field(gt=0, strict=True)

class RevisedPaymentSchedule(Change):
    type: Literal['revised_payment_schedule']
    invoice_id: str | None = Field(default=None, min_length=1, max_length=200)
    customer_id: str | None = Field(default=None, min_length=1, max_length=200)
    installments: list[Installment] = Field(min_length=1, max_length=6)
    reliability: float = Field(default=.9, ge=0, le=1)


ScenarioChange = Annotated[Union[CustomerDelay, SalesChange, ExtraExpense, SupplierTerms, RevisedPaymentSchedule],
                           Field(discriminator='type')]


class Scenario(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str = Field(min_length=1, max_length=120)
    changes: list[ScenarioChange] = Field(max_length=20)

    @field_validator('name')
    @classmethod
    def nonblank_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Scenario name cannot be blank')
        return value


def validate_scenario(scenario, business, *, saving=False):
    """Check a definition against the current ledger before saving or comparing."""
    if saving and not scenario.changes:
        raise ValueError('Add at least one change before saving a scenario')
    known_customers = {customer['id'] for customer in business['customers']}
    outstanding_customers = {invoice['customer_id'] for invoice in business['invoices']
        if invoice['status'] == 'open' and invoice['amount'] > invoice.get('received_amount', 0)}
    as_of = max(date.fromisoformat(business['as_of']), date.fromisoformat(business.get('_observation_as_of') or business['as_of']))
    horizon_end = as_of + timedelta(days=89)
    customers, singletons = set(), set()
    for change in scenario.changes:
        if change.type == 'delay_customer':
            if change.customer_id not in known_customers:
                raise ValueError('Choose a customer from your business')
            if change.customer_id not in outstanding_customers:
                raise ValueError('Choose a customer with outstanding open invoices')
            if change.customer_id in customers:
                raise ValueError('Each customer can have only one payment delay')
            customers.add(change.customer_id)
            if change.invoice_ids:
                eligible_ids = {i['id'] for i in business['invoices'] if i['customer_id'] == change.customer_id and i['status'] == 'open'}
                if not set(change.invoice_ids).issubset(eligible_ids): raise ValueError('Choose outstanding invoices belonging to that customer')
        elif change.type == 'extra_expense':
            if not as_of <= date.fromisoformat(change.date) <= horizon_end:
                raise ValueError(f'Expense date must be between {as_of.isoformat()} and {horizon_end.isoformat()}')
            if change.repeat == 'monthly' and not change.repeat_count: raise ValueError('Choose repeat_count for a monthly expense')
        elif change.type == 'revised_payment_schedule':
            if bool(change.invoice_id) == bool(change.customer_id): raise ValueError('Choose exactly one invoice or customer')
            invoices = [i for i in business['invoices'] if i['status'] == 'open' and (i['id'] == change.invoice_id or i['customer_id'] == change.customer_id)]
            if len(invoices) != 1: raise ValueError('A revised schedule must identify one outstanding invoice')
            if sum(item.amount for item in change.installments) != invoices[0]['amount'] - invoices[0].get('received_amount', 0): raise ValueError('Installments must equal the invoice outstanding amount')
            try:
                dates = [date.fromisoformat(item.date) for item in change.installments]
            except ValueError as error:
                raise ValueError('Use ISO installment dates') from error
            if dates != sorted(dates) or any(not as_of <= item <= horizon_end for item in dates): raise ValueError('Installment dates must be ordered and within the 90-day horizon')
        elif change.type in ('sales_change', 'supplier_terms'):
            if change.type == 'sales_change':
                if change.pct == 0:
                    raise ValueError('Enter a nonzero sales change')
                if business.get('sales_plan', {}).get('monthly_amount', 0) <= 0:
                    raise ValueError('Enter positive planned monthly sales before changing sales')
            elif not any(bill['status'] == 'open' for bill in business.get('supplier_bills', [])):
                raise ValueError('Add an open supplier bill before extending its terms')
            if change.type in singletons:
                raise ValueError('Add only one sales change and one supplier terms change per scenario')
            singletons.add(change.type)
    return scenario.model_dump(mode='json', exclude_unset=True)


def _definition(row):
    return dict(id=row['id'], name=row['name'], changes=json.loads(row['changes']),
                created_at=row['created_at'], updated_at=row['updated_at'])


def list_saved(business_id):
    with db.engine().connect() as connection:
        rows = connection.execute(select(db.scenarios).where(db.scenarios.c.business_id == business_id)
            .order_by(db.scenarios.c.updated_at.desc(), db.scenarios.c.id)).mappings().all()
    return [_definition(row) for row in rows]


def save(scenario, business_id):
    """Persist only assumptions; forecasts always use the current business on compare."""
    timestamp = datetime.now(timezone.utc).isoformat()
    saved = dict(id=str(uuid4()), business_id=business_id, name=scenario['name'],
                 changes=json.dumps(scenario['changes']), created_at=timestamp, updated_at=timestamp)
    with db.transaction() as connection:
        connection.execute(insert(db.scenarios).values(**saved))
    return _definition(saved)


def delete_saved(scenario_id, business_id):
    with db.transaction() as connection:
        result = connection.execute(delete(db.scenarios).where(
            db.scenarios.c.business_id == business_id, db.scenarios.c.id == scenario_id))
        return result.rowcount == 1
