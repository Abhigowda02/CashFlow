export type ScenarioChange =
  | { type: 'delay_customer'; customer_id: string; extra_days: number; invoice_ids?: string[] }
  | { type: 'sales_change'; pct: number; from_date?: string; duration_days?: number }
  | { type: 'extra_expense'; amount: number; date: string; category?: string; label?: string; repeat?: 'once'|'monthly'; repeat_count?: number }
  | { type: 'supplier_terms'; extra_days: number; direction?: 'extend'|'shorten'; supplier_id?: string }
  | { type: 'revised_payment_schedule'; invoice_id?: string; customer_id?: string; installments: {date:string;amount:number}[]; reliability?: number };
export type ScenarioDefinition = { name: string; changes: ScenarioChange[] };
export type SavedScenario = ScenarioDefinition & { id: string; created_at: string; updated_at: string };
export type ChangeDraft = { key: string; type: ScenarioChange['type']; customer_id?: string;
  extra_days?: string; pct?: string; amount?: string; date?: string; category?: string; label?: string; invoice_id?: string; installments?: { date: string; amount: string }[]; reliability?: string };
export type PlannerDraft = { name: string; changes: ChangeDraft[] };
export type PlannerBusiness = { as_of: string; customers: { id: string; name: string; segment: string }[];
  invoices: { id: string; customer_id: string; amount: number; received_amount?: number; status: string; due_date: string }[];
  supplier_bills?: { id: string; amount: number; status: string; is_msme: boolean }[];
  sales_plan?: { monthly_amount: number } };
export type PlannerForecast = { dates: string[]; p10: number[]; p50: number[]; p90: number[];
  safety_floor: number; shortage_prob: number; first_shortage_date: string | null; min_balance_p50: number;
  shortage_analysis?: { first_shortage_date: string | null; shortage_probability: number; peak_funding_gap: number };
  meta?: { delay_model_used?: string } };
export type ScenarioResult = { baseline: PlannerForecast; scenario: PlannerForecast };

export function eligibleCustomers(business: PlannerBusiness) {
  return business.customers.map(customer => {
    const invoices = business.invoices.filter(invoice => invoice.customer_id === customer.id && invoice.status === 'open' && invoice.amount > (invoice.received_amount ?? 0));
    return { ...customer, invoice_count: invoices.length,
      outstanding: invoices.reduce((sum, invoice) => sum+invoice.amount-(invoice.received_amount ?? 0), 0) };
  }).filter(customer => customer.outstanding > 0);
}

export function horizonEnd(asOf: string) {
  const end = new Date(`${asOf}T12:00:00Z`);
  end.setUTCDate(end.getUTCDate()+89);
  return end.toISOString().slice(0, 10);
}

export function buildDefinition(draft: PlannerDraft, business: PlannerBusiness) {
  const errors: string[] = [], changes: ScenarioChange[] = [];
  const eligible = new Set(eligibleCustomers(business).map(customer => customer.id));
  const seenCustomers = new Set<string>(), singles = new Set<string>();
  if (draft.name.trim().length > 120) errors.push('Use a scenario name of at most 120 characters.');
  if (draft.changes.length > 20) errors.push('Use at most 20 changes in one scenario.');
  for (const [index, row] of draft.changes.entries()) {
    const label = `Change ${index+1}`;
    if (row.type === 'delay_customer') {
      const extra = Number(row.extra_days);
      if (!row.customer_id || !eligible.has(row.customer_id)) errors.push(`${label}: choose a customer with outstanding invoices.`);
      if (row.customer_id && seenCustomers.has(row.customer_id)) errors.push(`${label}: this customer already has a delay; edit the existing change.`);
      if (!row.extra_days?.trim() || !Number.isInteger(extra) || extra < 1 || extra > 180) errors.push(`${label}: enter 1–180 extra days.`);
      seenCustomers.add(row.customer_id ?? '');
      changes.push({ type: row.type, customer_id: row.customer_id ?? '', extra_days: extra });
    } else if (row.type === 'extra_expense') {
      const amount = Number(row.amount);
      if (!row.amount?.trim() || !Number.isSafeInteger(amount) || amount <= 0) errors.push(`${label}: enter a positive whole INR amount.`);
      const parsed = new Date(`${row.date}T12:00:00Z`);
      if (!row.date || !/^\d{4}-\d{2}-\d{2}$/.test(row.date) || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== row.date || row.date < business.as_of || row.date > horizonEnd(business.as_of)) errors.push(`${label}: choose a payment date inside this 90-day forecast.`);
      changes.push({ type: row.type, amount, date: row.date ?? '', category: row.category ?? 'other', label: row.label?.trim() || undefined });
    } else if (row.type === 'sales_change') {
      const pct = Number(row.pct);
      if (!row.pct?.trim() || !Number.isFinite(pct) || pct < -100 || pct > 100 || pct === 0) errors.push(`${label}: enter a nonzero sales change between −100% and +100%.`);
      if (!(business.sales_plan?.monthly_amount)) errors.push(`${label}: enter future monthly sales in Expenses & obligations first; changing zero sales has no effect.`);
      if (singles.has(row.type)) errors.push(`${label}: edit the existing sales change instead of adding another.`);
      singles.add(row.type);
      changes.push({ type: row.type, pct });
    } else if (row.type === 'supplier_terms') {
      const extra = Number(row.extra_days);
      if (!row.extra_days?.trim() || !Number.isInteger(extra) || extra < 1 || extra > 180) errors.push(`${label}: enter a supplier extension of 1–180 days.`);
      if (!business.supplier_bills?.some(bill => bill.status === 'open')) errors.push(`${label}: add an open supplier bill before extending its terms.`);
      if (singles.has(row.type)) errors.push(`${label}: edit the existing supplier extension instead of adding another.`);
      singles.add(row.type);
      changes.push({ type: row.type, extra_days: extra });
    } else {
      const invoice = business.invoices.find(item => item.id === row.invoice_id && item.status === 'open');
      const installments = row.installments ?? [];
      const total = installments.reduce((sum, item) => sum + Number(item.amount), 0);
      const outstanding = invoice ? invoice.amount - (invoice.received_amount ?? 0) : 0;
      if (!invoice) errors.push(`${label}: choose an open invoice.`);
      if (!installments.length || installments.length > 6 || installments.some(item => !Number.isSafeInteger(Number(item.amount)) || Number(item.amount) <= 0 || !item.date || item.date < business.as_of || item.date > horizonEnd(business.as_of))) errors.push(`${label}: enter up to 6 positive instalments dated within the forecast horizon.`);
      if (total !== outstanding) errors.push(`${label}: instalments must total the outstanding amount.`);
      changes.push({ type: row.type, invoice_id: row.invoice_id, installments: installments.map(item => ({ date: item.date, amount: Number(item.amount) })), reliability: row.reliability ? Number(row.reliability) : .9 });
    }
  }
  return { errors, definition: { name: draft.name.trim() || 'Unsaved scenario', changes } as ScenarioDefinition };
}

export function definitionSignature(definition: ScenarioDefinition, model: string) {
  return JSON.stringify({ definition, model });
}

export function runwayDays(forecast: PlannerForecast) {
  const index = forecast.p50.findIndex(amount => amount < forecast.safety_floor);
  return index < 0 ? null : index;
}

export function baselineSignature(forecast: PlannerForecast) {
  return JSON.stringify([forecast.dates, forecast.p50, forecast.shortage_prob, forecast.first_shortage_date,
    forecast.min_balance_p50, forecast.safety_floor, forecast.meta?.delay_model_used]);
}

export function changeDescription(change: ScenarioChange, business: PlannerBusiness) {
  const money = (amount: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amount);
  if (change.type === 'delay_customer') {
    const customer = eligibleCustomers(business).find(row => row.id === change.customer_id);
    const name = business.customers.find(row => row.id === change.customer_id)?.name ?? change.customer_id;
    return `${name} pays ${change.extra_days} days later across ${customer?.invoice_count ?? 0} unpaid invoices (${money(customer?.outstanding ?? 0)} outstanding).`;
  }
  if (change.type === 'extra_expense') return `Pay an additional ${money(change.amount)} on ${change.date}.`;
  if (change.type === 'sales_change') return `${change.pct < 0 ? 'Reduce' : 'Increase'} projected future sales by ${Math.abs(change.pct)}%; existing invoices are unchanged.`;
  if (change.type === 'supplier_terms') return `${change.direction === 'shorten' ? 'Shorten' : 'Extend'} open supplier bills by ${change.extra_days} days, assuming suppliers agree.`;
  return `Use the reviewed instalment schedule with ${Math.round((change.reliability ?? .9) * 100)}% reliability.`;
}
