import { useEffect, useState } from 'react';
import { apiRequest } from './api';
import { RefreshCw, Users, ArrowRight, Send } from 'lucide-react';
import CustomerContextForm, { type CollectionContext } from './CustomerContextForm';
import ReminderSheet, { type ReminderData } from './ReminderSheet';

type Prediction = { invoice_id: string; outstanding: number; due_date: string; status: string;
  probability_7_days: number | null; probability_30_days: number | null; probability_60_days: number | null;
  paid_by_70: string | null; paid_by_90: string | null };
type Customer = { id: string; name: string; segment: string; invoice_count: number; paid_count: number;
  unpaid_count: number; outstanding: number; median_delay: number | null; average_delay: number | null;
  delay_std: number | null; on_time_share: number | null; prediction_basis: string; invoices: Prediction[];
  collection_context: CollectionContext | null };
type Profiles = { as_of: string; model: { status: string; message: string; trained_at: string | null;
  invoice_count: number; paid_count: number; censored_count: number;
  amount_feature_used?: boolean; amount_feature_policy?: string }; customers: Customer[] };
const money = (value: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value);
const percent = (value: number | null) => value === null ? 'Not estimated' : `${Math.round(value * 100)}%`;
const days = (value: number | null) => value === null ? 'No paid history' : `${Math.round(value * 10) / 10} days`;
const dateLabel = (value: string | null) => value ? new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`)) : 'Not estimated';
const basis: Record<string, string> = { customer_features: 'Customer features', segment_fallback: 'Segment fallback', business_pool: 'Business-wide fallback', not_fitted: 'Awaiting sufficient history' };

export default function CustomersPage({ apiUrl }: { apiUrl: string }) {
  const [data, setData] = useState<Profiles | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [activeReminder, setActiveReminder] = useState<ReminderData | null>(null);

  async function handleSendReminder(c: Customer) {
    try {
      const queue = await apiRequest<ReminderData[]>(`${apiUrl}/reminders/queue`);
      const found = queue.find((r) => r.customer_id === c.id);
      if (found) {
        setActiveReminder(found);
      } else {
        const invIds = c.invoices.map((i) => i.invoice_id);
        setActiveReminder({
          id: `REM-${c.id}`,
          customer_id: c.id,
          customer_name: c.name,
          invoice_ids: invIds.length ? invIds : ['DUE-RECV'],
          rung: 2,
          channel: 'email',
          subject: `Payment reminder: Reconciled dues for ${c.name}`,
          body: `Dear ${c.name},\n\nPlease arrange clearance of outstanding dues totaling ${money(c.outstanding)}.\n\nThank you,\nAccounts Team`,
          status: 'draft',
          total_amount: c.outstanding,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not prepare reminder draft');
    }
  }
  useEffect(() => {
    const controller = new AbortController();
    apiRequest<Profiles>(`${apiUrl}/customers`, undefined, controller.signal).then(result => {
      setData(result); setSelectedId(result.customers[0]?.id ?? '');
    }).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [apiUrl]);
  async function retrain() {
    setBusy(true); setError('');
    try {
      const result = await apiRequest<Profiles>(`${apiUrl}/customers/retrain`, {});
      setData(result);
      setSelectedId(current => result.customers.some(customer => customer.id === current) ? current : result.customers[0]?.id ?? '');
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not refresh model'); }
    finally { setBusy(false); }
  }
  const customer = data?.customers.find(row => row.id === selectedId);
  const filtered = data?.customers.filter(row => `${row.name} ${row.id} ${row.segment}`.toLowerCase().includes(search.toLowerCase())) ?? [];
  return <div className="space-y-5">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow">PAYMENT INTELLIGENCE</p>
      <h1 className="mt-1.5 text-[28px] font-semibold tracking-tight">Customer payment behaviour</h1>
      <p className="mt-2 text-sm text-slate-500">Understand who pays late and when your outstanding invoices may arrive.</p></div>
      <button className="button-secondary" disabled={busy || !data} onClick={() => void retrain()}><RefreshCw size={14} className={busy ? 'animate-spin' : ''} />{busy ? 'Updating…' : 'Refresh business model'}</button>
    </div>
    {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
    {!data && !error && <div role="status" className="panel-card p-8 text-sm text-slate-500">Building customer profiles from your business records…</div>}
    {data && <>
      <section className="panel-card p-4 text-xs leading-6 text-slate-600"><div className="flex flex-wrap items-center gap-2"><span className="risk-badge risk-medium">{data.model.status === 'ready' ? 'Fitted · Unvalidated' : data.model.status === 'insufficient_history' ? 'Building history' : 'Model unavailable'}</span>
        <span>{data.model.paid_count ?? 0} observed payments · {data.model.censored_count ?? 0} unpaid observations · As of {dateLabel(data.as_of)}</span></div>
        <p className="mt-2">{data.model.message}</p>
        {data.model.status === 'ready' && data.model.amount_feature_policy && <p>Invoice amount predictor: {data.model.amount_feature_used ? 'included' : 'excluded'}. {data.model.amount_feature_policy}</p>}
        {data.model.trained_at && <p>Last fitted {new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(data.model.trained_at))}. Automatically refreshed on the next request after relevant records change.</p>}
      </section>
      {!data.customers.length ? <section className="panel-card px-6 py-14 text-center"><Users size={27} className="mx-auto text-slate-400" /><h2 className="mt-4 text-sm font-semibold">Your customer profiles will appear here</h2><p className="mt-2 text-xs text-slate-500">Import invoices in Invoices & cash, then record payments as they arrive. No synthetic customers are added.</p></section> : <>
        <div className="grid items-start gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
          <section className="panel-card overflow-hidden"><div className="border-b border-slate-100 p-4"><h2 className="text-sm font-semibold">Customers <span className="ml-1 text-xs font-normal text-slate-400">{data.customers.length}</span></h2>
            <label className="mt-3 block text-xs text-slate-500">Search customers<input className="field-input mt-1" value={search} onChange={event => setSearch(event.target.value)} placeholder="Name, ID or segment" /></label></div>
            <div className="max-h-[520px] overflow-y-auto">{filtered.map(row => <button key={row.id} aria-pressed={selectedId === row.id} onClick={() => setSelectedId(row.id)} className={`flex w-full items-center justify-between gap-3 border-b border-slate-100 px-4 py-4 text-left ${selectedId === row.id ? 'bg-indigo-50' : 'hover:bg-slate-50'}`}>
              <div className="min-w-0"><p className="truncate text-xs font-semibold text-slate-800">{row.name}</p><p className="mt-1 text-[11px] capitalize text-slate-500">{row.segment} · {row.paid_count} paid invoices</p></div><ArrowRight size={14} className="shrink-0 text-slate-400" /></button>)}
              {!filtered.length && <p className="p-5 text-xs text-slate-500">No matching customers.</p>}
            </div>
          </section>
          {customer && <div className="min-w-0 space-y-5">
            <CustomerContextForm key={customer.id} apiUrl={apiUrl} customerId={customer.id} value={customer.collection_context}
              invoices={customer.invoices} onSaved={async () => { setData(await apiRequest<Profiles>(`${apiUrl}/customers`)); }} />
            <section className="panel-card p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-semibold tracking-tight">{customer.name}</h2><p className="mt-1 text-xs text-slate-500">{customer.id} · {customer.segment} · {customer.invoice_count} invoices</p></div>
              <div className="flex items-center gap-2">
                <span className="invoice-status">{basis[customer.prediction_basis]}</span>
                {customer.outstanding > 0 && (
                  <button
                    type="button"
                    className="button-primary py-1 px-3 text-xs inline-flex items-center gap-1.5"
                    onClick={() => void handleSendReminder(customer)}
                  >
                    <Send size={13} />
                    Send reminder
                  </button>
                )}
              </div>
            </div>
              <p className="mt-4 text-xs font-semibold text-slate-600">Observed invoice and payment history</p><div className="mt-3 grid grid-cols-2 gap-5 border-t border-slate-100 pt-5 sm:grid-cols-4">{[
                ['Outstanding', money(customer.outstanding)], ['Median delay', days(customer.median_delay)],
                ['Delay variability', customer.delay_std === null ? 'Need 2 payments' : `${Math.round(customer.delay_std * 10) / 10} days`], ['Paid on time', percent(customer.on_time_share)],
              ].map(([label, value]) => <div key={label}><p className="text-[11px] text-slate-500">{label}</p><p className="mt-2 text-base font-semibold tracking-tight">{value}</p></div>)}</div>
              <p className="mt-5 text-[11px] leading-5 text-slate-500">Statistics describe observed payments only. Negative delay means early payment; variability is the standard deviation. Unpaid and partly paid invoices are not counted as settled. Sparse customers use their segment or the pooled history of this business.</p>
            </section>
            <section className="panel-card overflow-hidden"><div className="p-5"><h2 className="text-sm font-semibold">Model estimates of payment timing</h2><p className="mt-1 text-xs leading-5 text-slate-500">Conditional on each invoice still being unpaid on {dateLabel(data.as_of)}. Not yet validated on representative real businesses. Dates are estimates, not commitments; no calibration claim is made.</p></div>
              <div className="overflow-x-auto"><table className="customer-prediction-table"><thead><tr><th>Invoice / outstanding</th><th>Due date</th><th>70% paid by</th><th>90% paid by</th><th>Within 30 days</th></tr></thead><tbody>
                {customer.invoices.map(invoice => <tr key={invoice.invoice_id}><td><strong className="font-semibold text-indigo-700">{invoice.invoice_id}</strong><p className="mt-1 text-[11px] text-slate-500">{money(invoice.outstanding)}</p></td><td>{dateLabel(invoice.due_date)}</td><td>{dateLabel(invoice.paid_by_70)}</td><td>{dateLabel(invoice.paid_by_90)}</td><td>{percent(invoice.probability_30_days)}</td></tr>)}
              </tbody></table></div>
              {!customer.invoices.length && <p className="px-5 py-10 text-center text-xs text-slate-500">No outstanding invoices for this customer.</p>}
              {data.model.status !== 'ready' && customer.invoices.length > 0 && <p className="border-t border-slate-100 bg-slate-50 p-4 text-xs text-slate-500">Probability dates remain unavailable until a business model can be fitted. Observed payment statistics above are still available.</p>}
            </section>
          </div>}
        </div>
      </>}
    </>}
    {activeReminder && (
      <ReminderSheet
        apiUrl={apiUrl}
        reminder={activeReminder}
        onClose={() => setActiveReminder(null)}
        onUpdated={async () => {
          setData(await apiRequest<Profiles>(`${apiUrl}/customers`));
        }}
      />
    )}
  </div>;
}
