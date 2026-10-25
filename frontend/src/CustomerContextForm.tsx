import { useState, type FormEvent } from 'react';
import { apiRequest } from './api';

export type CollectionContext = { importance: 'standard' | 'important' | 'strategic'; repeat_customer: boolean;
  service_issue: 'none' | 'open' | 'resolving'; disputed_invoice_ids: string[]; notes: string; reviewed_at?: string };

export default function CustomerContextForm({ apiUrl, customerId, value, invoices, onSaved }: {
  apiUrl: string; customerId: string; value: CollectionContext | null; invoices: { invoice_id: string }[];
  onSaved: () => Promise<void>;
}) {
  const [importance, setImportance] = useState(value?.importance ?? 'standard');
  const [repeat, setRepeat] = useState(value?.repeat_customer ?? false);
  const [issue, setIssue] = useState(value?.service_issue ?? 'none');
  const [disputes, setDisputes] = useState(() => (value?.disputed_invoice_ids ?? []).filter(id => invoices.some(invoice => invoice.invoice_id === id)));
  const [notes, setNotes] = useState(value?.notes ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      await apiRequest(`${apiUrl}/customer-context`, { customer_id: customerId, importance,
        repeat_customer: repeat, service_issue: issue, disputed_invoice_ids: disputes, notes });
      await onSaved();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save context'); }
    finally { setBusy(false); }
  }
  return <details className="panel-card p-5" open={!value}>
    <summary className="cursor-pointer text-sm font-semibold">Relationship & service context <span className="ml-2 text-xs font-normal text-slate-500">{value ? 'Reviewed by owner' : 'Needs owner review'}</span></summary>
    <p className="mt-3 text-xs leading-5 text-slate-500">These owner-provided details guide how to contact this customer. They do not change the cash ranking or the payment model. Nothing is sent automatically.</p>
    <form onSubmit={save} className="mt-4 space-y-4">
      {error && <p role="alert" className="text-xs text-rose-700">{error}</p>}
      <fieldset disabled={busy} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-xs">Customer importance<select className="field-input mt-1" value={importance} onChange={e => setImportance(e.target.value as typeof importance)}>
            <option value="standard">Standard</option><option value="important">Important</option><option value="strategic">Strategic</option>
          </select></label>
          <label className="block text-xs">Unresolved service issue<select className="field-input mt-1" value={issue} onChange={e => setIssue(e.target.value as typeof issue)}>
            <option value="none">None recorded</option><option value="open">Open issue</option><option value="resolving">Being resolved</option>
          </select></label>
        </div>
        <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={repeat} onChange={e => setRepeat(e.target.checked)} />Repeat customer / ongoing business relationship</label>
        {invoices.length > 0 && <fieldset><legend className="mb-2 text-xs font-medium">Outstanding invoices under dispute</legend><div className="flex max-h-36 flex-wrap gap-3 overflow-auto rounded-md border border-slate-200 p-3">
          {invoices.map(invoice => <label key={invoice.invoice_id} className="flex items-center gap-2 text-xs"><input type="checkbox" checked={disputes.includes(invoice.invoice_id)} onChange={e => setDisputes(e.target.checked ? [...disputes, invoice.invoice_id] : disputes.filter(id => id !== invoice.invoice_id))} />{invoice.invoice_id}</label>)}
        </div></fieldset>}
        <label className="block text-xs">Private owner notes<textarea className="field-input mt-1" rows={3} maxLength={1000} value={notes} onChange={e => setNotes(e.target.value)} placeholder="For example: account manager should resolve a delivery issue before requesting settlement." /></label>
        <button className="button-primary">{busy ? 'Saving…' : 'Save relationship context'}</button>
      </fieldset>
    </form>
  </details>;
}
