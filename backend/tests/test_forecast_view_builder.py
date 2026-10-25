from backend.modules.forecast_view_builder import build_headline, build_why, compact_inr, format_inr, risk_label
def test_indian_format(): assert format_inr(120000)=='Rs 1,20,000'
def test_compact_lakh_and_crore(): assert compact_inr(120000)=='Rs 1.2L' and compact_inr(34000000)=='Rs 3.4Cr'
def test_stale_headline_wins(): assert 'old' in build_headline(.9,'2026-11-01',100000,True,False).lower()
def test_expense_disclosure(): assert 'only shows expected receipts' in build_headline(.9,None,1,False,True)
def test_low_risk_headline(): assert 'No cash shortage' in build_headline(.01,None,1,False,False)
def test_shortage_headline(): assert 'Rs 1.2L' in build_headline(.68,'2026-11-14',120000,False,False)
def test_risk_labels(): assert [risk_label(x) for x in [.1,.4,.8]]==['low','medium','high']
def test_why_ranked_and_limited(): assert build_why([{'id':'i','amount':1},{'id':'j','amount':2}],[{'id':'p','name':'Payroll','amount':3,'next_due_date':'2026-11-01'}],{},'2026-10-25',2)[0]['amount']==3
