import { useEffect, useState } from 'react';
import { apiRequest } from './api';
import WorkspacePlan, { type PlanBusiness } from './WorkspacePlan';
import { CalendarDays, ReceiptText } from 'lucide-react';

type Due = { id: string; name: string; amount: number; date: string; category: string; kind: string; days_until: number };
type Summary = { as_of: string; through: string; recurring_monthly_total: number; recurring_count: number;
  next_7_days: number; next_30_days: number; overdue_supplier_total: number;
  recurring_categories: Record<string, number>; calendar_month_totals: Record<string, number>;
  obligations: { id: string; name: string; category: string; amount: number; day_of_month: number; next_due: string }[];
  upcoming: Due[]; overdue_suppliers: Due[] };
const labels: Record<string, string> = { salary: 'Salary & payroll', rent: 'Rent', loan: 'EMI & loans', tax: 'GST, TDS & taxes', utilities: 'Utilities', subscription: 'Subscriptions', insurance: 'Insurance', other: 'Other', supplier: 'Supplier bill' };
const money = (value: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value);
const dateLabel = (value: string) => new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`));

export default function ExpensesPage({ apiUrl, business, onChanged }: {
  apiUrl: string; business: PlanBusiness & { as_of: string }; onChanged: () => Promise<void>;
}) {
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState('');
  const [manage, setManage] = useState(false);
  const [category, setCategory] = useState('all');
  const [horizon, setHorizon] = useState(30);
  const [search, setSearch] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    apiRequest<Summary>(`${apiUrl}/expenses`, undefined, controller.signal).then(result => { if (!controller.signal.aborted) setData(result); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [apiUrl, business]);
  const upcoming = data?.upcoming.filter(row => row.days_until < horizon && (category === 'all' || row.category === category) && row.name.toLowerCase().includes(search.toLowerCase())) ?? [];
  const cards = data ? [
    ['Recurring monthly total', money(data.recurring_monthly_total), `${data.recurring_count} monthly obligations`],
    ['Due in next 7 days', money(data.next_7_days), 'Scheduled from the observation date'],
    ['Due in next 30 days', money(data.next_30_days), 'Recurring obligations and supplier bills'],
    ['Overdue supplier bills', money(data.overdue_supplier_total), 'Open bills due before the observation date'],
  ] : [];
  return <div className="space-y-5">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow">SPENDING PLAN</p><h1 className="mt-1.5 text-[28px] font-semibold tracking-tight">Expenses & obligations</h1>
      <p className="mt-2 text-sm text-slate-500">Salary, rent, loan instalments, taxes and other recurring commitments in one place.</p></div>
      <button className={manage ? 'button-secondary' : 'button-primary'} onClick={() => setManage(!manage)}>{manage ? 'Back to expense dashboard' : 'Manage expenses & plan'}</button>
    </div>
    <p className="text-xs leading-5 text-slate-500">Scheduled amounts as of {dateLabel(business.as_of)}. These records feed the cash forecast; entering a plan does not record a bank debit. Recurring obligations currently repeat monthly.</p>
    {error && <p role="alert" className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
    {manage ? <WorkspacePlan apiUrl={apiUrl} business={business} onChanged={onChanged} /> : !data && !error ? <div role="status" className="panel-card p-8 text-sm text-slate-500">Loading your expense schedule…</div> : data && <>
      <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">{cards.map(([label, value, detail]) => <section className="panel-card p-5" key={label}>
        <p className="text-xs text-slate-500">{label}</p><p className="mt-3 text-2xl font-semibold tracking-tight">{value}</p><p className="mt-2 text-[11px] leading-5 text-slate-400">{detail}</p>
      </section>)}</div>
      {!data.recurring_count && !data.upcoming.length && !data.overdue_suppliers.length && <section className="panel-card p-10 text-center"><ReceiptText size={28} className="mx-auto text-slate-400" /><h2 className="mt-4 text-sm font-semibold">Build your expense plan</h2><p className="mx-auto mt-2 max-w-lg text-xs leading-5 text-slate-500">Add salary, rent, EMI, tax, utility and subscription commitments. Add supplier bills with their due dates. Their outflows will appear here and in your forecast.</p><button className="button-primary mt-5" onClick={() => setManage(true)}>Add expenses</button></section>}
      {data.overdue_suppliers.length > 0 && <section className="rounded-lg border border-amber-200 bg-amber-50/50 p-5"><h2 className="text-sm font-semibold text-amber-900">Overdue supplier bills need review</h2><p className="mt-1 text-xs text-amber-800">These are separate from the next-7/30-day totals. The forecast treats overdue open supplier bills as immediate obligations.</p>
        <div className="mt-3 divide-y divide-amber-200/60">{data.overdue_suppliers.map(row => <div key={row.id} className="flex flex-wrap justify-between gap-2 py-3 text-xs"><span>{row.name} · due {dateLabel(row.date)} · {Math.abs(row.days_until)} days overdue</span><strong>{money(row.amount)}</strong></div>)}</div>
      </section>}
      <div className="grid items-start gap-5 xl:grid-cols-2">
        <section className="panel-card p-5"><h2 className="text-sm font-semibold">Monthly recurring breakdown</h2><p className="mt-1 text-xs text-slate-500">Categories are assigned by you in Manage expenses & plan.</p>
          <div className="mt-5 space-y-4">{Object.entries(data.recurring_categories).map(([name, amount]) => <div key={name}><div className="mb-2 flex justify-between text-xs"><span className="text-slate-600">{labels[name] ?? name}</span><strong className="font-medium">{money(amount)}</strong></div><div aria-hidden="true" className="h-1.5 overflow-hidden rounded bg-slate-100"><div className="h-full rounded bg-indigo-500" style={{ width: `${data.recurring_monthly_total ? amount/data.recurring_monthly_total*100 : 0}%` }} /></div></div>)}
            {!data.recurring_count && <p className="py-4 text-xs text-slate-400">No recurring expenses entered.</p>}
          </div>
        </section>
        <section className="panel-card p-5"><h2 className="text-sm font-semibold">Scheduled by calendar month</h2><p className="mt-1 text-xs leading-5 text-slate-500">Recurring obligations and open supplier bills from {dateLabel(data.as_of)} to {dateLabel(data.through)}. First and last months may be partial.</p>
          <div className="mt-5 divide-y divide-slate-100">{Object.entries(data.calendar_month_totals).map(([month, amount]) => <div key={month} className="flex items-center justify-between gap-3 py-4 text-sm"><span className="flex items-center gap-2 text-slate-600"><CalendarDays size={16} />{new Intl.DateTimeFormat('en-IN', { month: 'long', year: 'numeric' }).format(new Date(`${month}-01T12:00:00`))}</span><strong className="font-semibold">{money(amount)}</strong></div>)}
            {!data.upcoming.length && <p className="py-4 text-xs text-slate-400">No outflows scheduled in this window.</p>}
          </div>
        </section>
      </div>
      <section className="panel-card overflow-hidden"><div className="p-5"><h2 className="text-sm font-semibold">All recurring expenses</h2><p className="mt-1 text-xs text-slate-500">Day 29–31 uses the last day in shorter months. Tax dates are user supplied and are not verified automatically.</p></div>
        <div className="overflow-x-auto"><table className="expense-table"><thead><tr><th>Expense</th><th>Category</th><th>Frequency</th><th>Monthly amount</th><th>Next due</th></tr></thead><tbody>{data.obligations.map(row => <tr key={row.id}><td className="font-medium">{row.name}</td><td>{labels[row.category] ?? row.category}</td><td>Monthly · day {row.day_of_month}</td><td>{money(row.amount)}</td><td>{dateLabel(row.next_due)}</td></tr>)}</tbody></table></div>
        {!data.recurring_count && <p className="p-8 text-center text-xs text-slate-500">Add recurring obligations to see them here.</p>}
      </section>
      <section className="panel-card overflow-hidden"><div className="p-5"><h2 className="text-sm font-semibold">Upcoming payments</h2><div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="min-w-[180px] flex-1 text-xs text-slate-500">Search expenses<input className="field-input mt-1" value={search} onChange={event => setSearch(event.target.value)} placeholder="Salary, EMI, supplier…" /></label>
        <label className="text-xs text-slate-500">Category<select className="field-input mt-1" value={category} onChange={event => setCategory(event.target.value)}><option value="all">All categories</option>{Object.entries(labels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        <label className="text-xs text-slate-500">Period<select className="field-input mt-1" value={horizon} onChange={event => setHorizon(Number(event.target.value))}><option value={7}>Next 7 days</option><option value={30}>Next 30 days</option><option value={90}>Next 90 days</option></select></label>
      </div></div>
        <div className="overflow-x-auto"><table className="expense-table"><thead><tr><th>Due date</th><th>Expense</th><th>Category</th><th>Type</th><th>Amount</th></tr></thead><tbody>{upcoming.map(row => <tr key={`${row.kind}:${row.id}:${row.date}`}><td>{dateLabel(row.date)}{row.days_until === 0 && <span className="invoice-status ml-2">Today</span>}</td><td className="font-medium">{row.name}</td><td>{labels[row.category] ?? row.category}</td><td><span className="invoice-status">{row.kind === 'recurring' ? 'Recurring' : 'Supplier bill'}</span></td><td>{money(row.amount)}</td></tr>)}</tbody></table></div>
        {!upcoming.length && <p className="p-8 text-center text-xs text-slate-500">No scheduled payments match this view.</p>}
        <div className="border-t border-slate-100 px-5 py-4 text-xs text-slate-500">{upcoming.length} scheduled payments · Filtered total: <strong className="font-semibold text-slate-800">{money(upcoming.reduce((total, row) => total+row.amount, 0))}</strong></div>
      </section>
    </>}
  </div>;
}
