/**
 * Frozen contract layer TypeScript types mirroring shared/schema.py.
 * Do not edit except by deliberate decision; synchronized with shared/validate.py.
 */

export type InvoiceStatus = 'open' | 'paid' | 'disputed' | 'cancelled';

export interface Invoice {
  id: string;
  customer_id: string;
  amount: number;
  issue_date: string;
  due_date: string;
  status: InvoiceStatus;
  paid_date?: string | null;
  customer_name?: string | null;
  description?: string | null;
}

export type CustomerSegment = 'government' | 'corporate' | 'small';

export interface Customer {
  id: string;
  name: string;
  segment?: CustomerSegment | null;
  payment_terms_days?: number | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  gstin?: string | null;
  notes?: string | null;
}

export type TransactionDirection = 'credit' | 'debit';
export type TransactionSource = 'statement' | 'sms' | 'aa' | 'manual' | 'synthetic';

export interface Transaction {
  id: string;
  date: string;
  amount: number;
  direction: TransactionDirection;
  description: string;
  balance?: number | null;
  source: TransactionSource;
  dedupe_hash: string;
}

export type ObligationFrequency = 'monthly' | 'weekly' | 'quarterly' | 'yearly';
export type ObligationCategory = 'payroll' | 'rent' | 'emi' | 'tax' | 'utility' | 'vendor' | 'other';
export type ProposedStatus = 'pending' | 'approved' | 'rejected';

export interface ProposedObligation {
  id: string;
  name: string;
  amount: number;
  frequency: ObligationFrequency;
  day_of_month?: number | null;
  category?: ObligationCategory | null;
  confidence: number;
  detected_from_transaction_ids?: string[];
  status: ProposedStatus;
}

export type MatchType = 'invoice_receipt' | 'supplier_payment' | 'obligation' | 'other';
export type MatchStatus = 'pending' | 'confirmed' | 'rejected';

export interface ProposedMatch {
  id: string;
  transaction_id: string;
  invoice_id?: string | null;
  bill_id?: string | null;
  confidence: number;
  match_type: MatchType;
  notes?: string | null;
  status: MatchStatus;
}

export type WhyType = 'late_invoice' | 'obligation' | 'supplier_bill' | 'sales_inflow' | 'other';

export interface WhyItem {
  type: WhyType;
  ref: string;
  text: string;
  amount: number;
  expected_date: string;
  spread_days: number;
}

export interface ForecastAccuracy {
  mape?: number | null;
  bias?: number | null;
  backtest_days?: number | null;
  evaluated_at?: string | null;
}

export interface ForecastView {
  headline: string;
  generated_at: string;
  as_of: string;
  cash_last_updated: string;
  stale: boolean;
  dates: string[];
  p10: number[];
  p50: number[];
  p90: number[];
  safety_floor: number;
  shortage_prob: number;
  first_shortage_date?: string | null;
  min_balance_p50: number;
  why: WhyItem[];
  warnings: string[];
  accuracy?: ForecastAccuracy | null;
}

export type RiskLevel = 'low' | 'medium' | 'high';

export interface InvoiceForecast {
  invoice_id: string;
  expected_pay_date: string;
  p_by_30d: number;
  prob_late: number;
  risk: RiskLevel;
}

export type AlertKind = 'shortage_warning' | 'late_invoice' | 'msme_due' | 'stale_cash' | 'new_match' | 'other';
export type AlertSeverity = 'info' | 'warning' | 'critical';

export interface Alert {
  id: string;
  kind: AlertKind;
  severity: AlertSeverity;
  title: string;
  body: string;
  created_at: string;
  read: boolean;
  dedupe_key: string;
  link?: string | null;
}

export interface ActionEffect {
  shortage_prob_before: number;
  shortage_prob_after: number;
  first_shortage_before?: string | null;
  first_shortage_after?: string | null;
  runway_days_gained: number;
}

export interface ActionExecute {
  kind: string;
  payload: Record<string, unknown>;
}

export type ActionType = 'chase_invoice' | 'early_discount' | 'invoice_discounting' | 'delay_supplier' | 'overdraft' | 'cut_expense';

export interface ActionCard {
  id: string;
  type: ActionType;
  title: string;
  who: string;
  amount: number;
  by_date: string;
  effect: ActionEffect;
  cost: number;
  risk: RiskLevel;
  note: string;
  execute: ActionExecute;
}

export type ReminderChannel = 'email' | 'whatsapp' | 'sms' | 'letter';
export type ReminderStatus = 'draft' | 'approved' | 'sent';

export interface Reminder {
  id: string;
  invoice_ids: string[];
  customer_id: string;
  rung: number;
  channel: ReminderChannel;
  subject: string;
  body: string;
  status: ReminderStatus;
  created_at: string;
  sent_at?: string | null;
}
