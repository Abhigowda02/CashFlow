from engine.reminders import customer_reminder_drafts, manual_reminder_drafts
def _business(due='2026-10-24', status='open', disputed=False, contact=True):
    return {'customers':[{'id':'C1','name':'Asha','phone':'919999999999' if contact else None,'email':'a@example.com' if contact else None,'collection_context':{'disputed_invoice_ids':['I1'] if disputed else []}}],'invoices':[{'id':'I1','customer_id':'C1','amount':120000,'received_amount':0,'due_date':due,'status':status}]}
def test_boundaries():
    assert [customer_reminder_drafts(_business(),d)[0]['stage'] for d in ['2026-10-21','2026-10-24','2026-10-27','2026-10-31','2026-11-08','2026-11-23']]==['pre_due','due','overdue_3','overdue_7','overdue_15','legal_draft']
def test_paid_and_disputed_skip(): assert not customer_reminder_drafts(_business(status='paid'),'2026-10-24') and not customer_reminder_drafts(_business(disputed=True),'2026-10-24')
def test_legal_not_sendable(): assert not customer_reminder_drafts(_business(),'2026-11-23')[0]['sendable']
def test_links_only_with_contact():
    row=customer_reminder_drafts(_business(),'2026-10-24')[0]; assert row['whatsapp_link'].startswith('https://wa.me/') and row['mailto_link'].startswith('mailto:')
    assert customer_reminder_drafts(_business(contact=False),'2026-10-24')[0]['sms_link'] is None
def test_manual_lead_time():
    item={'type':'rent','title':'Rent','amount':1,'due_date':'2026-10-24','lead_time_days':3}; assert manual_reminder_drafts([item],'2026-10-21') and not manual_reminder_drafts([item],'2026-10-20')
