import { useEffect, useState, type FormEvent } from 'react';
import WorkspacePlan, { type PlanBusiness } from './WorkspacePlan';
import { apiRequest } from './api';
import { FileSearch, Trash2 } from 'lucide-react';

type Invoice = { id: string; customer_name: string; amount: number; received: number;
  outstanding: number; ledger_status: string; due_date: string; issue_date: string; days_overdue: number };
type Ledger = { invoices: Invoice[]; received: number; outstanding: number;
  receivable_aging: Record<string, number>; payable_aging: Record<string, number>;
  concentration: { customer: string; amount: number; share: number }[] };
type PdfDraft = {
  invoice_id: string; customer_id: string; customer_name: string; segment: '' | 'small' | 'corporate' | 'government' | null;
  amount: number | null; issue_date: string; due_date: string; currency: string; received_amount: number | null;
  paid_date: string | null; source_page: number; source_text: string; duplicate: boolean;
  field_confidence: Record<string, 'high' | 'medium' | 'missing'>; issues: string[];
};
type Props = { apiUrl: string; business: PlanBusiness & {
  name: string; as_of: string; opening_cash: number; safety_floor: number; invoices: { id: string }[];
};
  onChanged: () => Promise<void> };
const money = (value: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value);

async function jsonRequest(url: string, payload?: unknown) {
  return apiRequest<Ledger & { invoice_count: number }>(url, payload);
}

export default function LedgerPage({ apiUrl, business, onChanged }: Props) {
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [pdfDrafts, setPdfDrafts] = useState<PdfDraft[]>([]);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfError, setPdfError] = useState('');
  const [pdfMessage, setPdfMessage] = useState('');
  const [confirmPdfAppend, setConfirmPdfAppend] = useState(false);
  const [confirmPdfCurrency, setConfirmPdfCurrency] = useState(false);
  const [csvAppendFile, setCsvAppendFile] = useState<File | null>(null);
  const [csvAppendRows, setCsvAppendRows] = useState<any[]>([]);
  const [csvAppendBusy, setCsvAppendBusy] = useState(false);
  const [csvAppendError, setCsvAppendError] = useState('');
  const [csvAppendMessage, setCsvAppendMessage] = useState('');
  const [confirmCsvAppend, setConfirmCsvAppend] = useState(false);
  const [confirmCsvCurrency, setConfirmCsvCurrency] = useState(false);
  const [name, setName] = useState(business.name);
  const [asOf, setAsOf] = useState(business.as_of);
  const [cash, setCash] = useState(business.opening_cash);
  const [floor, setFloor] = useState(business.safety_floor);
  const [replace, setReplace] = useState(false);
  const [unitsConfirmed, setUnitsConfirmed] = useState(false);
  const [invoiceId, setInvoiceId] = useState('');
  const [amount, setAmount] = useState('');
  const [paymentDate, setPaymentDate] = useState(business.as_of);
  const [receiptId, setReceiptId] = useState(() => crypto.randomUUID());
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [view, setView] = useState<'invoices' | 'receipts' | 'import' | 'plan'>('invoices');
  useEffect(() => {
    let active = true;
    jsonRequest(`${apiUrl}/ledger`).then(data => { if (active) setLedger(data); })
      .catch(e => { if (active) setError(String(e.message)); });
    return () => { active = false; };
  }, [apiUrl, business]);

  async function importFile(event: FormEvent) {
    event.preventDefault();
    if (!file || !replace || !unitsConfirmed) return;
    if (file.size > 5_000_000) { setError('Choose a file smaller than 5 MB.'); return; }
    setBusy(true); setError(''); setMessage('');
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      let binary = '';
      for (let offset = 0; offset < bytes.length; offset += 8192) {
        binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
      }
      const result = await jsonRequest(`${apiUrl}/import`, { filename: file.name, content_base64: btoa(binary),
        name, as_of: asOf, opening_cash: cash, safety_floor: floor, declared_currency: 'INR' });
      await onChanged();
      setMessage(`Imported ${result.invoice_count} invoices. Add supplier bills and recurring outflows before relying on forecasts.`);
      setReplace(false); setUnitsConfirmed(false); setPage(0);
    } catch (e) { setError(e instanceof Error ? e.message : 'Import failed'); }
    finally { setBusy(false); }
  }

  async function previewPdf(event: FormEvent) {
    event.preventDefault();
    if (!pdfFile) return;
    setPdfBusy(true); setPdfError(''); setPdfMessage('');
    setPdfDrafts([]); setConfirmPdfAppend(false); setConfirmPdfCurrency(false);
    try {
      if (pdfFile.size > 5_000_000) throw new Error('PDF must be smaller than 5 MB.');
      const bytes = new Uint8Array(await pdfFile.arrayBuffer());
      let binary = '';
      for (let offset = 0; offset < bytes.length; offset += 8192) {
        binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
      }
      const result = await apiRequest<{ drafts: PdfDraft[]; duplicate_count: number }>(
        `${apiUrl}/import/pdf/preview`,
        { filename: pdfFile.name, content_base64: btoa(binary) },
      );
      setPdfDrafts(result.drafts.map(draft => ({ ...draft, segment: draft.segment ?? '' })));
      if (result.duplicate_count) setPdfError('Duplicate invoice IDs were found. Correct or remove those drafts before adding any invoices.');
    } catch (e) { setPdfError(e instanceof Error ? e.message : 'Could not review this PDF'); }
    finally { setPdfBusy(false); }
  }

  async function applyPdfDrafts() {
    setPdfBusy(true); setPdfError(''); setPdfMessage('');
    try {
      const ids = pdfDrafts.map(draft => draft.invoice_id.trim());
      const duplicateIds = new Set(ids.filter((id, index) => !id || ids.indexOf(id) !== index));
      if (pdfDrafts.some(draft => draft.duplicate || business.invoices.some(invoice => invoice.id === draft.invoice_id.trim())) || duplicateIds.size) {
        throw new Error('Resolve duplicate or missing invoice IDs before adding these invoices.');
      }
      const invalid = pdfDrafts.find(draft =>
        !draft.invoice_id.trim() || !draft.customer_id.trim() || !draft.customer_name.trim() ||
        !draft.segment || draft.amount === null || !Number.isSafeInteger(draft.amount) || draft.amount <= 0 ||
        draft.currency.trim().toUpperCase() !== 'INR' || !draft.issue_date || !draft.due_date ||
        draft.issue_date > business.as_of || draft.due_date < draft.issue_date ||
        draft.received_amount === null || !Number.isSafeInteger(draft.received_amount) || draft.received_amount < 0 ||
        draft.received_amount > (draft.amount ?? 0) ||
        (draft.received_amount === draft.amount && !draft.paid_date) ||
        (draft.paid_date !== null && (draft.paid_date < draft.issue_date || draft.paid_date > business.as_of)));
      if (invalid) throw new Error(`${invalid.invoice_id || 'An invoice'} has missing or invalid fields. Review the highlighted values.`);
      if (!confirmPdfAppend || !confirmPdfCurrency) {
        throw new Error('Confirm that these invoices should be added and that all amounts are INR.');
      }
      const result = await apiRequest<{ invoice_count: number }>(`${apiUrl}/import/pdf/apply`, {
        invoices: pdfDrafts.map(({ source_page: _page, source_text: _text, duplicate: _duplicate,
          field_confidence: _confidence, issues: _issues, ...invoice }) => invoice),
        confirm_append: confirmPdfAppend,
        confirm_currency_inr: confirmPdfCurrency,
      });
      await onChanged();
      setPdfMessage(`Added ${result.invoice_count} reviewed invoice${result.invoice_count === 1 ? '' : 's'}. Existing cash, receipts, expenses, and supplier bills were preserved.`);
      setPdfDrafts([]); setPdfFile(null); setConfirmPdfAppend(false); setConfirmPdfCurrency(false);
    } catch (e) { setPdfError(e instanceof Error ? e.message : 'Could not add reviewed invoices'); }
    finally { setPdfBusy(false); }
  }

  function updatePdfDraft(index: number, patch: Partial<PdfDraft>) {
    setPdfDrafts(current => current.map((draft, i) => i === index
      ? { ...draft, ...patch, duplicate: patch.invoice_id !== undefined ? false : draft.duplicate }
      : draft));
  }

  async function previewCsvAppend(event: FormEvent) {
    event.preventDefault();
    if (!csvAppendFile) return;
    setCsvAppendBusy(true); setCsvAppendError(''); setCsvAppendMessage('');
    setCsvAppendRows([]); setConfirmCsvAppend(false); setConfirmCsvCurrency(false);
    try {
      if (csvAppendFile.size > 5_000_000) throw new Error('CSV must be smaller than 5 MB.');
      const bytes = new Uint8Array(await csvAppendFile.arrayBuffer());
      let binary = '';
      for (let offset = 0; offset < bytes.length; offset += 8192) {
        binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
      }
      const result = await apiRequest<{rows: any[]; mapping: Record<string,string>; unmapped: string[]; saved: boolean}>(
        `${apiUrl}/invoices/preview`,
        { filename: csvAppendFile.name, content_base64: btoa(binary) },
      );
      const validRows = result.rows.filter((row: any) => !(row.flags || []).length);
      const skippedRows = result.rows.filter((row: any) => (row.flags || []).length);
      if (!validRows.length) {
        setCsvAppendRows(skippedRows);
        throw new Error('No new valid invoices were found. Duplicate or invalid rows are shown below.');
      }
      const saved = await apiRequest<{saved: boolean; invoice_count: number}>(
        `${apiUrl}/invoices/commit`,
        { rows: validRows, mode: 'append', confirm_currency_inr: true, keep_duplicates: false },
      );
      await onChanged();
      setMessage(`Imported ${saved.invoice_count} invoice${saved.invoice_count === 1 ? '' : 's'} and added them to the main invoice list.${skippedRows.length ? ` Skipped ${skippedRows.length} duplicate or invalid row${skippedRows.length === 1 ? '' : 's'}.` : ''}`);
      setCsvAppendRows([]); setCsvAppendFile(null); setPage(0); setView('invoices');
    } catch (e) { setCsvAppendError(e instanceof Error ? e.message : 'Could not preview this CSV'); }
    finally { setCsvAppendBusy(false); }
  }

  async function commitCsvAppend() {
    setCsvAppendBusy(true); setCsvAppendError(''); setCsvAppendMessage('');
    try {
      if (!confirmCsvAppend || !confirmCsvCurrency) throw new Error('Confirm both checkboxes before adding invoices.');
      const nonDupeRows = csvAppendRows.filter((r: any) => !(r.flags || []).includes('duplicate'));
      if (!nonDupeRows.length) throw new Error('All invoices are duplicates. Remove duplicate flags or upload a different file.');
      const result = await apiRequest<{saved: boolean; invoice_count: number}>(
        `${apiUrl}/invoices/commit`,
        { rows: nonDupeRows, mode: 'append', confirm_currency_inr: true, keep_duplicates: false },
      );
      await onChanged();
      setMessage(`Added ${result.invoice_count} invoice${result.invoice_count === 1 ? '' : 's'}. All imported invoices are now shown below.`);
      setCsvAppendRows([]); setCsvAppendFile(null);
      setConfirmCsvAppend(false); setConfirmCsvCurrency(false);
      setPage(0); setView('invoices');
    } catch (e) { setCsvAppendError(e instanceof Error ? e.message : 'Could not add invoices'); }
    finally { setCsvAppendBusy(false); }
  }

  async function receive(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      const result = await jsonRequest(`${apiUrl}/receipts`, { invoice_id: invoiceId, receipt_id: receiptId,
        amount: Number(amount), date: paymentDate });
      setLedger(result); setReceiptId(crypto.randomUUID()); setAmount('');
      setMessage('Receipt recorded. Available cash and the outstanding balance have been updated.');
      await onChanged();
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not record receipt'); }
    finally { setBusy(false); }
  }

  const filtered = (ledger?.invoices ?? []).filter(invoice =>
    `${invoice.id} ${invoice.customer_name} ${invoice.ledger_status}`.toLowerCase().includes(search.toLowerCase()));
  const open = ledger?.invoices.filter(invoice => invoice.outstanding > 0) ?? [];
  const template = 'invoice_id,customer_id,customer_name,email,phone,segment,amount,issue_date,due_date,status,received_amount,paid_date,currency\nINV-1,C1,Example Customer,customer@example.com,+919876543210,small,10000,2026-10-01,2026-10-20,open,2000,,INR\n';
  return <div className="space-y-5">
    <div><p className="eyebrow">CASH OPERATIONS</p><h1 className="mt-1.5 text-[28px] font-semibold tracking-tight">Invoices & cash</h1>
      <p className="mt-2 text-sm text-slate-500">Track what is owed, record what arrives, and keep your plan up to date.</p></div>
    <div className="ledger-summary">
      <div><p>Available cash</p><strong>{money(business.opening_cash)}</strong></div>
      <div><p>Outstanding receivables</p><strong>{money(ledger?.outstanding ?? 0)}</strong></div>
      <div><p>Invoice receipts to date</p><strong>{money(ledger?.received ?? 0)}</strong></div>
    </div>
    <nav className="section-tabs" aria-label="Cash operations">
      {([['invoices', 'Invoices'], ['receipts', 'Record a receipt'], ['import', 'Import data'], ['plan', 'Outflows & sales']] as const).map(([id, label]) =>
        <button key={id} type="button" aria-pressed={view === id} disabled={busy} onClick={() => setView(id)}>{label}</button>)}
    </nav>
    {error && <p role="alert" className="rounded-xl bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
    {message && <p role="status" className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-800">{message}</p>}
    <div>
      {false && view === 'import' && <form className="panel-card max-w-2xl space-y-4 p-6" onSubmit={importFile}>
        <h2 className="font-semibold">Import invoices</h2>
        <p className="text-xs leading-5 text-slate-500">CSV or Excel (.xlsx) replaces the current workspace, including its receipt log and plan. Up to 2,000 rows and 5 MB. Use whole INR amounts and ISO dates. For PDF, use the separate review-and-add workflow below.</p>
        <div className="rounded-xl border border-indigo-100 bg-indigo-50/70 p-4">
          <p className="text-xs font-semibold text-indigo-950">Download invoice template:</p>
          <div className="mt-2 flex flex-wrap gap-2.5">
            <a
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
              download="blank_invoice_template.csv"
              href={`data:text/csv;charset=utf-8,${encodeURIComponent(template)}`}
            >
              📥 Blank CSV Template
            </a>
            <a
              className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-900 shadow-sm transition hover:bg-amber-100"
              download="stress_test_shortfall.csv"
              href="/sample_data/stress_test_shortfall.csv"
            >
              📊 Sample Overdue Dataset (30 invoices)
            </a>
          </div>
        </div>
        <label className="block text-xs">Invoice file<input className="field-input mt-1" required type="file" accept=".csv,.xlsx" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>
        <label className="block text-xs">Business name<input className="field-input mt-1" required value={name} onChange={e => setName(e.target.value)} /></label>
        <label className="block text-xs">Observation date<input className="field-input mt-1" required type="date" value={asOf} onChange={e => setAsOf(e.target.value)} /></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs">Available cash (INR)<input className="field-input mt-1" required type="number" min="0" step="1" value={cash} onChange={e => setCash(Number(e.target.value))} /></label>
          <label className="text-xs">Safety floor (INR)<input className="field-input mt-1" required type="number" min="0" step="1" value={floor} onChange={e => setFloor(Number(e.target.value))} /></label>
        </div>
        <p className="text-xs leading-5 text-slate-500">Enter cash already in the bank on the observation date, including earlier receipts. Import replaces this workspace, receipt log, customer relationship context, supplier bills and obligations. Future sales start at zero.</p>
        <label className="flex items-start gap-2 text-xs"><input type="checkbox" checked={replace} onChange={e => setReplace(e.target.checked)} />I understand this replaces the current workspace.</label>
        <label className="flex items-start gap-2 text-xs leading-5"><input type="checkbox" checked={unitsConfirmed} onChange={e => setUnitsConfirmed(e.target.checked)} />I confirm every amount is the original invoice amount in INR. No currency conversion is performed; USD, CAD and other currencies are rejected.</label>
        <button className="button-primary" disabled={busy || !replace || !unitsConfirmed || !file}>Import workspace</button>
      </form>}
      {view === 'import' && <section className="panel-card max-w-4xl space-y-5 p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <span className="kpi-icon driver-blue mt-0.5"><FileSearch size={18} /></span>
          <div><h2 className="font-semibold">Review invoices from a text PDF</h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">PDFs are parsed locally by the backend. This is rule-based draft extraction—not OCR or AI. Scanned/image-only PDFs are unsupported. Extracted fields are unverified until you review and add them.</p>
          </div>
        </div>
        <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={previewPdf}>
          <label className="block min-w-0 flex-1 text-xs">Text-based PDF, max 5 MB and 25 pages; one invoice per page<input className="field-input mt-1" required type="file" accept=".pdf,application/pdf" onChange={e => { setPdfFile(e.target.files?.[0] ?? null); setPdfDrafts([]); setPdfError(''); setPdfMessage(''); }} /></label>
          <button className="button-secondary shrink-0" disabled={pdfBusy || !pdfFile}>{pdfBusy && !pdfDrafts.length ? 'Reading PDF…' : 'Extract draft fields'}</button>
        </form>
        {pdfError && <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-5 text-amber-900">{pdfError}</p>}
        {pdfMessage && <p role="status" className="rounded-xl bg-emerald-50 p-3 text-sm leading-5 text-emerald-800">{pdfMessage}</p>}
        {pdfDrafts.length > 0 && <div className="space-y-4">
          <div className="rounded-xl border border-indigo-100 bg-indigo-50/70 p-4 text-sm leading-6 text-indigo-950">
            <strong>Append only:</strong> reviewed invoices will be added to this workspace. Existing invoices, cash, receipts, expenses and supplier bills are preserved. Duplicate invoice IDs are blocked.
          </div>
          {pdfDrafts.map((draft, index) => {
            const sameId = pdfDrafts.some((candidate, other) => other !== index && candidate.invoice_id.trim() === draft.invoice_id.trim());
            const alreadyExists = business.invoices.some(invoice => invoice.id === draft.invoice_id.trim());
            const confidence = (field: string) => draft.field_confidence[field] ?? 'medium';
            return <article key={`${draft.source_page}-${index}`} className="rounded-xl border border-slate-200 p-4 sm:p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div><h3 className="text-sm font-semibold">Invoice draft {index + 1} · PDF page {draft.source_page}</h3>
                  <p className="mt-1 text-xs text-slate-500">Confidence describes extraction only; verify every field against the source.</p></div>
                <button type="button" className="icon-button" aria-label={`Remove invoice draft ${index + 1}`} onClick={() => setPdfDrafts(current => current.filter((_, i) => i !== index))}><Trash2 size={16} /></button>
              </div>
              {(draft.duplicate || sameId || alreadyExists) && <p role="alert" className="mb-3 rounded-lg bg-rose-50 p-3 text-xs text-rose-800">Duplicate invoice number. Correct the ID or remove this draft; duplicates cannot be added.</p>}
              {draft.issues.length > 0 && <div className="mb-4 rounded-lg bg-amber-50 p-3">
                <p className="text-xs font-semibold text-amber-900">Extraction flags to review</p>
                <ul className="mt-1 list-inside list-disc space-y-1 text-xs leading-5 text-amber-800">{draft.issues.map((issue, i) => <li key={i}>{issue}</li>)}</ul>
              </div>}
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <label className="text-xs">Invoice ID · {confidence('invoice_id')}<input className="field-input mt-1" value={draft.invoice_id} onChange={e => updatePdfDraft(index, { invoice_id: e.target.value })} /></label>
                <label className="text-xs">Customer name · {confidence('customer_name')}<input className="field-input mt-1" value={draft.customer_name} onChange={e => updatePdfDraft(index, { customer_name: e.target.value })} /></label>
                <label className="text-xs">Customer ID · {confidence('customer_id')}<input className="field-input mt-1" value={draft.customer_id} onChange={e => updatePdfDraft(index, { customer_id: e.target.value })} /></label>
                <label className="text-xs">Customer type · owner review<select className="field-input mt-1" value={draft.segment ?? ''} onChange={e => updatePdfDraft(index, { segment: e.target.value as PdfDraft['segment'] })}>
                  <option value="">Choose type</option><option value="small">Small business</option><option value="corporate">Corporate</option><option value="government">Government</option>
                </select></label>
                <label className="text-xs">Invoice total (whole INR) · {confidence('amount')}<input className="field-input mt-1" type="number" min="1" step="1" value={draft.amount ?? ''} onChange={e => updatePdfDraft(index, { amount: e.target.value === '' ? null : Number(e.target.value) })} /></label>
                <label className="text-xs">Currency · {confidence('currency')}<input className="field-input mt-1" value={draft.currency} onChange={e => updatePdfDraft(index, { currency: e.target.value })} /></label>
                <label className="text-xs">Issue date · {confidence('issue_date')}<input className="field-input mt-1" type="date" value={draft.issue_date} onChange={e => updatePdfDraft(index, { issue_date: e.target.value })} /></label>
                <label className="text-xs">Due date · {confidence('due_date')}<input className="field-input mt-1" type="date" value={draft.due_date} onChange={e => updatePdfDraft(index, { due_date: e.target.value })} /></label>
                <label className="text-xs">Amount received (INR) · {confidence('received_amount')}<input className="field-input mt-1" type="number" min="0" step="1" value={draft.received_amount ?? ''} onChange={e => updatePdfDraft(index, { received_amount: e.target.value === '' ? null : Number(e.target.value) })} /></label>
                {draft.received_amount === draft.amount && draft.amount !== null && <label className="text-xs">Payment date<input className="field-input mt-1" type="date" max={business.as_of} value={draft.paid_date ?? ''} onChange={e => updatePdfDraft(index, { paid_date: e.target.value || null })} /></label>}
              </div>
              <details className="mt-4 rounded-lg bg-slate-50 p-3">
                <summary className="cursor-pointer text-xs font-medium text-slate-700">Source text from PDF page {draft.source_page}</summary>
                <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words text-[11px] leading-5 text-slate-600">{draft.source_text}</pre>
              </details>
            </article>;
          })}
          <label className="flex items-start gap-2 text-xs leading-5"><input type="checkbox" checked={confirmPdfCurrency} onChange={e => setConfirmPdfCurrency(e.target.checked)} />I reviewed the amounts and confirm every invoice amount and any received amount is in INR. No currency conversion was performed.</label>
          <label className="flex items-start gap-2 text-xs leading-5"><input type="checkbox" checked={confirmPdfAppend} onChange={e => setConfirmPdfAppend(e.target.checked)} />I confirm these reviewed invoices should be added to the existing workspace. This does not replace my current records or update cash for historical receipts.</label>
          <button type="button" className="button-primary" disabled={pdfBusy || !pdfDrafts.length || !confirmPdfAppend || !confirmPdfCurrency || pdfDrafts.some(draft => draft.duplicate || business.invoices.some(invoice => invoice.id === draft.invoice_id.trim())) || pdfDrafts.some(draft => pdfDrafts.filter(other => other.invoice_id.trim() === draft.invoice_id.trim()).length > 1)} onClick={() => void applyPdfDrafts()}>{pdfBusy ? 'Adding reviewed invoices…' : `Add ${pdfDrafts.length} reviewed invoice${pdfDrafts.length === 1 ? '' : 's'}`}</button>
          <button type="button" className="button-secondary ml-2" disabled={pdfBusy} onClick={() => { setPdfDrafts([]); setConfirmPdfAppend(false); setConfirmPdfCurrency(false); setPdfError(''); }}>Cancel review</button>
        </div>}
      </section>}
      {view === 'import' && <section className="panel-card max-w-4xl space-y-5 p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <span className="kpi-icon driver-blue mt-0.5">📄</span>
          <div><h2 className="font-semibold">Import invoices</h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">Every accepted invoice is added to the current workspace and appears in the main invoice list. Existing cash, receipts, expenses, supplier bills and customer relationships are preserved. Duplicate invoice IDs are skipped.</p>
          </div>
        </div>
        <div className="rounded-xl border border-indigo-100 bg-indigo-50/70 p-4">
          <p className="text-xs font-semibold text-indigo-950">Download an invoice file:</p>
          <div className="mt-2 flex flex-wrap gap-2.5">
            <a className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700" download="blank_invoice_template.csv" href={`data:text/csv;charset=utf-8,${encodeURIComponent(template)}`}>Blank CSV template</a>
            <a className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-900" download="stress_test_shortfall.csv" href="/sample_data/stress_test_shortfall.csv">Sample overdue dataset</a>
          </div>
        </div>
        <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={previewCsvAppend}>
          <label className="block min-w-0 flex-1 text-xs">CSV file with invoices to add, max 5 MB<input className="field-input mt-1" required type="file" accept=".csv" onChange={e => { setCsvAppendFile(e.target.files?.[0] ?? null); setCsvAppendRows([]); setCsvAppendError(''); setCsvAppendMessage(''); setConfirmCsvAppend(false); setConfirmCsvCurrency(false); }} /></label>
          <button className="button-primary shrink-0" disabled={csvAppendBusy || !csvAppendFile}>{csvAppendBusy ? 'Importing invoices…' : 'Import invoices'}</button>
        </form>
        {csvAppendError && <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-5 text-amber-900">{csvAppendError}</p>}
        {csvAppendMessage && <p role="status" className="rounded-xl bg-emerald-50 p-3 text-sm leading-5 text-emerald-800">{csvAppendMessage}</p>}
        {csvAppendRows.length > 0 && <div className="space-y-4">
          <div className="rounded-xl border border-indigo-100 bg-indigo-50/70 p-4 text-sm leading-6 text-indigo-950">
            <strong>Append only:</strong> {csvAppendRows.length} invoice{csvAppendRows.length === 1 ? '' : 's'} found. Existing data is preserved.
            {csvAppendRows.some((r: any) => r.flags?.includes('duplicate')) && <span className="ml-2 text-amber-800">({csvAppendRows.filter((r: any) => r.flags?.includes('duplicate')).length} flagged as duplicates and will be skipped)</span>}
          </div>
          <div className="overflow-x-auto"><table className="ledger-table"><thead><tr>{['Invoice ID', 'Customer', 'Amount', 'Issue date', 'Due date', 'Received', 'Flags'].map(h => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>{csvAppendRows.map((row: any, i: number) => <tr key={i} className={`border-t border-slate-100 ${row.flags?.includes('duplicate') ? 'bg-amber-50' : ''}`}>
              <td className="p-2">{row.invoice_id}</td><td className="p-2">{row.customer_name || row.customer_id}</td>
              <td className="p-2">{money(row.amount)}</td><td className="p-2">{row.issue_date}</td><td className="p-2">{row.due_date}</td>
              <td className="p-2">{money(row.received_amount || 0)}</td>
              <td className="p-2">{(row.flags || []).join(', ') || '—'}</td>
            </tr>)}</tbody></table></div>
          <label className="flex items-start gap-2 text-xs leading-5"><input type="checkbox" checked={confirmCsvCurrency} onChange={e => setConfirmCsvCurrency(e.target.checked)} />I reviewed the amounts and confirm every invoice amount is in INR.</label>
          <label className="flex items-start gap-2 text-xs leading-5"><input type="checkbox" checked={confirmCsvAppend} onChange={e => setConfirmCsvAppend(e.target.checked)} />I confirm these invoices should be added to the existing workspace. This does not replace current records.</label>
          <div className="flex gap-2">
            <button type="button" className="button-primary" disabled={csvAppendBusy || !csvAppendRows.length || !confirmCsvAppend || !confirmCsvCurrency} onClick={() => void commitCsvAppend()}>{csvAppendBusy ? 'Adding invoices…' : `Add ${csvAppendRows.filter((r: any) => !(r.flags || []).includes('duplicate')).length} invoice${csvAppendRows.filter((r: any) => !(r.flags || []).includes('duplicate')).length === 1 ? '' : 's'}`}</button>
            <button type="button" className="button-secondary" disabled={csvAppendBusy} onClick={() => { setCsvAppendRows([]); setConfirmCsvAppend(false); setConfirmCsvCurrency(false); setCsvAppendError(''); }}>Cancel review</button>
          </div>
        </div>}
      </section>}
      {view === 'receipts' && <form className="panel-card max-w-xl space-y-4 p-6" onSubmit={receive}>
        <h2 className="font-semibold">Record money received</h2>
        <p className="text-xs leading-5 text-slate-500">Record a receipt only if it is not already included in the cash figure above. Partial receipts reduce the amount forecast for that invoice.</p>
        <label className="block text-xs">Invoice<select className="field-input mt-1" required value={invoiceId} onChange={e => { setInvoiceId(e.target.value); setReceiptId(crypto.randomUUID()); }}>
          <option value="">Choose an open invoice</option>{open.map(invoice => <option key={invoice.id} value={invoice.id}>{invoice.id} · {invoice.customer_name} · {money(invoice.outstanding)}</option>)}
        </select></label>
        <label className="block text-xs">Amount received (INR)<input className="field-input mt-1" type="number" step="1" min="1" max={open.find(i => i.id === invoiceId)?.outstanding} required value={amount} onChange={e => { setAmount(e.target.value); setReceiptId(crypto.randomUUID()); }} /></label>
        <label className="block text-xs">Receipt date<input className="field-input mt-1" type="date" required max={business.as_of} value={paymentDate} onChange={e => { setPaymentDate(e.target.value); setReceiptId(crypto.randomUUID()); }} /></label>
        <button className="button-primary" disabled={busy || !invoiceId}>Record receipt</button>
        <div className="mt-5 rounded-xl bg-slate-50 p-4 text-sm leading-7">
          <p>Available cash: <strong>{money(business.opening_cash)}</strong></p>
          <p>Outstanding receivables: <strong>{money(ledger?.outstanding ?? 0)}</strong></p>
          <p>Invoice receipts to date: <strong>{money(ledger?.received ?? 0)}</strong></p>
          <p className="text-xs text-slate-500">Receipt total is historical; it is not added again to available cash.</p>
        </div>
      </form>}
    </div>
    {view === 'plan' && <WorkspacePlan apiUrl={apiUrl} business={business} onChanged={onChanged} />}
    {ledger && view === 'invoices' && <div className="flex flex-col gap-5">
      <section className="panel-card overflow-hidden"><div className="flex flex-wrap items-center justify-between gap-3 p-5"><div><h2 className="text-sm font-semibold">All invoices <span className="ml-2 rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">{ledger.invoices.length}</span></h2><p className="mt-1 text-xs text-slate-500">Expected income and received payments, kept separate.</p></div><button className="button-primary" onClick={() => setView('import')}>Import invoices</button></div>
        <label className="mx-5 mb-4 block max-w-sm text-xs">Search invoices<input className="field-input mt-1" value={search} placeholder="Search by invoice, customer or status…" onChange={e => { setSearch(e.target.value); setPage(0); }} /></label>
        <div className="overflow-x-auto"><table className="ledger-table"><thead><tr>{['Invoice', 'Customer', 'Status', 'Due date', 'Amount', 'Received', 'Outstanding'].map(title => <th key={title}>{title}</th>)}</tr></thead>
          <tbody>{filtered.slice(page * 25, page * 25 + 25).map(invoice => <tr className="border-t border-slate-100" key={invoice.id}>
            <td className="p-2">{invoice.id}</td><td className="p-2">{invoice.customer_name}</td><td className="p-2"><span className="invoice-status" data-status={invoice.ledger_status}>{invoice.ledger_status}</span></td><td className="p-2">{invoice.due_date}</td>
            <td className="p-2">{money(invoice.amount)}</td><td className="p-2">{money(invoice.received)}</td><td className="p-2">{money(invoice.outstanding)}</td></tr>)}</tbody></table></div>
        {!filtered.length && <div className="px-6 py-14 text-center">
          <p className="text-sm font-semibold text-slate-700">{search ? 'No matching invoices' : 'Your invoice ledger starts here'}</p>
          <p className="mt-2 text-xs text-slate-500">{search ? 'Try another invoice number, customer or status.' : 'Import your first file to track receivables and forecast expected payments.'}</p>
          {!search && (
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <button type="button" className="button-primary" onClick={() => setView('import')}>
                Upload invoices
              </button>
              <button type="button" className="button-secondary" onClick={() => setMessage('Account Aggregator and bank connector will be available in connected data settings.')}>
                Connect data
              </button>
            </div>
          )}
        </div>}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 p-4 text-xs text-slate-500"><span>{filtered.length ? `${page * 25 + 1}–${Math.min((page + 1) * 25, filtered.length)} of ${filtered.length} invoices` : '0 invoices'}</span><div className="flex gap-2"><button className="button-secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
          <button className="button-secondary" disabled={(page + 1) * 25 >= filtered.length} onClick={() => setPage(page + 1)}>Next</button></div></div>
      </section>
      <div className="grid gap-5 lg:grid-cols-2">{([['Receivable aging', ledger.receivable_aging], ['Payable aging', ledger.payable_aging]] as const).map(([title, buckets]) =>
        <section className="panel-card p-5" key={title}><h2 className="text-sm font-semibold">{title}</h2><p className="mt-1 text-xs text-slate-500">Days past due; 90+ means more than 90 days.</p>
          <div className="mt-4 space-y-2">{Object.entries(buckets).map(([bucket, value]) => <div key={bucket} className="flex justify-between text-sm"><span>{bucket}</span><strong className="font-medium">{money(value)}</strong></div>)}</div></section>)}</div>
      <section className="panel-card p-5"><h2 className="text-sm font-semibold">Customer concentration</h2>
        <p className="mt-1 text-xs text-slate-500">Customers owing at least 30% of outstanding receivables are flagged.</p>
        {ledger.concentration.length === 0 && <p className="mt-4 text-xs text-slate-400">No outstanding receivables to analyse.</p>}
        {ledger.concentration.slice(0, 5).map((customer, index) => <p key={`${customer.customer}-${index}`} className={`mt-3 text-sm ${customer.share >= .3 ? 'text-amber-800' : 'text-slate-600'}`}>
          {customer.customer}: {money(customer.amount)} ({Math.round(customer.share * 100)}%){customer.share >= .3 && ' · High concentration'}</p>)}
      </section>
    </div>}
  </div>;
}
