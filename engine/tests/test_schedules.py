from engine.schedules import monthly_occurrences


def test_short_month_and_leap_year_recurrences():
    obligations = [dict(id='emi', name='EMI', amount=500, day_of_month=31)]
    leap = monthly_occurrences(obligations, '2028-02-28', 3)
    assert [row['date'] for row in leap] == ['2028-02-29']
    ordinary = monthly_occurrences(obligations, '2027-02-28', 2)
    assert ordinary[0]['date'] == '2027-02-28'
    assert ordinary[0]['days_until'] == 0
    assert ordinary[0]['category'] == 'other'


def test_window_is_half_open_and_does_not_include_past_occurrences():
    obligations = [dict(id='rent', name='Rent', amount=100, day_of_month=1)]
    assert monthly_occurrences(obligations, '2026-10-02', 30) == []
    assert monthly_occurrences(obligations, '2026-10-02', 31)[0]['date'] == '2026-11-01'
