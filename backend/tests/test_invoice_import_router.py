import base64

from backend.modules.gst_einvoice import parse_gst_einvoice
from backend.modules.invoice_mapper import map_columns, parse_rows


def test_mapper_recognises_tally_headers_and_flags_missing_values():
    headers = ['Voucher No', 'Party Name', 'Date', 'Due Date', 'Gross Total', 'Unused']
    proposed = map_columns(headers)
    assert proposed['mapping']['invoice_id'] == 'Voucher No'
    rows = parse_rows([{'Voucher No': 'T-1', 'Party Name': 'Maya', 'Date': '24/10/2026', 'Due Date': '23/11/2026', 'Gross Total': '1,20,000'}], proposed['mapping'])
    assert rows[0]['amount'] == 120000
    assert rows[0]['issue_date'] == '2026-10-24'
    assert rows[0]['flags'] == []


def test_mapper_derives_payment_state_from_outstanding_balance():
    headers = ['Invoice No', 'Customer Name', 'Invoice Date', 'Due Date', 'Invoice Amount', 'Outstanding']
    mapping = map_columns(headers)['mapping']
    rows = parse_rows([
        {'Invoice No': 'P-1', 'Customer Name': 'Maya', 'Invoice Date': '2026-09-01', 'Due Date': '2026-10-01', 'Invoice Amount': '100000', 'Outstanding': '25000'},
    ], mapping)
    assert rows[0]['received_amount'] == 75000
    assert rows[0]['flags'] == []


def test_gst_parser_returns_clear_error_without_crashing():
    result = parse_gst_einvoice('{bad json')
    assert result['rows'] == []
    assert 'Invalid GST' in result['errors'][0]['message']


def test_csv_preview_then_confirm_is_review_first(client):
    raw = ('Invoice No,Customer Name,Invoice Date,Due Date,Invoice Amount\n'
           'Z-1,Zoya Textiles,2026-10-01,2026-10-31,125000\n').encode()
    response = client.post('/api/invoices/preview', json={'filename': 'zoho.csv', 'content_base64': base64.b64encode(raw).decode()})
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview['saved'] is False
    assert client.get('/api/invoices').json() == []
    result = client.post('/api/invoices/commit', json={'rows': preview['rows'], 'mode': 'append', 'confirm_currency_inr': True})
    assert result.status_code == 200, result.text
    assert client.get('/api/invoices').json()[0]['id'] == 'Z-1'


def test_csv_append_preserves_partly_paid_invoice_and_existing_records(client):
    original = {
        'filename': 'initial.csv',
        'content_base64': base64.b64encode(
            b'Invoice No,Customer Name,Invoice Date,Due Date,Invoice Amount\nOLD-1,Existing Customer,2026-09-01,2026-10-01,1000\n'
        ).decode(),
    }
    initial = client.post('/api/invoices/preview', json=original).json()
    assert client.post('/api/invoices/commit', json={'rows': initial['rows'], 'mode': 'append', 'confirm_currency_inr': True}).status_code == 200

    raw = (
        'invoice_id,customer_id,customer_name,email,phone,segment,amount,issue_date,due_date,received_amount,paid_date,currency\n'
        'NEW-1,C-NEW,New Customer,new@example.com,+919876543210,corporate,120000,2026-08-01,2026-09-01,35000,,INR\n'
    ).encode()
    preview = client.post('/api/invoices/preview', json={'filename': 'append.csv', 'content_base64': base64.b64encode(raw).decode()})
    assert preview.status_code == 200, preview.text
    row = preview.json()['rows'][0]
    assert row['flags'] == []
    assert row['customer_id'] == 'C-NEW'
    assert row['received_amount'] == 35000
    result = client.post('/api/invoices/commit', json={'rows': [row], 'mode': 'append', 'confirm_currency_inr': True})
    assert result.status_code == 200, result.text
    invoices = {invoice['id']: invoice for invoice in client.get('/api/invoices').json()}
    assert set(invoices) == {'OLD-1', 'NEW-1'}
    assert invoices['NEW-1']['received'] == 35000
    assert invoices['NEW-1']['outstanding'] == 85000
    assert invoices['NEW-1']['ledger_status'] == 'partly paid'
    assert invoices['NEW-1']['customer_name'] == 'New Customer'
    from backend import ledger
    customer = next(item for item in ledger.load_business(client.business_id)['customers'] if item['id'] == 'C-NEW')
    assert customer['email'] == 'new@example.com' and customer['phone'] == '+919876543210'
