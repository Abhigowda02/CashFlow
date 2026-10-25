"""Pure, review-only reminder draft generation from business dictionaries."""
from __future__ import annotations
from datetime import date
from enum import StrEnum
from urllib.parse import quote
from .forecast import format_inr

class ReminderType(StrEnum):
    CUSTOMER_PAYMENT_OVERDUE='customer_payment_overdue'; ELECTRICITY_BILL='electricity_bill'; GAS_BILL='gas_bill'; WATER_BILL='water_bill'; RENT='rent'; SALARY='salary'; LOAN_EMI='loan_emi'; GST_TAX='gst_tax'; INSURANCE='insurance'; SUPPLIER_PAYMENT='supplier_payment'; CUSTOM='custom'

def _links(phone: str | None, email: str | None, text: str, subject: str) -> dict:
    return {'whatsapp_link': f'https://wa.me/{"".join(c for c in phone if c.isdigit())}?text={quote(text)}' if phone else None,
            'sms_link': f'sms:{phone}?body={quote(text)}' if phone else None,
            'mailto_link': f'mailto:{email}?subject={quote(subject)}&body={quote(text)}' if email else None}

def customer_reminder_drafts(business: dict, today: str) -> list[dict]:
    """Return one unsaved current-stage draft per eligible open invoice."""
    now=date.fromisoformat(today); customers={c['id']:c for c in business.get('customers',[])}; rows=[]
    for invoice in business.get('invoices',[]):
        outstanding=invoice.get('amount',0)-invoice.get('received_amount',0)
        if invoice.get('status')!='open' or outstanding<=0: continue
        customer=customers.get(invoice.get('customer_id'),{}); context=customer.get('collection_context',{})
        if invoice['id'] in context.get('disputed_invoice_ids',[]): continue
        delta=(now-date.fromisoformat(invoice['due_date'])).days
        stage= 'pre_due' if delta == -3 else 'due' if delta == 0 else 'overdue_3' if delta == 3 else 'overdue_7' if delta == 7 else 'overdue_15' if delta == 15 else 'legal_draft' if delta >= 30 else None
        if not stage: continue
        name=customer.get('name',invoice.get('customer_id','Customer')); legal=stage=='legal_draft'; subject=('DRAFT – advocate review: ' if legal else 'Payment reminder: ')+invoice['id']
        body=(f"Dear {name}, invoice {invoice['id']} for {format_inr(outstanding)} was due on {invoice['due_date']} ({max(0,delta)} days overdue). Please arrange payment." if not legal else f"DRAFT – FOR ADVOCATE REVIEW ONLY. Invoice {invoice['id']} for {format_inr(outstanding)} is {delta} days overdue. This is not legal advice.")
        rows.append({'invoice_id':invoice['id'],'customer_id':invoice.get('customer_id'),'customer_name':name,'stage':stage,'type':ReminderType.CUSTOMER_PAYMENT_OVERDUE.value,'subject':subject,'body':body,'sendable':not legal,**_links(customer.get('phone') or customer.get('contact_phone'),customer.get('email') or customer.get('contact_email'),body,subject)})
    return rows

def manual_reminder_drafts(items: list[dict], today: str) -> list[dict]:
    """Return due manual reminder items without saving or sending them."""
    now=date.fromisoformat(today); rows=[]
    for item in items:
        due=date.fromisoformat(item['due_date']); lead=int(item.get('lead_time_days',0))
        if lead not in (0,1,3,7): raise ValueError('lead_time_days must be 0, 1, 3, or 7')
        if now >= due.fromordinal(due.toordinal()-lead): rows.append({**item,'days_until_due':(due-now).days})
    return rows
