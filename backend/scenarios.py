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


class SalesChange(Change):
    type: Literal['sales_change']
    pct: float = Field(ge=-100, le=100, strict=True, allow_inf_nan=False)


class ExtraExpense(Change):
    type: Literal['extra_expense']
    amount: int = Field(gt=0, le=9_007_199_254_740_991, strict=True)
    date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')

    @field_validator('date')
    @classmethod
    def valid_date(cls, value):
        date.fromisoformat(value)
        return value


class SupplierTerms(Change):
    type: Literal['supplier_terms']
    extra_days: int = Field(ge=1, le=180, strict=True)


ScenarioChange = Annotated[Union[CustomerDelay, SalesChange, ExtraExpense, SupplierTerms],
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
    as_of = date.fromisoformat(business['as_of'])
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
        elif change.type == 'extra_expense':
            if not as_of <= date.fromisoformat(change.date) <= horizon_end:
                raise ValueError(f'Expense date must be between {as_of.isoformat()} and {horizon_end.isoformat()}')
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
    return scenario.model_dump(mode='json')


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
