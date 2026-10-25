import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Users, ReceiptText, TrendingDown, CalendarDays, Plus, X, Play, Save, RefreshCw } from 'lucide-react';
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { apiRequest } from './api';
import { baselineSignature, buildDefinition, changeDescription, definitionSignature, eligibleCustomers, horizonEnd, runwayDays,
  type ChangeDraft, type PlannerBusiness, type PlannerDraft, type PlannerForecast, type SavedScenario, type ScenarioDefinition, type ScenarioResult } from './scenarioLogic';

type Evaluated = { definition: ScenarioDefinition; signature: string; result: ScenarioResult; evaluated_at: string };
type LibraryComparison = { baseline: PlannerForecast; scenarios: { saved: SavedScenario; forecast: PlannerForecast }[] };
type Props = { apiUrl: string; business: PlannerBusiness; forecast: PlannerForecast; delayModel: string;
  draft: PlannerDraft; onDraft: (draft: PlannerDraft) => void };
const currency = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });
const money = (value: number) => currency.format(value);
const shortMoney = (value: number) => new Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
const dateLabel = (value: string | null) => value ? new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`)) : 'None in 90 days';
const percent = (value: number) => `${Math.round(value*100)}%`;
const cardTypes = [
  { type: 'delay_customer' as const, title: 'Customer pays late', detail: 'Choose the customer and delay.', icon: Users },
  { type: 'extra_expense' as const, title: 'Unexpected expense', detail: 'Enter an amount and payment date.', icon: ReceiptText },
  { type: 'sales_change' as const, title: 'Sales change', detail: 'Change projected future sales.', icon: TrendingDown },
  { type: 'supplier_terms' as const, title: 'More time to pay', detail: 'Extend open supplier payment terms.', icon: CalendarDays },
];

export default function ScenarioPlanner({ apiUrl, business, forecast, delayModel, draft, onDraft }: Props) {
  const [view, setView] = useState<'build' | 'saved'>('build');
  const [evaluated, setEvaluated] = useState<Evaluated | null>(null);
  const [saved, setSaved] = useState<SavedScenario[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [comparison, setComparison] = useState<LibraryComparison | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loadingLibrary, setLoadingLibrary] = useState(true);
  const [error, setError] = useState('');
  const [libraryError, setLibraryError] = useState('');
  const [notice, setNotice] = useState('');
  const [deleteId, setDeleteId] = useState('');
  const running = useRef<AbortController | null>(null);
  const customers = eligibleCustomers(business);
  const openBills = business.supplier_bills?.filter(bill => bill.status === 'open') ?? [];
  const built = buildDefinition(draft, business);
  const signature = definitionSignature(built.definition, delayModel);
  const stale = Boolean(evaluated && (built.errors.length > 0 || signature !== evaluated.signature));
  useEffect(() => {
    const controller = new AbortController();
    apiRequest<SavedScenario[]>(`${apiUrl}/scenarios`, undefined, controller.signal).then(result => {
      if (!controller.signal.aborted) setSaved(result);
    }).catch(e => { if (!controller.signal.aborted) setLibraryError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setLoadingLibrary(false); });
    return () => { controller.abort(); running.current?.abort(); };
  }, [apiUrl]);
  function update(key: string, values: Partial<ChangeDraft>) {
    setNotice(''); onDraft({ ...draft, changes: draft.changes.map(row => row.key === key ? { ...row, ...values } : row) });
  }
  function add(type: ChangeDraft['type']) {
    setNotice(''); onDraft({ ...draft, changes: [...draft.changes, { key: crypto.randomUUID(), type }] });
  }
  async function run(event?: FormEvent) {
    event?.preventDefault(); setError(''); setNotice('');
    if (!draft.changes.length || built.errors.length) return;
    const controller = new AbortController(); running.current?.abort(); running.current = controller;
    const definition = structuredClone(built.definition), submittedSignature = signature;
    setBusy(true);
    try {
      const result = await apiRequest<ScenarioResult>(`${apiUrl}/scenario?delay_model=${delayModel}`, definition, controller.signal);
      if (!controller.signal.aborted) setEvaluated({ definition, signature: submittedSignature, result, evaluated_at: new Date().toISOString() });
    } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Could not evaluate scenario'); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  async function save() {
    setError(''); setNotice('');
    if (loadingLibrary || saving) return;
    if (!draft.name.trim()) { setError('Give this scenario a name before saving.'); return; }
    if (!draft.changes.length || built.errors.length) { setError('Complete the selected changes before saving.'); return; }
    setSaving(true);
    try {
      const result = await apiRequest<SavedScenario>(`${apiUrl}/scenarios`, built.definition);
      setSaved(current => [result, ...current]);
      setNotice(`Saved “${result.name}”. Only assumptions were saved; your cash and invoices are unchanged.`);
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save scenario'); }
    finally { setSaving(false); }
  }
  function load(item: SavedScenario) {
    const changes = item.changes.map(change => {
      const row: ChangeDraft = { key: crypto.randomUUID(), type: change.type };
      if (change.type === 'delay_customer') Object.assign(row, { customer_id: change.customer_id, extra_days: String(change.extra_days) });
      else if (change.type === 'extra_expense') Object.assign(row, { amount: String(change.amount), date: change.date, category: change.category ?? 'other', label: change.label ?? '' });
      else if (change.type === 'sales_change') row.pct = String(change.pct);
      else if (change.type === 'supplier_terms') row.extra_days = String(change.extra_days);
      // Revised schedules are retained in the saved API definition; their editor
      // is intentionally introduced in a later UI task.
      return row;
    });
    onDraft({ name: item.name, changes }); setView('build'); setEvaluated(null); setError('');
    setNotice('Saved assumptions loaded. Check customer balances and dates, then compare against your current records. Save again to create a new copy.');
  }
  async function remove(id: string) {
    if (busy || saving) return;
    setLibraryError(''); setSaving(true);
    try {
      await apiRequest<void>(`${apiUrl}/scenarios/${encodeURIComponent(id)}`, {}, undefined, 'DELETE');
      setSaved(current => current.filter(item => item.id !== id)); setSelectedIds(current => current.filter(value => value !== id));
      setComparison(null); setDeleteId('');
    } catch (e) { setLibraryError(e instanceof Error ? e.message : 'Could not delete scenario'); }
    finally { setSaving(false); }
  }
  async function compareSaved() {
    setLibraryError(''); setComparison(null); if (!selectedIds.length || saving) return;
    const selected = saved.filter(item => selectedIds.includes(item.id));
    const controller = new AbortController(); running.current?.abort(); running.current = controller; setBusy(true);
    try {
      const responses = await Promise.all(selected.map(item => apiRequest<ScenarioResult>(`${apiUrl}/scenario?delay_model=${delayModel}`,
        { name: item.name, changes: item.changes }, controller.signal)));
      if (responses.some(response => baselineSignature(response.baseline) !== baselineSignature(responses[0].baseline))) throw new Error('Business records changed during comparison. Refresh and try again.');
      if (!controller.signal.aborted) setComparison({ baseline: responses[0].baseline, scenarios: responses.map((response, index) => ({ saved: selected[index], forecast: response.scenario })) });
    } catch (e) { if (!controller.signal.aborted) setLibraryError(e instanceof Error ? e.message : 'Could not compare saved scenarios'); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  const result = evaluated?.result;
  return <div className="space-y-5">
    <div><p className="eyebrow">PLAN BEFORE YOU COMMIT</p><h1 className="mt-1.5 text-[28px] font-semibold tracking-tight">What happens if…?</h1>
      <p className="mt-2 text-sm text-slate-500">Choose a change, review the assumptions, and compare its effect on your cash.</p></div>
    <nav className="section-tabs" aria-label="Scenario workspace"><button aria-pressed={view === 'build'} onClick={() => setView('build')}>Build a scenario</button><button aria-pressed={view === 'saved'} onClick={() => setView('saved')}>Saved scenarios ({saved.length})</button></nav>
    <p className="text-xs leading-5 text-slate-500">Observation date: {dateLabel(business.as_of)} · 90-day horizon · These are simulations. Actual invoices, obligations and cash remain unchanged.</p>
    {notice && <p role="status" className="rounded-md border border-emerald-200 bg-emerald-50 p-4 text-xs leading-5 text-emerald-800">{notice}</p>}
    {view === 'build' ? <>
      {error && <p role="alert" className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
      <div className="grid items-start gap-5 xl:grid-cols-[minmax(330px,.85fr)_minmax(0,1.15fr)]">
        <form className="panel-card space-y-5 p-5" onSubmit={event => void run(event)}>
          <div className="flex items-center justify-between"><h2 className="text-sm font-semibold">1. Choose what changes</h2>{draft.changes.length > 0 && <button className="text-xs text-slate-500 underline" type="button" disabled={busy || saving} onClick={() => { onDraft({ name: '', changes: [] }); setEvaluated(null); setNotice(''); setError(''); }}>Reset all</button>}</div>
          <div className="grid grid-cols-2 gap-2">{cardTypes.map(card => {
            const singleton = card.type === 'sales_change' || card.type === 'supplier_terms';
            const disabled = draft.changes.length >= 20 || (singleton && draft.changes.some(row => row.type === card.type)) || (card.type === 'delay_customer' && customers.length === 0) || (card.type === 'supplier_terms' && !openBills.length) || (card.type === 'sales_change' && !(business.sales_plan?.monthly_amount));
            return <button key={card.type} className="scenario-event" type="button" disabled={disabled} onClick={() => add(card.type)}><card.icon size={17} /><strong>{card.title}</strong><span>{card.type === 'delay_customer' && !customers.length ? 'Add an unpaid invoice first.' : card.type === 'sales_change' && !business.sales_plan?.monthly_amount ? 'Enter future monthly sales first.' : card.type === 'supplier_terms' && !openBills.length ? 'Add an open supplier bill first.' : card.detail}</span></button>;
          })}</div>
          {!draft.changes.length && <p className="text-xs leading-5 text-slate-500">Nothing is preselected. Pick an event to begin; add more events only when you want to combine them.</p>}
          {draft.changes.map((row, index) => <section className="scenario-change" key={row.key}>
            <div className="mb-4 flex items-center justify-between gap-2"><h3 className="text-xs font-semibold">{index+1}. {cardTypes.find(card => card.type === row.type)?.title}</h3><button type="button" className="text-slate-400 hover:text-rose-600" aria-label={`Remove change ${index+1}`} onClick={() => onDraft({ ...draft, changes: draft.changes.filter(item => item.key !== row.key) })}><X size={15} /></button></div>
            {row.type === 'delay_customer' && <>
              <label className="block text-xs">Which customer pays late?<select className="field-input mt-1" required value={row.customer_id ?? ''} onChange={event => update(row.key, { customer_id: event.target.value })}><option value="">Choose a customer — no default selection</option>
                {row.customer_id && !customers.some(customer => customer.id === row.customer_id) && <option value={row.customer_id}>{business.customers.find(customer => customer.id === row.customer_id)?.name ?? row.customer_id} — no outstanding invoices</option>}
                {customers.map(customer => <option key={customer.id} value={customer.id} disabled={draft.changes.some(other => other.key !== row.key && other.type === 'delay_customer' && other.customer_id === customer.id)}>{customer.name} · {money(customer.outstanding)}</option>)}
              </select></label>
              <label className="mt-3 block text-xs">Extra delay in days<input className="field-input mt-1" type="number" min={1} max={180} step={1} required placeholder="For example, 20" value={row.extra_days ?? ''} onChange={event => update(row.key, { extra_days: event.target.value })} /></label>
              <p className="mt-2 text-[11px] leading-5 text-slate-500">Applies only to all currently unpaid invoices of the customer you select. Add another customer-delay change to test a different customer independently.</p>
            </>}
            {row.type === 'extra_expense' && <div className="grid gap-3 sm:grid-cols-2"><label className="text-xs">Additional expense (INR)<input className="field-input mt-1 min-h-11" type="number" min={1} step={1} required placeholder="For example, 30000" value={row.amount ?? ''} onChange={event => update(row.key, { amount: event.target.value })} /></label><label className="text-xs">Payment date<input className="field-input mt-1 min-h-11" type="date" required min={business.as_of} max={horizonEnd(business.as_of)} value={row.date ?? ''} onChange={event => update(row.key, { date: event.target.value })} /></label><label className="text-xs">Category<select className="field-input mt-1 min-h-11" value={row.category ?? 'other'} onChange={event => update(row.key, { category: event.target.value })}>{[['electricity','Electricity bill'],['gas','Gas bill'],['water','Water bill'],['rent','Rent'],['salary','Salaries'],['loan_emi','Loan EMI'],['tax','GST/tax'],['insurance','Insurance'],['internet_phone','Internet/phone'],['supplier_payment','Supplier payment'],['maintenance','Maintenance'],['fuel_transport','Fuel/transport'],['other','Other']].map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="text-xs">Label (optional)<input className="field-input mt-1 min-h-11" maxLength={80} value={row.label ?? ''} onChange={event => update(row.key, { label: event.target.value })} /></label></div>}
            {row.type === 'sales_change' && <><label className="block text-xs">Change in future sales (%)<input className="field-input mt-1" type="number" min={-100} max={100} step="any" required placeholder="−20 for a 20% decrease" value={row.pct ?? ''} onChange={event => update(row.key, { pct: event.target.value })} /></label><p className="mt-2 text-[11px] leading-5 text-slate-500">Current monthly sales assumption: {money(business.sales_plan?.monthly_amount ?? 0)}. Existing invoice amounts stay unchanged.</p></>}
            {row.type === 'supplier_terms' && <><label className="block text-xs">Extra days agreed with suppliers<input className="field-input mt-1" type="number" min={1} max={180} step={1} required placeholder="For example, 15" value={row.extra_days ?? ''} onChange={event => update(row.key, { extra_days: event.target.value })} /></label><p className="mt-2 text-[11px] leading-5 text-slate-500">Applies to all {openBills.length} open supplier bills ({money(openBills.reduce((sum, bill) => sum+bill.amount, 0))}). This assumes suppliers agree; verify payment obligations before acting.</p>{openBills.some(bill => bill.is_msme) && <p className="mt-2 text-[11px] text-amber-800">Micro/small-enterprise supplier bills are included. Review their payment restrictions before assuming an extension.</p>}</>}
          </section>)}
          {draft.changes.length > 0 && <>
            <div className="border-t border-slate-100 pt-4"><h2 className="text-sm font-semibold">2. Review your assumptions</h2>
              {built.errors.length > 0 ? <ul className="mt-3 space-y-1 text-xs leading-5 text-amber-800">{built.errors.map(message => <li key={message}>{message}</li>)}</ul> : <ol className="mt-3 list-decimal space-y-2 pl-4 text-xs leading-5 text-slate-600">{built.definition.changes.map((change, index) => <li key={index}>{changeDescription(change, business)}</li>)}</ol>}
              <p className="mt-3 text-[11px] text-slate-400">All other assumptions follow your current business plan.</p>
            </div>
            <button className="button-primary w-full" type="submit" disabled={busy || built.errors.length > 0}><Play size={14} />{busy ? 'Comparing cash impact…' : 'Compare cash impact'}</button>
            <div className="space-y-3 border-t border-slate-100 pt-4"><label className="block text-xs">Scenario name<input className="field-input mt-1" value={draft.name} maxLength={120} onChange={event => onDraft({ ...draft, name: event.target.value })} placeholder="For example, Wholesale customer pays 20 days late" /></label><button className="button-secondary w-full" type="button" disabled={loadingLibrary || saving || built.errors.length > 0 || !draft.name.trim()} onClick={() => void save()}><Save size={14} />{saving ? 'Saving…' : 'Save assumptions as a new scenario'}</button></div>
          </>}
        </form>
        <div className="min-w-0 space-y-5">
          {result && evaluated ? <>
            {stale && <div role="status" className="rounded-md border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900"><strong>Needs recalculation.</strong> The results below belong to the last evaluated assumptions, not your current edits.</div>}
            <div className={`panel-card p-5 ${stale ? 'opacity-65' : ''}`}><p className="eyebrow">3. UNDERSTAND THE IMPACT</p><h2 className="mt-2 text-lg font-semibold">{evaluated.definition.name}</h2>
              <ShortageBanner scenario={result.scenario} baseline={result.baseline} />
              <p className="mt-3 text-sm leading-6 text-slate-700">{impactSummary(result.baseline, result.scenario)}</p>
              <p className="mt-2 text-xs text-slate-500">Lowest median cash changes by <strong>{signedMoney(result.scenario.min_balance_p50-result.baseline.min_balance_p50)}</strong> versus the baseline.</p>
              <details className="mt-4 text-xs"><summary className="cursor-pointer text-indigo-700">View evaluated assumptions</summary><ul className="mt-2 list-disc space-y-2 pl-4 text-slate-500">{evaluated.definition.changes.map((change, index) => <li key={index}>{changeDescription(change, business)}</li>)}</ul></details>
            </div>
            <ComparisonTable baseline={result.baseline} scenarios={[{ name: evaluated.definition.name, forecast: result.scenario }]} />
            <ScenarioPlot baseline={result.baseline} scenarios={[{ name: evaluated.definition.name, forecast: result.scenario }]} />
            <p className="text-[11px] leading-5 text-slate-400">Model used: {result.scenario.meta?.delay_model_used ?? delayModel}. Shortage dates summarise simulated paths with shortages; median runway is measured from the P50 line. These estimates are conditional on your assumptions.</p>
          </> : <section className="panel-card p-7"><div className="mb-5 inline-flex rounded-md bg-indigo-50 p-3 text-indigo-600"><Plus size={22} /></div><h2 className="text-lg font-semibold">Start with one real business event</h2><p className="mt-3 text-sm leading-6 text-slate-500">Choose who pays late, add a bill, or change a sales assumption. Compare the effect before committing to a decision.</p><div className="mt-6 grid grid-cols-2 gap-5 border-t border-slate-100 pt-5"><div><p className="text-xs text-slate-500">Current shortage chance</p><strong className="mt-2 block text-xl font-semibold">{percent(forecast.shortage_prob)}</strong></div><div><p className="text-xs text-slate-500">Lowest median cash</p><strong className="mt-2 block text-xl font-semibold">{money(forecast.min_balance_p50)}</strong></div></div><p className="mt-5 text-xs text-slate-400">No stress changes are active until you add them.</p></section>}
        </div>
      </div>
    </> : <div className="space-y-5">
      {libraryError && <p role="alert" className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{libraryError}</p>}
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="max-w-2xl text-xs leading-5 text-slate-500">Saved scenarios contain assumptions only. Select up to two and compare them with a fresh baseline using your current records and selected payment model.</p><button className="button-primary" disabled={busy || saving || !selectedIds.length} onClick={() => void compareSaved()}><RefreshCw size={14} />{busy ? 'Re-evaluating…' : 'Compare selected'}</button></div>
      {loadingLibrary ? <p className="panel-card p-8 text-sm text-slate-500">Loading saved scenarios…</p> : !saved.length ? <div className="panel-card p-10 text-center"><h2 className="text-sm font-semibold">No saved scenarios yet</h2><p className="mt-2 text-xs text-slate-500">Build a scenario and save its assumptions to revisit it later.</p><button className="button-secondary mt-5" onClick={() => setView('build')}>Build a scenario</button></div> : <div className="grid gap-3 md:grid-cols-2">{saved.map(item => <section key={item.id} className="panel-card p-5"><label className="flex items-start gap-3"><input type="checkbox" className="mt-1" checked={selectedIds.includes(item.id)} disabled={busy || (!selectedIds.includes(item.id) && selectedIds.length >= 2)} onChange={event => { setSelectedIds(event.target.checked ? [...selectedIds, item.id] : selectedIds.filter(id => id !== item.id)); setComparison(null); }} /><span><strong className="text-sm font-semibold">{item.name}</strong><span className="mt-1 block text-xs text-slate-500">{item.changes.length} changes · Saved {new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' }).format(new Date(item.created_at))}</span></span></label><ul className="mt-4 list-disc space-y-2 pl-4 text-xs leading-5 text-slate-500">{item.changes.map((change, index) => <li key={index}>{changeDescription(change, business)}</li>)}</ul><div className="mt-4 flex flex-wrap gap-3"><button className="button-secondary" disabled={busy} onClick={() => load(item)}>Load & edit</button>{deleteId === item.id ? <><button className="button-secondary text-rose-700" disabled={busy || saving} onClick={() => void remove(item.id)}>Confirm delete</button><button className="text-xs text-slate-500" onClick={() => setDeleteId('')}>Cancel</button></> : <button className="text-xs text-slate-500 underline" disabled={busy} onClick={() => setDeleteId(item.id)}>Delete</button>}</div></section>)}</div>}
      {comparison && <><ComparisonTable baseline={comparison.baseline} scenarios={comparison.scenarios.map(row => ({ name: row.saved.name, forecast: row.forecast }))} /><ScenarioPlot baseline={comparison.baseline} scenarios={comparison.scenarios.map(row => ({ name: row.saved.name, forecast: row.forecast }))} /></>}
    </div>}
  </div>;
}

function signedMoney(value: number) { return `${value > 0 ? '+' : value < 0 ? '−' : ''}${money(Math.abs(value))}`; }
function ShortageBanner({ scenario, baseline }: { scenario: PlannerForecast; baseline: PlannerForecast }) {
  const text = (forecast: PlannerForecast) => {
    const value = forecast.shortage_analysis;
    if (!value) return null;
    return !value.first_shortage_date || value.shortage_probability <= 0 ? 'No shortage expected' : `Shortage likely on ${dateLabel(value.first_shortage_date)} (${percent(value.shortage_probability)} chance), peak gap Rs ${new Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 1 }).format(value.peak_funding_gap)}`;
  };
  const current = text(scenario), base = text(baseline);
  if (!current) return null;
  return <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-950"><strong>{current}</strong>{base && base !== current && <p className="mt-1 text-xs text-amber-800">Baseline: {base}</p>}</div>;
}
function impactSummary(baseline: PlannerForecast, scenario: PlannerForecast) {
  const delta = Math.round((scenario.shortage_prob-baseline.shortage_prob)*100);
  const change = delta > 0 ? `raises the shortage chance by ${delta} percentage points` : delta < 0 ? `reduces the shortage chance by ${Math.abs(delta)} percentage points` : 'leaves the simulated shortage chance unchanged';
  return `This scenario ${change}, from ${percent(baseline.shortage_prob)} to ${percent(scenario.shortage_prob)}.`;
}
function ComparisonTable({ baseline, scenarios }: { baseline: PlannerForecast; scenarios: { name: string; forecast: PlannerForecast }[] }) {
  const columns = [{ name: 'Current plan', forecast: baseline }, ...scenarios];
  const rows: { label: string; value: (forecast: PlannerForecast) => string }[] = [
    { label: 'Chance of falling below safety floor', value: forecast => percent(forecast.shortage_prob) },
    { label: 'Estimated first shortage date', value: forecast => dateLabel(forecast.first_shortage_date) },
    { label: 'Lowest median cash balance', value: forecast => money(forecast.min_balance_p50) },
    { label: 'Gap below safety floor at median low', value: forecast => money(Math.max(0, forecast.safety_floor-forecast.min_balance_p50)) },
    { label: 'Median cash runway', value: forecast => runwayDays(forecast) === null ? '90+ days' : `${runwayDays(forecast)} days` },
  ];
  return <section className="panel-card overflow-hidden"><div className="p-5"><h2 className="text-sm font-semibold">Cash impact, side by side</h2><p className="mt-1 text-xs text-slate-500">Safety floor: {money(baseline.safety_floor)} · As of {dateLabel(baseline.dates[0])}</p></div><div className="overflow-x-auto"><table className="scenario-metrics-table"><thead><tr><th>Measure</th>{columns.map((column, index) => <th key={index}>{column.name}</th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.label}><th>{row.label}</th>{columns.map((column, index) => <td key={index}>{row.value(column.forecast)}</td>)}</tr>)}</tbody></table></div></section>;
}
function ScenarioPlot({ baseline, scenarios }: { baseline: PlannerForecast; scenarios: { name: string; forecast: PlannerForecast }[] }) {
  const data = baseline.dates.map((date, index) => Object.assign({ date, baseline: baseline.p50[index] }, ...scenarios.map((scenario, n) => ({ [`scenario${n}`]: scenario.forecast.p50[index] }))));
  const colors = ['#4f46e5', '#0891b2'];
  return <section className="panel-card p-5"><h2 className="text-sm font-semibold">Median balance over time</h2><div className="mt-3 flex flex-wrap gap-4 text-[11px] text-slate-500"><span>▰ Current plan</span>{scenarios.map((scenario, index) => <span key={index} style={{ color: colors[index] }}>▰ {scenario.name}</span>)}</div><div className="mt-5 h-[280px]"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{ left: 4, right: 10, bottom: 8 }}><CartesianGrid stroke="#eef0f4" vertical={false} /><XAxis dataKey="date" tickFormatter={value => new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short' }).format(new Date(`${value}T12:00:00`))} tick={{ fontSize: 10, fill: '#98a2b3' }} minTickGap={35} tickLine={false} axisLine={false} /><YAxis tickFormatter={shortMoney} tick={{ fontSize: 10, fill: '#98a2b3' }} width={60} tickLine={false} axisLine={false} /><Tooltip formatter={(value: number) => money(value)} /><ReferenceLine y={baseline.safety_floor} stroke="#f97066" strokeDasharray="4 4" /><Line dataKey="baseline" name="Current plan" stroke="#98a2b3" strokeDasharray="5 4" strokeWidth={2} dot={false} isAnimationActive={false} />{scenarios.map((scenario, index) => <Line key={index} dataKey={`scenario${index}`} name={scenario.name} stroke={colors[index]} strokeWidth={2.2} dot={false} isAnimationActive={false} />)}</LineChart></ResponsiveContainer></div><p className="mt-3 text-[11px] text-slate-400">Lines show P50 medians, not guaranteed outcomes. The dashed red line is your safety floor.</p></section>;
}
