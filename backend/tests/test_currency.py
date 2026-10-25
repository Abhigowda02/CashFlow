import base64
import io

import pandas as pd
import pytest

from backend.tests.test_ledger_api import payload


def request_with_units(extension, units):
    request = payload()
    table = pd.read_csv(io.BytesIO(base64.b64decode(request['content_base64'])), keep_default_na=False)
    if units is None:
        table = table.drop(columns='currency')
    else:
        table['currency'] = units
    if extension == 'xlsx':
        output = io.BytesIO()
        table.to_excel(output, index=False)
        data = output.getvalue()
    else:
        data = table.to_csv(index=False).encode()
    return dict(request, filename=f'invoices.{extension}', content_base64=base64.b64encode(data).decode())


@pytest.mark.parametrize('extension', ['csv', 'xlsx'])
@pytest.mark.parametrize('units', [None, ['', ''], ['INR', '']])
def test_unknown_units_require_an_explicit_declaration(client, extension, units):
    request = request_with_units(extension, units)
    before = client.get('/api/business').json()
    assert client.post('/api/import', json=request).status_code == 400
    assert client.get('/api/business').json() == before
    response = client.post('/api/import', json=dict(request, declared_currency='INR'))
    assert response.status_code == 200, response.text
    business = client.get('/api/business').json()
    assert business['currency_provenance'] == 'owner_confirmed_INR'
    assert business['amount_unit_verified'] is True
    assert business['amount_semantics'] == 'original_invoice_amount'


@pytest.mark.parametrize('units', [['USD', 'USD'], ['CAD', 'INR'], ['unknown', ''], ['INR', 'EUR']])
def test_confirmation_never_converts_or_overrides_known_foreign_units(client, units):
    before = client.get('/api/business').json()
    request = request_with_units('csv', units)
    assert client.post('/api/import', json=dict(request, declared_currency='INR')).status_code == 400
    assert client.get('/api/business').json() == before


def test_explicit_inr_rows_and_api_declaration_validation(client):
    request = request_with_units('csv', [' inr ', 'INR'])
    assert client.post('/api/import', json=request).status_code == 200
    assert client.get('/api/business').json()['currency_provenance'] == 'row_declared_INR'
    for value in ['USD', '', True, 1]:
        assert client.post('/api/import', json=dict(request, declared_currency=value)).status_code == 422
