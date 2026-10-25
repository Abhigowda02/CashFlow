from backend.tests.conftest import signed_in_client


def expense_plan():
    return dict(obligations=[
        dict(id='salary', name='Payroll', amount=60000, day_of_month=1, category='salary'),
        dict(id='rent', name='Office rent', amount=10000, day_of_month=5, category='rent'),
        dict(id='emi', name='Loan EMI', amount=5000, day_of_month=10, category='loan'),
        dict(id='tax', name='Tax provision', amount=7000, day_of_month=20, category='tax'),
        dict(id='utility', name='Utilities', amount=2000, day_of_month=31, category='utilities'),
    ], supplier_bills=[
        dict(id='b1', supplier='Upcoming supplier', amount=3000, due_date='2026-10-28'),
        dict(id='b2', supplier='Overdue supplier', amount=4000, due_date='2026-10-23'),
        dict(id='b3', supplier='Already paid', amount=9000, due_date='2026-10-29', status='paid'),
    ], monthly_sales=0, terms_days=30, monthly_noise_pct=0)


def test_expenses_totals_and_forecast_agree(client):
    assert client.post('/api/plan', json=expense_plan()).status_code == 200
    response = client.get('/api/expenses')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['recurring_monthly_total'] == 84000
    assert data['next_7_days'] == 3000
    assert data['next_30_days'] == 87000
    assert data['overdue_supplier_total'] == 4000
    assert data['recurring_categories']['salary'] == 60000
    assert all(row['id'] != 'b3' for row in data['upcoming'])
    assert next(row for row in data['obligations'] if row['id'] == 'utility')['next_due'] == '2026-10-31'
    november_utilities = next(row for row in data['upcoming'] if row['id'] == 'utility' and row['date'].startswith('2026-11'))
    assert november_utilities['date'] == '2026-11-30'
    assert client.get('/api/business').json()['opening_cash'] == 0
    forecast = client.get('/api/forecast').json()
    expected = sum(row['amount'] for row in data['upcoming']) + data['overdue_supplier_total']
    assert forecast['p50'][-1] == -expected
    assert sum(data['calendar_month_totals'].values()) == sum(row['amount'] for row in data['upcoming'])


def test_expenses_are_private_and_categories_validated(client):
    client.post('/api/plan', json=expense_plan())
    other = signed_in_client('another@example.com')
    assert other.get('/api/expenses').json()['recurring_monthly_total'] == 0
    bad = expense_plan()
    bad['obligations'][0]['category'] = 'unsupported'
    assert client.post('/api/plan', json=bad).status_code == 422
    assert client.get('/api/expenses').json()['recurring_monthly_total'] == 84000
