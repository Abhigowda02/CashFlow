from engine.shortage import analyse, with_delta

def test_summary_reports_gap_and_days():
    forecast={'safety_floor':100,'shortage_prob':.5,'first_shortage_date':'2026-01-02','dates':['2026-01-01','2026-01-02'],'p10':[90,50],'p50':[120,80]}
    value=analyse(forecast)
    assert value['peak_funding_gap']==50 and value['days_below_floor']==1 and value['days_until_shortage']==1
def test_delta_is_additive():
    base=analyse({'safety_floor':0,'shortage_prob':0,'first_shortage_date':None,'dates':['2026-01-01'],'p10':[0],'p50':[0]})
    assert with_delta(base,base)['deltas']['peak_funding_gap']==0
