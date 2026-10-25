import React, { useEffect, useState } from 'react';
import {
  Bell,
  CheckCircle2,
  Clock,
  ExternalLink,
  Mail,
  Settings,
  ShieldAlert,
  AlertTriangle,
  Info,
  X,
  RefreshCw,
} from 'lucide-react';
import { apiRequest } from './api';

export type AlertKind = 'shortage_warning' | 'late_invoice' | 'msme_due' | 'stale_cash' | 'other';
export type AlertSeverity = 'info' | 'warning' | 'critical';

export interface AlertItem {
  id: string;
  kind: AlertKind;
  severity: AlertSeverity;
  title: string;
  body: string;
  created_at: string;
  read: boolean;
  dedupe_key: string;
  link?: string | null;
}

export interface AlertPrefs {
  risk_threshold: number;
  horizon_days: number;
  email_enabled: boolean;
  owner_email?: string | null;
  quiet_hours?: string | null;
  digest_weekly: boolean;
}

interface NotificationCenterProps {
  apiUrl: string;
  onNavigate?: (tabId: string) => void;
  onOpenBalanceModal?: () => void;
}

export default function NotificationCenter({
  apiUrl,
  onNavigate,
  onOpenBalanceModal,
}: NotificationCenterProps) {
  const [open, setOpen] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [prefs, setPrefs] = useState<AlertPrefs | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [testEmailMsg, setTestEmailMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  async function loadAlerts() {
    setLoading(true);
    try {
      const data = await apiRequest<AlertItem[]>(`${apiUrl}/alerts`);
      setAlerts(data);
    } catch {
      // ignore in background
    } finally {
      setLoading(false);
    }
  }

  async function loadPrefs() {
    try {
      const p = await apiRequest<AlertPrefs>(`${apiUrl}/alerts/prefs`);
      setPrefs(p);
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    void loadAlerts();
    void loadPrefs();
    const interval = setInterval(() => {
      void loadAlerts();
    }, 60000);
    return () => clearInterval(interval);
  }, [apiUrl]);

  async function markRead(id: string) {
    setBusyAction(id);
    try {
      await apiRequest(`${apiUrl}/alerts/${id}/read`, {});
      setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, read: true } : a)));
    } catch {
      // fallback
    } finally {
      setBusyAction(null);
    }
  }

  async function snoozeAlert(id: string, days = 1) {
    setBusyAction(id);
    try {
      await apiRequest(`${apiUrl}/alerts/${id}/snooze`, { days });
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    } catch {
      // fallback
    } finally {
      setBusyAction(null);
    }
  }

  async function markAllRead() {
    setBusyAction('all');
    try {
      await apiRequest(`${apiUrl}/alerts/mark-all-read`, {});
      setAlerts((prev) => prev.map((a) => ({ ...a, read: true })));
    } catch {
      // fallback
    } finally {
      setBusyAction(null);
    }
  }

  async function savePrefs(e: React.FormEvent) {
    e.preventDefault();
    if (!prefs) return;
    setBusyAction('save_prefs');
    try {
      const updated = await apiRequest<{ status: string; prefs: AlertPrefs }>(`${apiUrl}/alerts/prefs`, prefs);
      setPrefs(updated.prefs);
      setShowSettings(false);
    } catch {
      // fallback
    } finally {
      setBusyAction(null);
    }
  }

  async function sendTestEmail() {
    setBusyAction('test_email');
    setTestEmailMsg(null);
    try {
      const res = await apiRequest<{ status: string; delivery: { status: string; message?: string; error?: string } }>(
        `${apiUrl}/alerts/test-email`,
        { recipient_email: prefs?.owner_email }
      );
      if (res.delivery?.status === 'sent') {
        setTestEmailMsg({ type: 'success', text: `Test email dispatched via SMTP to ${prefs?.owner_email}.` });
      } else {
        setTestEmailMsg({
          type: 'success',
          text: `Mock email recorded successfully for ${prefs?.owner_email} (SMTP unconfigured; mock delivery active).`,
        });
      }
    } catch (err) {
      setTestEmailMsg({
        type: 'error',
        text: err instanceof Error ? err.message : 'Could not dispatch test email.',
      });
    } finally {
      setBusyAction(null);
    }
  }

  const unreadCount = alerts.filter((a) => !a.read).length;

  function handleLinkClick(link?: string | null) {
    if (!link) return;
    setOpen(false);
    if (link === '/ledger') {
      if (onOpenBalanceModal) onOpenBalanceModal();
      else if (onNavigate) onNavigate('ledger');
    } else if (link === '/forecast') {
      if (onNavigate) onNavigate('forecast');
    } else if (link === '/expenses') {
      if (onNavigate) onNavigate('expenses');
    } else if (link === '/reminders') {
      if (onNavigate) onNavigate('reminders');
    } else if (onNavigate) {
      onNavigate(link.replace('/', ''));
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        className="icon-button relative"
        aria-label={`Notifications and alerts, ${unreadCount} unread`}
        title={`Notifications and alerts (${unreadCount} unread)`}
        onClick={() => {
          setOpen(!open);
          setShowSettings(false);
        }}
      >
        <Bell size={18} />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold text-white shadow">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Alerts and notifications center"
          className="absolute right-0 top-11 z-50 w-80 sm:w-96 rounded-xl border border-slate-200 bg-white shadow-2xl"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-800">Alerts & Notifications</span>
              {unreadCount > 0 && (
                <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-semibold text-rose-700">
                  {unreadCount} new
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                title="Alert preferences"
                onClick={() => setShowSettings(!showSettings)}
              >
                <Settings size={15} />
              </button>
              <button
                type="button"
                className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                title="Close"
                onClick={() => setOpen(false)}
              >
                <X size={15} />
              </button>
            </div>
          </div>

          {/* Quick Actions Bar */}
          {!showSettings && alerts.length > 0 && (
            <div className="flex items-center justify-between border-b border-slate-50 bg-slate-50/50 px-4 py-1.5 text-[11px] text-slate-500">
              <button
                type="button"
                className="hover:text-indigo-600"
                onClick={() => void loadAlerts()}
                disabled={loading}
              >
                <span className="flex items-center gap-1">
                  <RefreshCw size={11} className={loading ? 'animate-spin' : ''} /> Refresh
                </span>
              </button>
              {unreadCount > 0 && (
                <button
                  type="button"
                  className="font-medium text-indigo-600 hover:underline"
                  disabled={busyAction === 'all'}
                  onClick={() => void markAllRead()}
                >
                  Mark all as read
                </button>
              )}
            </div>
          )}

          {/* Settings Modal Mode */}
          {showSettings && prefs ? (
            <form onSubmit={savePrefs} className="space-y-4 p-4 text-xs">
              <div className="flex items-center justify-between">
                <h4 className="font-semibold text-slate-800">Alert Preferences</h4>
                <button
                  type="button"
                  className="text-[11px] text-indigo-600 hover:underline"
                  onClick={() => setShowSettings(false)}
                >
                  Back to alerts
                </button>
              </div>

              <div>
                <label className="block font-medium text-slate-700">
                  Shortage Risk Threshold: {prefs.risk_threshold}%
                </label>
                <input
                  type="range"
                  min="10"
                  max="90"
                  step="5"
                  className="range-control mt-1.5 w-full"
                  value={prefs.risk_threshold}
                  onChange={(e) => setPrefs({ ...prefs, risk_threshold: Number(e.target.value) })}
                />
                <p className="mt-1 text-[10px] text-slate-400">
                  Alert when forecast shows chance of cash deficit &gt;= {prefs.risk_threshold}%.
                </p>
              </div>

              <div>
                <label className="block font-medium text-slate-700">
                  Forecast Warning Horizon (Days)
                </label>
                <input
                  type="number"
                  min="7"
                  max="60"
                  className="field-input mt-1"
                  value={prefs.horizon_days}
                  onChange={(e) => setPrefs({ ...prefs, horizon_days: Number(e.target.value) })}
                />
              </div>

              <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                <label className="flex items-center gap-2 font-medium text-slate-800">
                  <input
                    type="checkbox"
                    checked={prefs.email_enabled}
                    onChange={(e) => setPrefs({ ...prefs, email_enabled: e.target.checked })}
                  />
                  <span>Dispatch email alerts for critical shortages</span>
                </label>
                <p className="mt-1 text-[10px] text-slate-500">
                  Sends privacy-conscious alert messages (no exposed bank balances on lock-screens).
                </p>

                {prefs.email_enabled && (
                  <div className="mt-2.5 space-y-2">
                    <input
                      type="email"
                      placeholder="owner@example.com"
                      className="field-input text-xs"
                      value={prefs.owner_email ?? ''}
                      onChange={(e) => setPrefs({ ...prefs, owner_email: e.target.value })}
                    />
                    <button
                      type="button"
                      className="button-secondary w-full py-1.5 text-xs"
                      disabled={busyAction === 'test_email'}
                      onClick={() => void sendTestEmail()}
                    >
                      <Mail size={12} />
                      {busyAction === 'test_email' ? 'Dispatching…' : 'Send test alert email'}
                    </button>
                    {testEmailMsg && (
                      <p
                        className={`text-[11px] ${
                          testEmailMsg.type === 'success' ? 'text-emerald-700' : 'text-rose-700'
                        }`}
                      >
                        {testEmailMsg.text}
                      </p>
                    )}
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  className="button-secondary"
                  onClick={() => setShowSettings(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="button-primary"
                  disabled={busyAction === 'save_prefs'}
                >
                  Save preferences
                </button>
              </div>
            </form>
          ) : (
            /* Alerts List */
            <div className="max-h-[380px] overflow-y-auto divide-y divide-slate-100">
              {alerts.length === 0 ? (
                <div className="p-8 text-center">
                  <CheckCircle2 size={24} className="mx-auto text-emerald-500" />
                  <p className="mt-2 text-xs font-semibold text-slate-700">No active alerts</p>
                  <p className="mt-1 text-[11px] text-slate-400">
                    Your projected runway and upcoming dues look healthy.
                  </p>
                </div>
              ) : (
                alerts.map((alert) => (
                  <div
                    key={alert.id}
                    className={`p-3.5 transition-colors ${
                      alert.read ? 'bg-white opacity-80' : 'bg-indigo-50/20'
                    }`}
                  >
                    <div className="flex items-start gap-2.5">
                      <div className="mt-0.5 shrink-0">
                        {alert.severity === 'critical' ? (
                          <ShieldAlert size={16} className="text-rose-600" />
                        ) : alert.severity === 'warning' ? (
                          <AlertTriangle size={16} className="text-amber-600" />
                        ) : (
                          <Info size={16} className="text-blue-600" />
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-1">
                          <p className="truncate text-xs font-semibold text-slate-800">
                            {alert.title}
                          </p>
                          <span
                            className={`risk-badge text-[9px] ${
                              alert.severity === 'critical'
                                ? 'risk-high'
                                : alert.severity === 'warning'
                                ? 'risk-medium'
                                : 'risk-low'
                            }`}
                          >
                            {alert.severity}
                          </span>
                        </div>
                        <p className="mt-1 text-[11px] leading-4 text-slate-600">{alert.body}</p>

                        <div className="mt-2.5 flex items-center justify-between text-[11px]">
                          {alert.link ? (
                            <button
                              type="button"
                              className="inline-flex items-center gap-1 font-semibold text-indigo-600 hover:text-indigo-800"
                              onClick={() => handleLinkClick(alert.link)}
                            >
                              <span>
                                {alert.link === '/forecast'
                                  ? 'View forecast'
                                  : alert.link === '/expenses'
                                  ? 'View obligations'
                                  : alert.link === '/reminders'
                                  ? 'Review reminders'
                                  : 'Resolve in cash'}
                              </span>
                              <ExternalLink size={11} />
                            </button>
                          ) : (
                            <span />
                          )}

                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              className="text-slate-400 hover:text-slate-600"
                              title="Snooze 1 day"
                              disabled={busyAction === alert.id}
                              onClick={() => void snoozeAlert(alert.id, 1)}
                            >
                              <Clock size={13} />
                            </button>
                            {!alert.read && (
                              <button
                                type="button"
                                className="text-indigo-600 hover:text-indigo-800"
                                title="Mark read"
                                disabled={busyAction === alert.id}
                                onClick={() => void markRead(alert.id)}
                              >
                                <CheckCircle2 size={14} />
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
