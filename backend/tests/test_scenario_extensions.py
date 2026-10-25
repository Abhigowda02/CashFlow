from backend import clock

def test_clock_override_drives_today(monkeypatch):
    monkeypatch.setenv('APP_ENV','test'); monkeypatch.setenv('APP_FAKE_TODAY','2026-11-01')
    assert clock.today_ist().isoformat() == '2026-11-01'

def test_pinned_today_drives_forecast_start(client, monkeypatch):
    monkeypatch.setenv('APP_FAKE_TODAY','2026-11-01')
    assert client.get('/api/forecast').json()['dates'][0] == '2026-11-01'

def test_invoice_specific_delay_only_targets_selected_invoice(client):
    from backend.tests.test_ledger_api import payload
    assert client.post('/api/import', json=payload()).status_code == 200
    business=client.get('/api/business').json(); invoice=business['invoices'][0]
    response=client.post('/api/scenario',json={'name':'invoice delay','changes':[{'type':'delay_customer','customer_id':invoice['customer_id'],'invoice_ids':[invoice['id']],'extra_days':10}]})
    assert response.status_code == 200

def test_revised_schedule_rejects_wrong_total(client):
    from backend.tests.test_ledger_api import payload
    assert client.post('/api/import', json=payload()).status_code == 200
    business=client.get('/api/business').json(); invoice=business['invoices'][0]
    response=client.post('/api/scenario',json={'name':'schedule','changes':[{'type':'revised_payment_schedule','invoice_id':invoice['id'],'installments':[{'date':'2026-10-25','amount':1}]}]})
    assert response.status_code == 422
