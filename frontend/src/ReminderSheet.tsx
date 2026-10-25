import { useState } from 'react';
import {
  Check,
  Copy,
  ExternalLink,
  Mail,
  MessageSquare,
  Phone,
  Send,
  ShieldAlert,
  X,
} from 'lucide-react';
import { apiRequest } from './api';

export interface ReminderData {
  id: string;
  invoice_ids: string[];
  customer_id: string;
  customer_name?: string | null;
  rung: number;
  channel: 'email' | 'whatsapp' | 'sms' | 'letter';
  subject: string;
  body: string;
  status: 'draft' | 'approved' | 'sent' | 'cancelled';
  recipient?: string | null;
  created_at?: string;
  sent_at?: string | null;
  oldest_overdue_days?: number;
  total_amount?: number;
}

interface ReminderSheetProps {
  apiUrl: string;
  reminder: ReminderData;
  onClose: () => void;
  onUpdated: () => void;
}

const RUNG_LABELS: Record<number, { title: string; tone: string; desc: string }> = {
  1: { title: 'Rung 1: Friendly Notice', tone: 'risk-low', desc: 'Upcoming due date in 3 days' },
  2: { title: 'Rung 2: Polite Reminder', tone: 'risk-medium', desc: 'Payment due today' },
  3: { title: 'Rung 3: Firm Follow-up', tone: 'risk-medium', desc: '7+ days overdue' },
  4: { title: 'Rung 4: Final Demand', tone: 'risk-high', desc: '15+ days overdue with MSMED statutory interest note' },
  5: { title: 'Rung 5: Legal Draft', tone: 'risk-high', desc: '30+ days overdue · Draft for advocate review' },
};

export default function ReminderSheet({
  apiUrl,
  reminder,
  onClose,
  onUpdated,
}: ReminderSheetProps) {
  const [subject, setSubject] = useState(reminder.subject);
  const [body, setBody] = useState(reminder.body);
  const [channel, setChannel] = useState(reminder.channel || 'email');
  const [recipient, setRecipient] = useState(reminder.recipient || '');
  const [status, setStatus] = useState(reminder.status);
  const [confirmLegal, setConfirmLegal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ text: string; link?: string | null; mailto?: string | null } | null>(null);
  const [copied, setCopied] = useState(false);

  const rungInfo = RUNG_LABELS[reminder.rung] || RUNG_LABELS[2];

  async function handleApprove() {
    setBusy(true);
    setError(null);
    try {
      // First save any edits
      await apiRequest(`${apiUrl}/reminders/${reminder.id}/edit`, {
        subject,
        body,
        channel,
        recipient,
      });
      // Then approve
      await apiRequest(`${apiUrl}/reminders/${reminder.id}/approve`, {});
      setStatus('approved');
      onUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not approve reminder');
    } finally {
      setBusy(false);
    }
  }

  async function handleSend() {
    if (reminder.rung === 5 && !confirmLegal) {
      setError('Please confirm that this notice is a draft for advocate review only.');
      return;
    }
    setBusy(true);
    setError(null);
    setFeedback(null);
    try {
      const res = await apiRequest<{
        status: string;
        channel: string;
        delivery?: { status?: string; message?: string; mailto?: string | null; error?: string };
        link?: string | null;
      }>(`${apiUrl}/reminders/${reminder.id}/send`, {
        confirm_legal_draft: confirmLegal,
      });

      setStatus('sent');
      onUpdated();

      if (channel === 'whatsapp' || channel === 'sms') {
        const link = res.link;
        setFeedback({
          text: `Message prepared for ${channel.toUpperCase()}. Click link to open chat.`,
          link,
        });
        if (link) {
          window.open(link, '_blank');
        }
      } else {
        const del = res.delivery;
        if (del?.status === 'sent') {
          setFeedback({ text: 'Email successfully delivered via SMTP.' });
        } else {
          setFeedback({
            text: 'Mock email recorded (SMTP unconfigured; mock mode active). Use mailto fallback if desired.',
            mailto: del?.mailto,
          });
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to dispatch reminder');
    } finally {
      setBusy(false);
    }
  }

  function handleCopy() {
    navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="reminder-sheet-title"
    >
      <div className="relative flex max-h-[92vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-100 p-5">
          <div>
            <div className="flex items-center gap-2">
              <span className={`risk-badge ${rungInfo.tone}`}>{rungInfo.title}</span>
              <span className="text-xs text-slate-400">· {rungInfo.desc}</span>
            </div>
            <h2 id="reminder-sheet-title" className="mt-1.5 text-lg font-bold text-slate-900">
              {reminder.customer_name || reminder.customer_id}
            </h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Invoices: {reminder.invoice_ids.join(', ')}
            </p>
          </div>
          <button
            type="button"
            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>

        {/* Content body */}
        <div className="flex-1 space-y-4 overflow-y-auto p-5 text-xs">
          {error && (
            <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-rose-800">
              {error}
            </div>
          )}

          {feedback && (
            <div
              role="status"
              className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-emerald-900"
            >
              <p className="font-semibold">{feedback.text}</p>
              <div className="mt-2 flex gap-3">
                {feedback.link && (
                  <a
                    href={feedback.link}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 font-semibold underline"
                  >
                    Open {channel} chat <ExternalLink size={12} />
                  </a>
                )}
                {feedback.mailto && (
                  <a href={feedback.mailto} className="inline-flex items-center gap-1 font-semibold underline">
                    Open in default email app <ExternalLink size={12} />
                  </a>
                )}
              </div>
            </div>
          )}

          {/* Rung 5 Advocate Review Warning */}
          {reminder.rung === 5 && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-900">
              <div className="flex items-start gap-2.5">
                <ShieldAlert size={18} className="mt-0.5 shrink-0 text-amber-700" />
                <div>
                  <h4 className="font-bold">Draft only: have an advocate review</h4>
                  <p className="mt-1 text-[11px] leading-5 text-amber-800">
                    This draft includes statutory MSMED compound interest demands. Antigravity CashFlow provides
                    drafting assistance and does not provide legal advice or auto-dispatch notices.
                  </p>
                  <label className="mt-2.5 flex items-center gap-2 font-semibold">
                    <input
                      type="checkbox"
                      checked={confirmLegal}
                      onChange={(e) => setConfirmLegal(e.target.checked)}
                    />
                    <span>I confirm this document is a draft prepared for advocate review only</span>
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* Delivery Channel and Recipient */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="block font-semibold text-slate-700">Dispatch Channel</label>
              <div className="mt-1 flex gap-2">
                <button
                  type="button"
                  className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg border py-2 text-xs font-semibold ${
                    channel === 'email'
                      ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                      : 'border-slate-200 bg-white text-slate-600'
                  }`}
                  onClick={() => setChannel('email')}
                >
                  <Mail size={14} /> Email
                </button>
                <button
                  type="button"
                  className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg border py-2 text-xs font-semibold ${
                    channel === 'whatsapp'
                      ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                      : 'border-slate-200 bg-white text-slate-600'
                  }`}
                  onClick={() => setChannel('whatsapp')}
                >
                  <MessageSquare size={14} /> WhatsApp
                </button>
                <button
                  type="button"
                  className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg border py-2 text-xs font-semibold ${
                    channel === 'sms'
                      ? 'border-sky-600 bg-sky-50 text-sky-700'
                      : 'border-slate-200 bg-white text-slate-600'
                  }`}
                  onClick={() => setChannel('sms')}
                >
                  <Phone size={14} /> SMS
                </button>
              </div>
            </div>

            <div>
              <label className="block font-semibold text-slate-700">
                {channel === 'email' ? 'Recipient Email' : 'Recipient Phone Number'}
              </label>
              <input
                type="text"
                className="field-input mt-1"
                placeholder={channel === 'email' ? 'client@example.com' : '9876543210'}
                value={recipient}
                onChange={(e) => setRecipient(e.target.value)}
              />
            </div>
          </div>

          {/* Subject Line */}
          <div>
            <label className="block font-semibold text-slate-700">Subject</label>
            <input
              type="text"
              className="field-input mt-1"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
          </div>

          {/* Message Body */}
          <div>
            <div className="flex items-center justify-between">
              <label className="block font-semibold text-slate-700">Message Text</label>
              <button
                type="button"
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-600 hover:underline"
                onClick={handleCopy}
              >
                <Copy size={11} /> {copied ? 'Copied!' : 'Copy text'}
              </button>
            </div>
            <textarea
              rows={8}
              className="field-input mt-1 font-mono text-[11px] leading-5"
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
        </div>

        {/* Footer controls */}
        <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/50 p-4">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold text-slate-500">Status:</span>
            <span
              className={`risk-badge ${
                status === 'sent' ? 'risk-low' : status === 'approved' ? 'risk-medium' : 'bg-slate-100 text-slate-700'
              }`}
            >
              {status.toUpperCase()}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button type="button" className="button-secondary" onClick={onClose}>
              Close
            </button>

            {status === 'draft' ? (
              <button
                type="button"
                className="button-primary"
                disabled={busy}
                onClick={() => void handleApprove()}
              >
                <Check size={14} />
                {busy ? 'Approving…' : 'Approve reminder'}
              </button>
            ) : (
              <button
                type="button"
                className="button-primary"
                disabled={busy || (reminder.rung === 5 && !confirmLegal)}
                onClick={() => void handleSend()}
              >
                <Send size={14} />
                {busy
                  ? 'Dispatching…'
                  : channel === 'whatsapp'
                  ? 'Open WhatsApp'
                  : channel === 'sms'
                  ? 'Send SMS'
                  : 'Send email'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
