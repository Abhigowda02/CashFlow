import React, { useEffect, useState } from 'react';
import {
  Building2,
  CheckCircle2,
  Mail,
  MessageSquare,
  Phone,
  RefreshCw,
} from 'lucide-react';
import { apiRequest } from './api';
import ReminderSheet, { type ReminderData } from './ReminderSheet';

interface SettingsState {
  sender_name?: string;
  contact_email?: string;
  contact_phone?: string;
  upi_id?: string;
  bank_name?: string;
  account_name?: string;
  account_number?: string;
  ifsc_code?: string;
}

interface ReminderLogRow {
  id: string;
  reminder_id?: string;
  customer_id: string;
  invoice_ids: string;
  rung: number;
  channel: string;
  subject: string;
  recipient?: string;
  status: string;
  timestamp: string;
}

const money = (val: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);

const RUNG_NAME: Record<number, string> = {
  1: 'Rung 1 (-3d Friendly)',
  2: 'Rung 2 (Due Today)',
  3: 'Rung 3 (+7d Firm)',
  4: 'Rung 4 (+15d Demand)',
  5: 'Rung 5 (+30d Legal Draft)',
};

export default function RemindersPage({ apiUrl }: { apiUrl: string }) {
  const [queue, setQueue] = useState<ReminderData[]>([]);
  const [history, setHistory] = useState<ReminderLogRow[]>([]);
  const [settings, setSettings] = useState<SettingsState>({});
  const [loading, setLoading] = useState(true);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsSavedMsg, setSettingsSavedMsg] = useState(false);
  const [selectedReminder, setSelectedReminder] = useState<ReminderData | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [queueData, historyData, settingsData] = await Promise.all([
        apiRequest<ReminderData[]>(`${apiUrl}/reminders/queue`),
        apiRequest<ReminderLogRow[]>(`${apiUrl}/reminders/history`),
        apiRequest<SettingsState>(`${apiUrl}/reminders/settings`),
      ]);
      setQueue(queueData);
      setHistory(historyData);
      setSettings(settingsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load reminder queue');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, [apiUrl]);

  async function handleSaveSettings(e: React.FormEvent) {
    e.preventDefault();
    setSavingSettings(true);
    setSettingsSavedMsg(false);
    try {
      await apiRequest(`${apiUrl}/reminders/settings`, settings);
      setSettingsSavedMsg(true);
      setTimeout(() => setSettingsSavedMsg(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save payment settings');
    } finally {
      setSavingSettings(false);
    }
  }

  const totalOverdue = queue.reduce((acc, curr) => acc + (curr.total_amount || 0), 0);

  return (
    <div className="space-y-6">
      {/* Top title bar */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">DUNNING & ESCALATION LADDER</p>
          <h1 className="mt-1.5 text-[28px] font-semibold tracking-tight">Customer Payment Reminders</h1>
          <p className="mt-1 text-sm text-slate-500">
            Escalation ladder (-3, 0, +7, +15, +30 days) with owner approval-first workflow and SMTP/WhatsApp/SMS delivery.
          </p>
        </div>
        <button
          type="button"
          className="button-secondary"
          disabled={loading}
          onClick={() => void loadData()}
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          {loading ? 'Refreshing…' : 'Refresh queue'}
        </button>
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {error}
        </div>
      )}

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="panel-card p-5">
          <p className="text-xs font-medium text-slate-500">Pending Reminder Drafts</p>
          <p className="mt-2 text-2xl font-bold tracking-tight text-slate-900">{queue.length}</p>
          <p className="mt-1 text-[11px] text-slate-400">Awaiting your approval before dispatch</p>
        </div>
        <div className="panel-card p-5">
          <p className="text-xs font-medium text-slate-500">Total Receivables in Queue</p>
          <p className="mt-2 text-2xl font-bold tracking-tight text-indigo-700">{money(totalOverdue)}</p>
          <p className="mt-1 text-[11px] text-slate-400">Reconciled across overdue invoices</p>
        </div>
        <div className="panel-card p-5">
          <p className="text-xs font-medium text-slate-500">Messages Dispatched</p>
          <p className="mt-2 text-2xl font-bold tracking-tight text-emerald-700">{history.length}</p>
          <p className="mt-1 text-[11px] text-slate-400">Recorded in immutable audit log</p>
        </div>
      </div>

      {/* Main Grid: Queue on Left, Payment Settings on Right */}
      <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        {/* Reminders Queue Table */}
        <section className="panel-card overflow-hidden">
          <div className="border-b border-slate-100 p-5">
            <h2 className="text-sm font-bold text-slate-900">Today's Reminders Queue</h2>
            <p className="mt-1 text-xs text-slate-500">
              Invoices are grouped by customer. Multiple overdue invoices are combined into one reminder draft.
            </p>
          </div>

          {loading ? (
            <div className="p-10 text-center text-xs text-slate-500">Evaluating reminder rungs…</div>
          ) : queue.length === 0 ? (
            <div className="p-12 text-center">
              <CheckCircle2 size={32} className="mx-auto text-emerald-500" />
              <h3 className="mt-3 text-sm font-semibold text-slate-800">No overdue reminders pending</h3>
              <p className="mt-1 text-xs text-slate-500">
                All invoices are either current, settled, or paused by an active promise to pay or open dispute.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="ledger-table">
                <thead>
                  <tr>
                    <th>Customer / Invoices</th>
                    <th>Ladder Stage</th>
                    <th>Channel</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {queue.map((rem) => (
                    <tr key={rem.id}>
                      <td>
                        <p className="font-semibold text-slate-900">{rem.customer_name || rem.customer_id}</p>
                        <p className="mt-0.5 text-[11px] text-slate-500">
                          {rem.invoice_ids.length} invoice(s): {rem.invoice_ids.join(', ')}
                        </p>
                      </td>
                      <td>
                        <span
                          className={`risk-badge ${
                            rem.rung >= 4 ? 'risk-high' : rem.rung >= 2 ? 'risk-medium' : 'risk-low'
                          }`}
                        >
                          {RUNG_NAME[rem.rung] || `Rung ${rem.rung}`}
                        </span>
                      </td>
                      <td>
                        <span className="inline-flex items-center gap-1 capitalize text-slate-600">
                          {rem.channel === 'whatsapp' ? (
                            <MessageSquare size={13} className="text-emerald-600" />
                          ) : rem.channel === 'sms' ? (
                            <Phone size={13} className="text-sky-600" />
                          ) : (
                            <Mail size={13} className="text-indigo-600" />
                          )}
                          {rem.channel}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${
                            rem.status === 'approved'
                              ? 'bg-amber-100 text-amber-800'
                              : rem.status === 'sent'
                              ? 'bg-emerald-100 text-emerald-800'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {rem.status}
                        </span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="button-primary py-1 px-3 text-xs"
                          onClick={() => setSelectedReminder(rem)}
                        >
                          {rem.status === 'draft' ? 'Review & Approve' : 'Review & Send'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Business Payment Details Configuration */}
        <section className="panel-card p-5">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <Building2 size={16} className="text-indigo-600" />
            <h2 className="text-sm font-bold text-slate-900">Payment Clearance Details</h2>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            These details are automatically included in customer reminder templates.
          </p>

          <form onSubmit={handleSaveSettings} className="mt-4 space-y-3 text-xs">
            <div>
              <label className="block font-medium text-slate-700">Sender / Business Name</label>
              <input
                type="text"
                className="field-input mt-1"
                placeholder="Apex Enterprises Accounts"
                value={settings.sender_name ?? ''}
                onChange={(e) => setSettings({ ...settings, sender_name: e.target.value })}
              />
            </div>

            <div>
              <label className="block font-medium text-slate-700">UPI ID</label>
              <input
                type="text"
                className="field-input mt-1"
                placeholder="apex@okicici"
                value={settings.upi_id ?? ''}
                onChange={(e) => setSettings({ ...settings, upi_id: e.target.value })}
              />
            </div>

            <div>
              <label className="block font-medium text-slate-700">Bank Name</label>
              <input
                type="text"
                className="field-input mt-1"
                placeholder="HDFC Bank"
                value={settings.bank_name ?? ''}
                onChange={(e) => setSettings({ ...settings, bank_name: e.target.value })}
              />
            </div>

            <div>
              <label className="block font-medium text-slate-700">Account Number</label>
              <input
                type="text"
                className="field-input mt-1"
                placeholder="50200012345678"
                value={settings.account_number ?? ''}
                onChange={(e) => setSettings({ ...settings, account_number: e.target.value })}
              />
            </div>

            <div>
              <label className="block font-medium text-slate-700">IFSC Code</label>
              <input
                type="text"
                className="field-input mt-1"
                placeholder="HDFC0001234"
                value={settings.ifsc_code ?? ''}
                onChange={(e) => setSettings({ ...settings, ifsc_code: e.target.value })}
              />
            </div>

            {settingsSavedMsg && (
              <p className="text-emerald-700 font-semibold">Payment settings saved successfully.</p>
            )}

            <button type="submit" className="button-secondary w-full" disabled={savingSettings}>
              {savingSettings ? 'Saving…' : 'Save payment details'}
            </button>
          </form>
        </section>
      </div>

      {/* Transmission History / Evidence Log */}
      <section className="panel-card overflow-hidden">
        <div className="border-b border-slate-100 p-5">
          <h2 className="text-sm font-bold text-slate-900">Transmission History & Audit Evidence</h2>
          <p className="mt-1 text-xs text-slate-500">
            Immutable log of all sent notices, channels, and delivery statuses for commercial records.
          </p>
        </div>

        {history.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500">No sent reminder history recorded yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="ledger-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Customer</th>
                  <th>Stage</th>
                  <th>Channel / Recipient</th>
                  <th>Subject</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id}>
                    <td className="text-slate-500 font-mono text-[11px]">
                      {new Intl.DateTimeFormat('en-IN', {
                        dateStyle: 'medium',
                        timeStyle: 'short',
                      }).format(new Date(h.timestamp))}
                    </td>
                    <td className="font-semibold text-slate-800">{h.customer_id}</td>
                    <td>{RUNG_NAME[h.rung] || `Rung ${h.rung}`}</td>
                    <td>
                      <span className="font-medium text-slate-700">{h.channel}</span> · {h.recipient || 'N/A'}
                    </td>
                    <td className="max-w-xs truncate text-slate-600" title={h.subject}>
                      {h.subject}
                    </td>
                    <td>
                      <span className="risk-badge risk-low text-[10px]">{h.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ReminderSheet Drawer / Modal */}
      {selectedReminder && (
        <ReminderSheet
          apiUrl={apiUrl}
          reminder={selectedReminder}
          onClose={() => setSelectedReminder(null)}
          onUpdated={() => {
            void loadData();
          }}
        />
      )}
    </div>
  );
}
