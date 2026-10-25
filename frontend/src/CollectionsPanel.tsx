import { useEffect, useState } from 'react';
import { apiRequest } from './api';
import { RefreshCw } from 'lucide-react';

type Row = { rank: number; customer_id: string; customer_name: string; invoice_ids: string[];
  overdue_amount: number; oldest_overdue_days: number; shortage_probability_after: number;
  probability_reduction_pp: number; expected_gap_reduction: number; runway_days_gained: number;
  cash_advanced_by_deadline: number; guidance: { sensitivity: string; approach: string; reason: string; next_action: string } };
type Ranking = { customers: Row[]; as_of: string; delay_model_used: string; delay_model_requested: string;
  n_sims: number; acceleration_days: number; comparison_deadline: string; assumption: string; ranking_method: string;
  baseline: { shortage_probability: number; first_shortage_date: string | null; expected_peak_gap: number } };
const money = (value: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value);

export default function CollectionsPanel({ apiUrl, delayModel }: { apiUrl: string; delayModel: string }) {
  const [ranking, setRanking] = useState<Ranking | null>(null);
  const [days, setDays] = useState(15);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setBusy(true); setError(''); setRanking(null);
    apiRequest<Ranking>(`${apiUrl}/collections?delay_model=${delayModel}&acceleration_days=${days}`, undefined, controller.signal)
      .then(result => { if (!controller.signal.aborted) setRanking(result); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [apiUrl, delayModel, days, refresh]);
  return <div className="space-y-5">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><h2 className="text-lg font-semibold tracking-tight">Who should you follow up with first?</h2>
      <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-500">Customers are ranked by simulated cash benefit. Relationship and service issues determine the suggested approach, not an invented collection-success score.</p></div>
      <div className="flex items-end gap-2"><label className="text-xs text-slate-500">What if receipts arrive earlier by<select className="field-input mt-1" value={days} disabled={busy} onChange={event => setDays(Number(event.target.value))}><option value="7">7 days</option><option value="15">15 days</option><option value="30">30 days</option></select></label>
      <button className="icon-button" aria-label="Refresh collections ranking" disabled={busy} onClick={() => setRefresh(refresh+1)}><RefreshCw size={16} className={busy ? 'animate-spin' : ''} /></button></div>
    </div>
    {busy && <div role="status" className="panel-card p-8 text-sm text-slate-500">Comparing customer collections across 500 paired cash-flow paths…</div>}
    {error && <div role="alert" className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}<button className="ml-3 underline" onClick={() => setRefresh(refresh+1)}>Retry</button></div>}
    {ranking && <>
      <div className="ledger-summary"><div><p>Current shortage chance</p><strong>{Math.round(ranking.baseline.shortage_probability*100)}%</strong></div><div><p>Expected peak gap below safety floor</p><strong>{money(ranking.baseline.expected_peak_gap)}</strong></div><div><p>Customers with overdue invoices</p><strong>{ranking.customers.length}</strong></div></div>
      <div className="rounded-lg border border-indigo-100 bg-indigo-50/40 p-4 text-xs leading-6 text-slate-600"><p><strong className="font-semibold">Assumption:</strong> {ranking.assumption}</p>
        <p>These are conditional scenario estimates, not a prediction that a reminder will succeed. No collection effectiveness has been validated.</p>
        <p><strong className="font-semibold">Ranking:</strong> {ranking.ranking_method}</p>
        <p>Model used: {ranking.delay_model_used}. {ranking.delay_model_used !== ranking.delay_model_requested && 'Requested survival model was unavailable; historical delays were used.'} Cash-advanced comparison date: {ranking.comparison_deadline}. Expected gap averages the worst below-floor gap in each path, including zero for paths without a shortage.</p>
      </div>
      {!ranking.customers.length ? <div className="panel-card px-6 py-12 text-center"><p className="text-sm font-semibold">No overdue invoices to prioritise</p><p className="mt-2 text-xs text-slate-500">Only outstanding invoices past their due date are included. Future-due and settled invoices are excluded.</p></div> : <div className="panel-card overflow-hidden"><div className="overflow-x-auto"><table className="collections-table"><thead><tr><th>Priority / customer</th><th>Overdue</th><th>Shortage reduction</th><th>Expected gap reduced</th><th>Runway gained</th><th>Suggested approach</th></tr></thead><tbody>
        {ranking.customers.map(row => <tr key={row.customer_id}>
          <td><p className="font-semibold text-slate-800">#{row.rank} {row.customer_name}</p><p className="mt-1 text-[11px] text-slate-500">{row.invoice_ids.length} overdue invoices · oldest {row.oldest_overdue_days} days</p></td>
          <td><strong className="font-semibold">{money(row.overdue_amount)}</strong></td>
          <td><strong className="font-semibold">{row.probability_reduction_pp.toFixed(1)} pp</strong><p className="mt-1 text-[11px] text-slate-500">After: {Math.round(row.shortage_probability_after*100)}%</p></td>
          <td><strong className="font-semibold">{money(row.expected_gap_reduction)}</strong><p className="mt-1 text-[11px] text-slate-500">Cash advanced by comparison date: {money(row.cash_advanced_by_deadline)}</p></td>
          <td>{row.runway_days_gained.toFixed(1)} days</td>
          <td className="min-w-[300px] max-w-[420px]"><p className="text-xs font-semibold">{row.guidance.approach}</p><span className={`risk-badge mt-2 ${row.guidance.sensitivity === 'high' ? 'risk-high' : row.guidance.sensitivity === 'unknown' || row.guidance.sensitivity === 'medium' ? 'risk-medium' : 'risk-low'}`}>{row.guidance.sensitivity === 'unknown' ? 'Context not reviewed' : `${row.guidance.sensitivity} relationship sensitivity`}</span><p className="mt-2 text-[11px] leading-5 text-slate-600">{row.guidance.reason}</p><p className="mt-2 text-[11px] leading-5 text-slate-500">{row.guidance.next_action}</p></td>
        </tr>)}
      </tbody></table></div></div>}
      <p className="text-[11px] leading-5 text-slate-500">Use Customers → Relationship & service context to record importance, repeat business, service issues and disputes. Settle disputes before relying on the associated timing benefit. No messages are sent, and no cash is recorded by this simulation.</p>
    </>}
  </div>;
}
