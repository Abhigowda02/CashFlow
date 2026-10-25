import { useState, type FormEvent } from 'react';
import { apiRequest } from './api';
type Obligation = { id: string; name: string; amount: number; day_of_month: number; frequency: 'monthly'; category?: string };
type Bill = { id: string; supplier: string; amount: number; due_date: string; is_msme: boolean; status: 'open' | 'paid' };
export type PlanBusiness = { obligations?: Obligation[]; supplier_bills?: Bill[];
  sales_plan?: { monthly_amount: number; terms_days: number; monthly_noise_pct: number } };

export default function WorkspacePlan({ apiUrl, business, onChanged }: {
  apiUrl: string; business: PlanBusiness & { as_of: string }; onChanged: () => Promise<void>;
}) {
  const [obligations, setObligations] = useState<Obligation[]>(business.obligations ?? []);
  const [bills, setBills] = useState<Bill[]>(business.supplier_bills ?? []);
  const [sales, setSales] = useState(business.sales_plan?.monthly_amount ?? 0);
  const [terms, setTerms] = useState(business.sales_plan?.terms_days ?? 30);
  const [noise, setNoise] = useState(business.sales_plan?.monthly_noise_pct ?? 15);
  const [asOf, setAsOf] = useState(business.as_of);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      await apiRequest(`${apiUrl}/plan`, { obligations, supplier_bills: bills, monthly_sales: sales, terms_days: terms, monthly_noise_pct: noise, as_of: asOf });
      await onChanged();
    } catch (e) { setError(e instanceof Error ? e.message : 'Save failed'); }
    finally { setBusy(false); }
  }
  return <form className="panel-card space-y-5 p-5" onSubmit={save}>
    <div><h2 className="font-semibold">Outflows & future sales</h2><p className="mt-1 text-xs leading-5 text-slate-500">Enter your actual salary, rent, EMI or tax schedules. Dates are supplied by you; tax deadlines are not automatically verified. Changes affect forecasts, not current cash.</p></div>
    {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
    <div className="space-y-1.5">
      <label className="block text-xs font-semibold text-slate-700">Observation date (as_of)<input className="field-input mt-1" required type="date" min={business.as_of} value={asOf} onChange={e => setAsOf(e.target.value)} /></label>
      <p className="text-[11px] leading-relaxed text-slate-500">
        <strong>Accounting principle:</strong> CashFlow anchors to this Observation Date (<span className="font-mono text-slate-700">{business.as_of}</span>) and does not automatically tick forward with your computer&apos;s clock. When tomorrow arrives, the app does not silently advance the date by 1 day and pretend bank debits happened. In financial accounting, bank balances must be reconciled against actual bank statements, not guessed by a timer.
      </p>
    </div>
    <fieldset className="space-y-3"><legend className="mb-2 text-sm font-semibold">Recurring monthly obligations</legend>
      {obligations.map((item, index) => <div className="grid items-end gap-2 sm:grid-cols-2 xl:grid-cols-[2fr_1.2fr_1fr_1fr_auto]" key={item.id}>
        <label className="text-xs">Description<input className="field-input mt-1" required value={item.name} onChange={e => setObligations(obligations.map((row, i) => i === index ? { ...row, name: e.target.value } : row))} /></label>
        <label className="text-xs">Category<select className="field-input mt-1" value={item.category ?? 'other'} onChange={e => setObligations(obligations.map((row, i) => i === index ? { ...row, category: e.target.value } : row))}>
          <option value="salary">Salary & payroll</option><option value="rent">Rent</option><option value="loan">EMI & loan</option><option value="tax">GST, TDS & taxes</option><option value="utilities">Utilities</option><option value="subscription">Subscriptions</option><option value="insurance">Insurance</option><option value="other">Other</option>
        </select></label>
        <label className="text-xs">INR<input className="field-input mt-1" type="number" required min="0" step="1" value={item.amount} onChange={e => setObligations(obligations.map((row, i) => i === index ? { ...row, amount: Number(e.target.value) } : row))} /></label>
        <label className="text-xs">Day of month<input className="field-input mt-1" type="number" required min="1" max="31" value={item.day_of_month} onChange={e => setObligations(obligations.map((row, i) => i === index ? { ...row, day_of_month: Number(e.target.value) } : row))} /></label>
        <button type="button" className="button-secondary" aria-label={`Remove ${item.name || 'obligation'}`} onClick={() => setObligations(obligations.filter((_, i) => i !== index))}>Remove</button>
      </div>)}
      <p className="text-xs text-slate-500">Days 29–31 fall on the last day in shorter months.</p>
      <button className="button-secondary" type="button" onClick={() => setObligations([...obligations, { id: crypto.randomUUID(), name: '', amount: 0, day_of_month: 1, frequency: 'monthly', category: 'other' }])}>Add obligation</button>
    </fieldset>
    <fieldset className="space-y-3"><legend className="mb-2 text-sm font-semibold">Supplier bills</legend>
      {bills.map((bill, index) => <div className="grid items-end gap-2 rounded-xl bg-slate-50 p-3 sm:grid-cols-3" key={bill.id}>
        <label className="text-xs">Supplier<input className="field-input mt-1" required value={bill.supplier} onChange={e => setBills(bills.map((row, i) => i === index ? { ...row, supplier: e.target.value } : row))} /></label>
        <label className="text-xs">INR<input className="field-input mt-1" type="number" required min="0" step="1" value={bill.amount} onChange={e => setBills(bills.map((row, i) => i === index ? { ...row, amount: Number(e.target.value) } : row))} /></label>
        <label className="text-xs">Due date<input className="field-input mt-1" type="date" required value={bill.due_date} onChange={e => setBills(bills.map((row, i) => i === index ? { ...row, due_date: e.target.value } : row))} /></label>
        <label className="flex gap-2 text-xs"><input type="checkbox" checked={bill.is_msme} onChange={e => setBills(bills.map((row, i) => i === index ? { ...row, is_msme: e.target.checked } : row))} />Micro/small enterprise supplier</label>
        <span className="text-xs text-slate-500">Status: {bill.status}</span>
        <button type="button" className="button-secondary" onClick={() => setBills(bills.filter((_, i) => i !== index))}>Remove bill</button>
      </div>)}
      <button className="button-secondary" type="button" onClick={() => setBills([...bills, { id: crypto.randomUUID(), supplier: '', amount: 0, due_date: business.as_of, status: 'open', is_msme: false }])}>Add supplier bill</button>
    </fieldset>
    <div className="grid gap-3 sm:grid-cols-3">
      <label className="text-xs">Expected monthly sales (INR)<input className="field-input mt-1" type="number" required min="0" step="1" value={sales} onChange={e => setSales(Number(e.target.value))} /></label>
      <label className="text-xs">Payment terms (days)<input className="field-input mt-1" type="number" required min="0" max="365" step="1" value={terms} onChange={e => setTerms(Number(e.target.value))} /></label>
      <label className="text-xs">Sales uncertainty (%)<input className="field-input mt-1" type="number" required min="0" max="100" step="1" value={noise} onChange={e => setNoise(Number(e.target.value))} /></label>
    </div>
    <button className="button-primary" disabled={busy}>{busy ? 'Saving…' : 'Save plan & refresh forecast'}</button>
  </form>;
}
