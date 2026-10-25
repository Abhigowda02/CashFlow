import { useState } from 'react';
import { API_BASE, apiRequest } from './api';

export default function DemoControl({ reset = false, onLoaded }: {
  reset?: boolean; onLoaded: () => Promise<void>;
}) {
  const [reviewing, setReviewing] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function load() {
    if (!confirmed || busy) return;
    setBusy(true); setError('');
    try {
      await apiRequest(`${API_BASE}/demo`, { confirm: true, reset });
      await onLoaded();
      setReviewing(false); setConfirmed(false);
    } catch (e) { setError(e instanceof Error ? e.message : 'Demo could not be loaded. Try again.'); }
    finally { setBusy(false); }
  }
  return <section className={reset ? 'mt-3' : 'mt-6 rounded-lg border border-indigo-200 bg-indigo-50 p-4'} aria-label={reset ? 'Reset synthetic demo' : 'Explore synthetic demo'}>
    {!reset && <><h3 className="text-sm font-semibold text-indigo-950">Try a complete fictional business</h3>
      <p className="mt-2 text-xs leading-5 text-indigo-900">Explore invoices, partial receipts, payroll, rent, EMI, supplier bills and future-sales assumptions without entering them manually. Synthetic data demonstrates the workflow; it does not prove forecast accuracy.</p></>}
    {!reviewing ? <button type="button" className="button-secondary mt-3" onClick={() => setReviewing(true)}>{reset ? 'Reset synthetic demo' : 'Explore synthetic demo'}</button> : <div className="mt-3 space-y-3">
      <p className="text-xs leading-5">{reset ? 'Reset only this synthetic demo to its original invoices, cash and plan? Demo receipts, relationship edits and saved scenarios will be removed.' : 'Load the complete synthetic business into this new, empty workspace? Your setup form values will not be used.'} Other business workspaces are unaffected.</p>
      <label className="flex items-start gap-2 text-xs leading-5"><input type="checkbox" checked={confirmed} disabled={busy} onChange={event => setConfirmed(event.target.checked)} />{reset ? 'I confirm resetting this synthetic demo only.' : 'I understand this is fictional demo data.'}</label>
      <div className="flex flex-wrap gap-2"><button className="button-primary" type="button" disabled={!confirmed || busy} onClick={() => void load()}>{busy ? 'Loading demo…' : reset ? 'Confirm demo reset' : 'Load synthetic demo'}</button><button type="button" className="button-secondary" disabled={busy} onClick={() => { setReviewing(false); setConfirmed(false); setError(''); }}>Cancel</button></div>
    </div>}
    {error && <p role="alert" className="mt-3 text-xs leading-5 text-rose-800">{error}</p>}
  </section>;
}
