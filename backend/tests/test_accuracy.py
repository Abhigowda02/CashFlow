from backend.modules.accuracy import alert_hit_rate, badge_text, coverage, empirical_fit, empirical_predict, live_accuracy, payment_date_mae, walk_forward

def test_mae_and_empty(): assert payment_date_mae([{'actual':'2026-01-03','predicted':'2026-01-01'}]) == 2 and payment_date_mae([]) is None
def test_coverage_inclusive(): assert coverage(['2026-01-02'], ['2026-01-02'], ['2026-01-02']) == 1
def test_alert_rate(): assert alert_hit_rate([.9,.1],[True,False])['f1'] == 1
def test_alert_lengths_validate():
    import pytest
    with pytest.raises(ValueError): alert_hit_rate([.5], [])
def test_empirical_baseline(): assert empirical_predict(empirical_fit([{'due_date':'2026-01-01','paid_date':'2026-01-03'}]), {'due_date':'2026-01-01'})['predicted'] == '2026-01-03'
def test_walk_forward_never_trains_on_future_settlement():
    rows=[{'issue_date':'2026-01-01','due_date':'2026-01-05','paid_date':'2026-01-06'},{'issue_date':'2026-01-02','due_date':'2026-01-05','paid_date':'2026-01-10'}]
    assert walk_forward(rows,['2026-01-07'],empirical_fit,empirical_predict)['cutoffs'][0]['n_train']==1
def test_live_needs_fourteen_days(): assert live_accuracy([], []) is None
def test_live_metrics():
    logs=[{'date':f'2026-01-{day:02}','p10':90,'p50':100,'p90':110} for day in range(1,15)]; actual=[{'date':row['date'],'balance':100} for row in logs]
    assert live_accuracy(logs,actual)['coverage']==1
def test_badge_honest_copy(): assert 'Live accuracy builds' in badge_text({'mae':2,'coverage':.8},None)
