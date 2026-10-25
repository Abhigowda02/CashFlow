"""Explicit, tenant-scoped loading of the existing complete jury fixture."""
import base64
import json
from pathlib import Path

from sqlalchemy import delete, select, update

from . import database as db, ledger


EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'
SOURCE = 'synthetic_demo'
FIXTURE = 'jury_textiles_v1'


class DemoConflict(ValueError):
    """The current workspace cannot safely be replaced by a demo."""


def fixture_business():
    """Reuse the checked-in invoice and plan examples, without generating new data."""
    setup = json.loads((EXAMPLES / 'jury_setup.json').read_text(encoding='utf-8'))
    if setup.get('synthetic') is not True:
        raise ValueError('The jury fixture must be explicitly synthetic')
    business = ledger.import_invoices('jury_invoices.csv',
        base64.b64encode((EXAMPLES / 'jury_invoices.csv').read_bytes()).decode(),
        setup['name'], setup['as_of'], setup['opening_cash'], setup['safety_floor'])
    business.update(
        obligations=[dict(row, frequency=row.get('frequency', 'monthly')) for row in setup['obligations']],
        supplier_bills=setup['supplier_bills'],
        sales_plan=dict(monthly_amount=setup['monthly_sales'], terms_days=setup['terms_days'],
                        monthly_noise_pct=setup['monthly_noise_pct']),
        data_source=SOURCE,
        demo_fixture=FIXTURE,
        source_kind='synthetic',
        source_provenance='Fictional examples/jury_invoices.csv and jury_setup.json; pipeline demonstration only.',
        observation_date_source='explicit_synthetic_fixture',
    )
    return business


def load(business_id, *, reset=False):
    """Replace only a never-onboarded empty workspace or an explicitly reset demo.

    The row is locked before checking the server-owned source marker and writing.
    An owner-created cash-only business remains real data, even with zero invoices.
    """
    with db.transaction() as connection:
        row = connection.execute(select(db.workspaces).where(
            db.workspaces.c.id == business_id).with_for_update()).mappings().one()
        current = json.loads(row['payload'])
        is_demo = current.get('data_source') == SOURCE and current.get('demo_fixture') == FIXTURE
        empty = not row['onboarded'] and current == {}
        if not empty and not is_demo:
            raise DemoConflict('Demo loading cannot replace your business. Use a separate new demo account.')
        if is_demo and not reset:
            raise DemoConflict('The demo is already loaded. Explicitly confirm a demo reset to reload it.')
        if empty and reset:
            raise DemoConflict('There is no loaded demo to reset. Choose Load synthetic demo first.')
        business = fixture_business()
        connection.execute(update(db.workspaces).where(db.workspaces.c.id == business_id)
                           .values(payload=json.dumps(business), onboarded=True))
        # Both tables are tenant scoped; an explicit demo reset also removes its
        # experimental receipts/scenarios so they cannot refer to stale assumptions.
        connection.execute(delete(db.receipts).where(db.receipts.c.business_id == business_id))
        connection.execute(delete(db.scenarios).where(db.scenarios.c.business_id == business_id))
    return business
