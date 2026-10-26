import { useEffect, useState } from 'react';
import { apiRequest } from './api';
type Payment = { id: string; invoice_id: string | null; amount: number; decision: string; status: string; fraud_score: number; fraud_reasons: string[]; payer_name: string | null; created_at: string };
const money = (value: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value);
export default function PaymentReviewPage({ apiUrl }: { apiUrl: string }) {
  const [rows, setRows] = useState<Payment[]>([]); const [error, setError] = useState('');
  const load = () => apiRequest<Payment[]>(`${apiUrl}/admin/payments`).then(setRows).catch(e => setError(e.message));
  useEffect(() => { void load(); }, [apiUrl]);
  const review = (id: string, action: 'approve' | 'reject') => apiRequest(`${apiUrl}/admin/payments/${id}/review/${action}`).then(load).catch(e => setError(e.message));
  return <section className="panel-card overflow-hidden"><div className="p-5"><p className="eyebrow">MOCK BANK</p><h1 className="mt-1 text-xl font-semibold">Payment fraud review</h1><p className="mt-2 text-xs text-slate-500">Mock-bank decisions only. No real payment gateway is connected.</p></div>{error && <p role="alert" className="p-5 text-sm text-rose-700">{error}</p>}{!error && !rows.length && <p className="p-5 text-sm text-slate-500">No bank payments have been received.</p>}{!!rows.length && <div className="overflow-x-auto"><table className="ledger-table"><thead><tr><th>Invoice</th><th>Amount</th><th>Decision</th><th>Score</th><th>Reasons</th><th>Status</th><th>Review</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><td>{row.invoice_id ?? 'Unmatched'}</td><td>{money(row.amount)}</td><td>{row.decision}</td><td>{row.fraud_score}</td><td>{row.fraud_reasons.join(', ')}</td><td>{row.status}</td><td>{row.status === 'pending_review' && <><button className="button-primary" onClick={() => void review(row.id, 'approve')}>Approve</button><button className="button-secondary ml-2" onClick={() => void review(row.id, 'reject')}>Reject</button></>}</td></tr>)}</tbody></table></div>}</section>;
}
