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
