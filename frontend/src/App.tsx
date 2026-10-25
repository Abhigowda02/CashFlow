import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Banknote,
  CalendarDays,
  Check,
  Clock3,
  Factory,
  FileText,
  Gauge,
  LayoutDashboard,
  LoaderCircle,
  RefreshCw,
  Sparkles,
  TrendingDown,
  Wallet,
  Users,
  type LucideIcon,
} from "lucide-react";
import {
  ComposedChart,
  Area,
  CartesianGrid,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import LedgerPage from './LedgerPage';
import CustomersPage from './CustomersPage';
import CollectionsPanel from './CollectionsPanel';
import ExpensesPage from './ExpensesPage';
import ScenarioPlanner from './ScenarioPlanner';
import { type PlannerDraft } from './scenarioLogic';
import { API_BASE, apiRequest, type Account } from './api';
import { type PlanBusiness } from './WorkspacePlan';

const API_URL = API_BASE;

type Customer = {
  id: string;
  name: string;
  segment: "government" | "corporate" | "small";
};

type Invoice = {
  id: string;
  customer_id: string;
  amount: number;
  due_date: string;
  status: "open" | "paid";
  received_amount?: number;
};

type Business = PlanBusiness & {
  name: string;
  as_of: string;
  opening_cash: number;
  safety_floor: number;
  customers: Customer[];
  invoices: Invoice[];
  data_source?: string;
};

type ForecastDriver = {
  type: "late_invoice" | "obligation" | "supplier_bill";
  ref: string;
  text: string;
};

type Forecast = {
  dates: string[];
  p10: number[];
  p50: number[];
  p90: number[];
  safety_floor: number;
  shortage_prob: number;
  first_shortage_date: string | null;
  min_balance_p50: number;
  drivers: ForecastDriver[];
  warnings?: string[];
  meta?: { delay_model_used?: string; delay_model_requested?: string; data_source?: string;
    payment_model?: { status: string; message: string }; model_training_source?: string };
};

type Action = {
  id: string;
  title: string;
  type: string;
  cost: number;
  risk: "low" | "medium" | "high";
  note: string;
  shortage_prob_after: number;
  first_shortage_date_after: string | null;
  runway_days_gained: number;
};

type TabId = "dashboard" | "forecast" | "simulator" | "actions" | "ledger" | "customers" | "expenses";

const tabs: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: "dashboard", label: "Overview", icon: LayoutDashboard },
  { id: "ledger", label: "Invoices & cash", icon: FileText },
  { id: "customers", label: "Customers", icon: Users },
  { id: "expenses", label: "Expenses & obligations", icon: CalendarDays },
  { id: "forecast", label: "Cash forecast", icon: TrendingDown },
  { id: "simulator", label: "Scenario planner", icon: Sparkles },
  { id: "actions", label: "Recommended actions", icon: Check },
];

const inr = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const compactInr = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  notation: "compact",
  maximumFractionDigits: 1,
});

function money(value: number) {
  return inr.format(value);
}

function formatDate(value: string | null) {
  if (!value) return "No shortage in 90 days";
  const parsed = new Date(`${value}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(parsed);
}

function shortDate(value: string) {
  const parsed = new Date(`${value}T12:00:00`);
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat("en-IN", {
        day: "numeric",
        month: "short",
      }).format(parsed);
}

function dayDifference(from: string, to: string) {
  const start = new Date(`${from}T12:00:00`).getTime();
  const end = new Date(`${to}T12:00:00`).getTime();
  return Math.max(0, Math.ceil((end - start) / 86_400_000));
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return apiRequest<T>(`${API_URL}${path}`, undefined, signal);
}

function chartData(forecast: Forecast) {
  return forecast.dates.map((date, index) => {
    const p10 = forecast.p10[index] ?? 0;
    const p50 = forecast.p50[index] ?? 0;
    const p90 = forecast.p90[index] ?? 0;
    return {
      date,
      p10,
      p50,
      p90,
      range: [p10, p90] as [number, number],
    };
  });
}

function probability(value: number) {
  return `${Math.round(value * 100)}%`;
}

function shortageTone(value: number) {
  if (value >= 0.5) return "danger";
  if (value >= 0.2) return "warning";
  return "success";
}

function displayError(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function App({ account, onSignout }: { account: Account; onSignout: () => Promise<void> }) {
  const [signoutError, setSignoutError] = useState('');
  const [delayModel, setDelayModel] = useState('empirical');
  const [activeTab, setActiveTab] = useState<TabId>("dashboard");
  const [business, setBusiness] = useState<Business | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [actions, setActions] = useState<Action[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [plannerDraft, setPlannerDraft] = useState<PlannerDraft>({ name: '', changes: [] });

  const loadData = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setLoadError(null);
    try {
      const [businessData, forecastData, actionsData] = await Promise.all([
        getJson<Business>("/business", signal),
        getJson<Forecast>(`/forecast?delay_model=${delayModel}`, signal),
        getJson<Action[]>(`/actions?delay_model=${delayModel}`, signal),
      ]);
      if (signal?.aborted) return;
      setBusiness(businessData);
      setForecast(forecastData);
      setActions(actionsData);
      if (businessData.invoices.length === 0) {
        setActiveTab("ledger");
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setLoadError(displayError(error));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [delayModel]);

  useEffect(() => {
    const controller = new AbortController();
    void loadData(controller.signal);
    return () => controller.abort();
  }, [loadData]);

  const overdueReceivables = useMemo(() => {
    if (!business) return 0;
    return business.invoices
      .filter(
        (invoice) =>
          invoice.status === "open" && invoice.due_date < business.as_of,
      )
      .reduce((total, invoice) => total + invoice.amount - (invoice.received_amount ?? 0), 0);
  }, [business]);

  const hasForecastInputs = useMemo(() => {
    if (!business) return false;
    return business.invoices.some(
      (invoice) =>
        invoice.status === "open" &&
        invoice.amount - (invoice.received_amount ?? 0) > 0,
    ) ||
      (business.obligations?.length ?? 0) > 0 ||
      (business.supplier_bills ?? []).some((bill) => bill.status === "open") ||
      (business.sales_plan?.monthly_amount ?? 0) > 0;
  }, [business]);

  const hasExpenseWarning = useMemo(() => {
    if (!business) return false;
    if (forecast?.warnings && forecast.warnings.length > 0) return true;
    return (business.obligations?.length ?? 0) === 0 && (business.sales_plan?.monthly_amount ?? 0) === 0;
  }, [business, forecast]);

  const runwayDays = useMemo(() => {
    if (!business || !forecast) return null;
    const firstBelowFloor = forecast.p50.findIndex(
      (balance) => balance < forecast.safety_floor,
    );
    if (firstBelowFloor < 0) return null;
    const firstDate = forecast.dates[firstBelowFloor];
    return firstDate ? dayDifference(business.as_of, firstDate) : null;
  }, [business, forecast]);

  if (loading) return <LoadingScreen />;

  if (loadError || !business || !forecast) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#f7f8fa] px-5">
        <div className="w-full max-w-md rounded-3xl border border-rose-100 bg-white p-8 text-center shadow-xl shadow-rose-950/5">
          <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-rose-50 text-rose-600">
            <AlertCircle size={25} />
          </div>
          <h1 className="mt-5 text-xl font-semibold text-slate-900">
            Couldn’t load your cash-flow data
          </h1>
          <p className="mt-2 break-words text-sm leading-6 text-slate-500">
            {loadError ?? "The API returned incomplete business data."}
          </p>
          <button className="button-primary mt-6" onClick={() => void loadData()}>
            <RefreshCw size={16} />
            Try again
          </button>
        </div>
      </main>
    );
  }

  const tone = hasExpenseWarning ? "warning" : hasForecastInputs ? shortageTone(forecast.shortage_prob) : "warning";
  const firstShortage =
    forecast.dates.find(
      (_, index) => forecast.p50[index] < forecast.safety_floor,
    ) ?? null;

  return (
    <div className="workspace-shell text-slate-900">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <div className="mx-auto flex min-h-screen max-w-[1800px]">
        <aside className="sidebar-shell hidden w-[236px] shrink-0 flex-col px-4 py-6 lg:flex">
          <Brand />
          <div className="workspace-switcher">
            <span className="workspace-avatar">{business.name.slice(0, 2).toUpperCase()}</span>
            <div className="min-w-0"><p className="truncate text-xs font-semibold text-slate-800">{business.name}</p><p className="mt-1 text-[10px] text-slate-500">Business workspace · INR</p></div>
          </div>
          <div>
            <p className="nav-caption px-3">FINANCE</p>
            <nav aria-label="Primary navigation" className="mt-3 space-y-1.5">
              {tabs.map((tab) => (
                <TabButton
                  key={tab.id}
                  active={activeTab === tab.id}
                  icon={tab.icon}
                  label={tab.label}
                  onClick={() => setActiveTab(tab.id)}
                />
              ))}
            </nav>
          </div>
          <div className="mt-auto flex items-center gap-3 border-t border-slate-200 pt-5">
            <div className="workspace-avatar">
              {account.email.slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="truncate text-xs font-semibold text-slate-800">
                Business owner
              </p>
              <p className="mt-0.5 truncate text-[11px] text-slate-400" title={account.email}>{account.email}</p>
            </div>
          </div>
        </aside>

        <main id="main-content" className="min-w-0 flex-1 px-4 pb-10 pt-5 sm:px-7 lg:px-9 lg:pt-6">
          <header className="workspace-topbar">
            <div className="lg:hidden">
              <Brand />
            </div>
            <div className="hidden lg:block">
              <p className="text-xs font-medium text-slate-500">
                Workspace <span className="mx-2 text-slate-300">/</span><span className="text-slate-800">{tabs.find(tab => tab.id === activeTab)?.label}</span>
              </p>
              <p
                className="mt-1.5 text-[11px] text-slate-400"
                title="Observation Date (as_of): Financial accounting anchors to reconciled bank statements rather than silently ticking with the computer clock."
              >
                Observation date:{" "}
                <span className="font-medium text-slate-600">
                  {new Intl.DateTimeFormat("en-IN", {
                    weekday: "short",
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  }).format(new Date(`${business.as_of}T12:00:00`))}
                </span>
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button className="button-secondary" title={account.email} onClick={() => { void onSignout().catch(e => setSignoutError(e.message)); }}>Sign out</button>
              <label className="model-select">
                <span>Forecast method</span>
                <select aria-label="Forecast method" className="field-input" value={delayModel} onChange={event => setDelayModel(event.target.value)}>
                  <option value="empirical">Historical delays</option>
                  <option value="survival">Survival model</option>
                </select>
              </label>
              <button
                aria-label="Refresh data"
                className="icon-button"
                onClick={() => void loadData()}
                title="Refresh data"
              >
                <RefreshCw size={17} />
              </button>
            </div>
          </header>

          <nav aria-label="Primary navigation" className="mb-6 grid grid-cols-2 gap-2 pb-1 lg:hidden">
            {tabs.map((tab) => (
              <TabButton
                key={tab.id}
                active={activeTab === tab.id}
                compact
                icon={tab.icon}
                label={tab.label}
                onClick={() => setActiveTab(tab.id)}
              />
            ))}
          </nav>

          <div role="status" className="source-status">
            <span className="status-dot" />
            {business.data_source === 'imported' ? 'Imported invoice workspace' : 'Your business workspace'}
            {' · '}Model used: {forecast.meta?.delay_model_used ?? 'unknown'}
            {forecast.meta?.delay_model_used !== delayModel && ' · Requested model unavailable; historical-delay fallback used.'}
            {delayModel === 'survival' && ' · Model accuracy on this business has not been validated.'}
          </div>
          {delayModel === 'survival' && forecast.meta?.payment_model &&
            <p className="mb-5 text-xs leading-5 text-slate-500">{forecast.meta.payment_model.message}</p>}
          <p role="note" className="mb-5 text-xs leading-5 text-slate-600"><strong>Forecast estimates:</strong> not yet validated on representative real businesses. Observed history describes past records; forecasts estimate future outcomes; scenario changes are assumptions. Suggested actions do not guarantee collection or prevent a shortage.</p>
          {signoutError && <p role="alert" className="mb-4 text-sm text-rose-700">{signoutError}</p>}
          {!hasForecastInputs &&
            <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              Your forecast currently reflects cash on hand only. Add expected receipts and planned outflows before relying on the runway or shortage estimate.
              <button className="ml-2 underline" onClick={() => setActiveTab('ledger')}>Add your business records</button>
            </div>}
          {activeTab === 'ledger' && <LedgerPage apiUrl={API_URL} business={business} onChanged={() => loadData()} />}
          {activeTab === 'customers' && <CustomersPage apiUrl={API_URL} />}
          {activeTab === 'expenses' && <ExpensesPage apiUrl={API_URL} business={business} onChanged={() => loadData()} />}
          {activeTab === "dashboard" && (
            <Dashboard
              business={business}
              forecast={forecast}
              overdueReceivables={overdueReceivables}
              runwayDays={runwayDays}
              firstShortage={firstShortage}
              tone={tone}
              hasForecastInputs={hasForecastInputs}
              hasExpenseWarning={hasExpenseWarning}
              onNavigate={setActiveTab}
            />
          )}
          {activeTab === "forecast" && (
            <ForecastPage
              business={business}
              forecast={forecast}
              hasForecastInputs={hasForecastInputs}
              hasExpenseWarning={hasExpenseWarning}
              onNavigate={setActiveTab}
            />
          )}
          {activeTab === "simulator" && <ScenarioPlanner apiUrl={API_URL} business={business} forecast={forecast}
            delayModel={delayModel} draft={plannerDraft} onDraft={setPlannerDraft} />}
          {activeTab === "actions" && (
            <ActionsPage
              actions={actions}
              shortageProbability={forecast.shortage_prob}
              apiUrl={API_URL}
              delayModel={delayModel}
            />
          )}

          <footer className="mt-10 flex flex-col items-center justify-between gap-2 border-t border-slate-200/70 pt-5 text-[11px] text-slate-400 sm:flex-row">
            <span>Forecast uses your entered records; verify obligations and cash balances.</span>
            <span>Built for clearer cash-flow decisions</span>
          </footer>
        </main>
      </div>
    </div>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-3">
      <div className="brand-symbol">
        <Factory size={21} strokeWidth={1.8} />
      </div>
      <div>
        <p className="text-[17px] font-bold tracking-tight text-slate-900">
          cashflow<span className="text-indigo-600">.</span>
        </p>
        <p className="text-[10px] font-medium tracking-[0.12em] text-slate-400">
          BUSINESS FINANCE
        </p>
      </div>
    </div>
  );
}

function TabButton({
  active,
  compact = false,
  icon: Icon,
  label,
  onClick,
}: {
  active: boolean;
  compact?: boolean;
  icon: LucideIcon;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className={`nav-button ${active ? "nav-button-active" : ""} ${compact ? "nav-button-compact" : ""}`}
      onClick={onClick}
      type="button"
      aria-current={active ? 'page' : undefined}
    >
      <Icon size={18} strokeWidth={active ? 2.2 : 1.8} />
      <span>{label}</span>
    </button>
  );
}

function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-1.5 text-[25px] font-semibold tracking-[-0.035em] text-slate-900 sm:text-[28px]">
          {title}
        </h1>
        <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-500">
          {description}
        </p>
      </div>
      {action}
    </div>
  );
}

function Dashboard({
  business,
  forecast,
  overdueReceivables,
  runwayDays,
  firstShortage,
  tone,
  hasForecastInputs,
  hasExpenseWarning,
  onNavigate,
}: {
  business: Business;
  forecast: Forecast;
  overdueReceivables: number;
  runwayDays: number | null;
  firstShortage: string | null;
  tone: "danger" | "warning" | "success";
  hasForecastInputs: boolean;
  hasExpenseWarning: boolean;
  onNavigate: (tab: TabId) => void;
}) {
  const cards: {
    label: string;
    value: string;
    subtext: string;
    icon: LucideIcon;
    accent: string;
    trend?: "up" | "down";
  }[] = [
    {
      label: "Available cash",
      value: money(business.opening_cash),
      subtext: "Cash recorded as of the observation date",
      icon: Wallet,
      accent: "green",
    },
    {
      label: "Cash runway",
      value: hasExpenseWarning || !hasForecastInputs ? "—" : runwayDays === null ? "90+" : `${runwayDays} days`,
      subtext:
        hasExpenseWarning
          ? "Add expenses to calculate runway"
          : !hasForecastInputs
          ? "Add expected receipts and planned outflows"
          : runwayDays === null
          ? "Above safety floor for 90 days"
          : `Safety floor crossed ${formatDate(firstShortage)}`,
      icon: Gauge,
      accent: "blue",
      trend: !hasExpenseWarning && hasForecastInputs ? runwayDays === null ? "up" : "down" : undefined,
    },
    {
      label: "Overdue receivables",
      value: money(overdueReceivables),
      subtext: "Open invoices past their due date",
      icon: FileText,
      accent: "orange",
    },
    {
      label: "Shortage probability",
      value: hasExpenseWarning ? "—" : hasForecastInputs ? probability(forecast.shortage_prob) : "—",
      subtext: hasExpenseWarning
        ? "Add expenses to estimate shortage risk"
        : hasForecastInputs
        ? "Chance of falling below your safety floor"
        : "Add business records before interpreting this estimate",
      icon: AlertTriangle,
      accent: "purple",
    },
  ];

  return (
    <>
      <PageHeading
        eyebrow="LIQUIDITY"
        title="Cash overview"
        description="Your current cash position, upcoming pressure points, and next steps."
        action={
          <div
            className="flex w-fit items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 shadow-sm cursor-help"
            title="Observation Date (as_of): In financial accounting, bank balances must be reconciled against actual bank statements, not guessed by a timer."
          >
            <CalendarDays size={15} className="text-slate-400" />
            As of {formatDate(business.as_of)}
          </div>
        }
      />

      <div className={`shortage-banner shortage-${tone}`}>
        <div className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-white/15">
          {tone === "danger" ? (
            <AlertTriangle size={21} />
          ) : tone === "warning" ? (
            <AlertCircle size={21} />
          ) : (
            <Check size={21} />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold leading-6 sm:text-[15px]">
            {hasExpenseWarning
              ? "Add your expenses (or connect bank data) to see shortage risk"
              : !hasForecastInputs
              ? "Add business records to estimate cash risk"
              : forecast.shortage_prob >= 0.5
              ? `Cash shortage likely around ${firstShortage ? shortDate(firstShortage) : "the forecast period"} (${probability(forecast.shortage_prob)} probability)`
              : forecast.shortage_prob >= 0.2
                ? `Cash flow needs attention — ${probability(forecast.shortage_prob)} chance of falling below your safety floor`
                : `Looking steady — just ${probability(forecast.shortage_prob)} chance of a cash shortage`}
          </p>
          <p className="mt-0.5 text-xs opacity-80">
            {hasExpenseWarning
              ? (forecast.warnings?.[0] ?? "No expenses entered: forecast only shows invoice receipts. Add regular outflows to see when cash dips.")
              : !hasForecastInputs
              ? "The current forecast reflects cash on hand only; it is not a risk assessment."
              : forecast.shortage_prob >= 0.5
              ? "Take a look at your forecast and consider an action."
              : "Your 90-day forecast is based on expected receipts and upcoming obligations."}
          </p>
        </div>
        <button
          className="hidden items-center gap-1.5 rounded-xl bg-white/15 px-3 py-2 text-xs font-semibold text-white transition hover:bg-white/25 sm:flex"
          onClick={() => onNavigate(hasExpenseWarning ? "expenses" : hasForecastInputs ? "forecast" : "ledger")}
        >
          {hasExpenseWarning ? "Add expenses" : hasForecastInputs ? "View forecast" : "Add records"} <ArrowUpRight size={14} />
        </button>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <KpiCard key={card.label} {...card} />
        ))}
      </div>

      {hasExpenseWarning && (
        <aside aria-label="Missing expenses warning" className="mb-5 rounded-2xl border border-amber-300 bg-amber-50 p-5 text-amber-950 shadow-sm sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3.5">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-amber-200 text-amber-900">
                <CalendarDays size={22} />
              </div>
              <div>
                <h3 className="text-base font-semibold text-amber-950">
                  Add your expenses (or connect bank data) to see shortage risk
                </h3>
                <p className="mt-1 max-w-2xl text-xs leading-5 text-amber-900">
                  {forecast.warnings?.[0] ?? "No expenses entered: forecast only shows invoice receipts"}.
                  Because no payroll, rent, EMI, or supplier bills are recorded, the forecast line below only tracks invoice receipts.
                </p>
              </div>
            </div>
            <button
              type="button"
              className="button-primary shrink-0 !bg-amber-600 hover:!bg-amber-700 !text-white"
              onClick={() => onNavigate("expenses")}
            >
              <CalendarDays size={16} />
              Add your expenses
            </button>
          </div>
        </aside>
      )}

      {hasForecastInputs ? (
        <section className="panel-card mt-5 p-5 sm:p-6">
          <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="eyebrow">90-DAY OUTLOOK</p>
              <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-900">
                Cash balance forecast
              </h2>
            </div>
            <button
              className="button-secondary !px-3 !py-2 !text-xs"
              onClick={() => onNavigate("forecast")}
            >
              Explore forecast <ArrowUpRight size={14} />
            </button>
          </div>
          {hasExpenseWarning && (
            <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50/70 px-3.5 py-2 text-xs text-amber-900">
              <strong>Receipts-only projection:</strong> Operational expenses are missing. Enter recurring expenses to project true cash burn.
            </div>
          )}
          <ForecastChart forecast={forecast} compact />
        </section>
      ) : (
        <section className="panel-card mt-5 flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
          <div className="flex items-start gap-3">
            <span className="kpi-icon driver-blue mt-0.5"><FileText size={18} /></span>
            <div>
              <p className="text-sm font-semibold text-slate-800">Your forecast needs business activity</p>
              <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-500">
                Add open invoices, recurring expenses, supplier bills, or expected sales to see how cash may change over the next 90 days.
              </p>
            </div>
          </div>
          <button className="button-primary shrink-0" onClick={() => onNavigate("ledger")}>
            Add invoices or plan <ArrowUpRight size={15} />
          </button>
        </section>
      )}

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <section className="panel-card p-5 sm:p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="eyebrow">COLLECTIONS TO WATCH</p>
              <h2 className="mt-1 text-lg font-semibold tracking-tight">
                Overdue invoices
              </h2>
            </div>
            <div className="grid size-9 place-items-center rounded-xl bg-amber-50 text-amber-700">
              <Clock3 size={18} />
            </div>
          </div>
          <OverdueList business={business} />
        </section>
        <section className="panel-card p-5 sm:p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="eyebrow">{overdueReceivables > 0 ? "COLLECTIONS TO REVIEW" : "NEXT STEP"}</p>
              <h2 className="mt-1 text-lg font-semibold tracking-tight">
                {overdueReceivables > 0
                  ? "Follow up on overdue invoices"
                  : hasForecastInputs
                    ? "Review upcoming payments"
                    : "Build your cash plan"}
              </h2>
            </div>
            <div className="grid size-9 place-items-center rounded-xl bg-emerald-50 text-emerald-700">
              {overdueReceivables > 0 ? <Banknote size={18} /> : <CalendarDays size={18} />}
            </div>
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-500">
            {overdueReceivables > 0
              ? "Review overdue balances and decide which customers need a thoughtful follow-up."
              : hasForecastInputs
                ? "Check that recurring commitments and supplier due dates match your current plan."
                : "Import invoices and add your regular outflows so the forecast reflects your business."}
          </p>
          <button
            className="button-primary mt-5 w-full sm:w-auto"
            onClick={() => onNavigate(overdueReceivables > 0 ? "actions" : hasForecastInputs ? "expenses" : "ledger")}
          >
            {overdueReceivables > 0
              ? "View collection actions"
              : hasForecastInputs
                ? "Review expenses"
                : "Add business records"} <ArrowUpRight size={16} />
          </button>
        </section>
      </div>
    </>
  );
}

function KpiCard({
  label,
  value,
  subtext,
  icon: Icon,
  accent,
  trend,
}: {
  label: string;
  value: string;
  subtext: string;
  icon: LucideIcon;
  accent: string;
  trend?: "up" | "down";
}) {
  return (
    <div className="panel-card min-w-0 p-4 sm:p-5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-slate-500">{label}</p>
        <span className={`kpi-icon kpi-${accent}`}>
          <Icon size={17} />
        </span>
      </div>
      <div className="mt-4 flex items-end gap-2">
        <p className="truncate text-[22px] font-semibold tracking-[-0.04em] text-slate-900 sm:text-[25px]">
          {value}
        </p>
        {trend && (
          <span
            className={`mb-1 ${trend === "up" ? "text-emerald-600" : "text-rose-500"}`}
          >
            {trend === "up" ? (
              <ArrowUpRight size={16} />
            ) : (
              <ArrowDownRight size={16} />
            )}
          </span>
        )}
      </div>
      <p className="mt-1.5 text-[11px] leading-5 text-slate-400">{subtext}</p>
    </div>
  );
}

function OverdueList({ business }: { business: Business }) {
  const overdue = business.invoices
    .filter(
      (invoice) =>
        invoice.status === "open" && invoice.due_date < business.as_of,
    )
    .sort((left, right) => left.due_date.localeCompare(right.due_date));
  const visible = overdue.slice(0, 3);

  if (!visible.length) {
    return (
      <div className="mt-5 rounded-xl bg-slate-50 px-4 py-5 text-sm text-slate-500">
        No overdue invoices right now.
      </div>
    );
  }

  return (
    <div className="mt-3 divide-y divide-slate-100">
      {visible.map((invoice) => {
        const customer = business.customers.find(
          (item) => item.id === invoice.customer_id,
        );
        return (
          <div
            className="flex items-center justify-between gap-3 py-3"
            key={invoice.id}
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-700">
                {customer?.name ?? invoice.customer_id}
              </p>
              <p className="mt-0.5 text-[11px] text-slate-400">
                {invoice.id} · Due {shortDate(invoice.due_date)}
              </p>
            </div>
            <p className="shrink-0 text-sm font-semibold text-slate-800">
              {money(invoice.amount - (invoice.received_amount ?? 0))}
            </p>
          </div>
        );
      })}
      {overdue.length > visible.length && (
        <p className="pt-3 text-xs text-slate-400">
          +{overdue.length - visible.length} more overdue invoices
        </p>
      )}
    </div>
  );
}

function ForecastPage({
  business,
  forecast,
  hasForecastInputs,
  hasExpenseWarning,
  onNavigate,
}: {
  business: Business;
  forecast: Forecast;
  hasForecastInputs: boolean;
  hasExpenseWarning: boolean;
  onNavigate: (tab: TabId) => void;
}) {
  return (
    <>
      <PageHeading
        eyebrow="PLAN WITH MORE CONFIDENCE"
        title="Cash forecast"
        description="A 90-day view of your expected balance, with a range of outcomes and the safety floor to watch."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <span
              className="flex w-fit items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm cursor-help"
              title="Observation Date (as_of): In financial accounting, bank balances must be reconciled against actual bank statements, not guessed by a timer."
            >
              <CalendarDays size={14} className="text-slate-400" />
              As of {formatDate(business.as_of)}
            </span>
            <span className="flex w-fit items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-500">
              <span className="size-2 rounded-full bg-emerald-500" />
              90-day outlook
            </span>
          </div>
        }
      />
      {hasExpenseWarning && (
        <aside aria-label="Missing expenses notice" className="mb-6 rounded-2xl border border-amber-300 bg-amber-50 p-5 text-amber-950 shadow-sm sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3.5">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-amber-200 text-amber-900">
                <CalendarDays size={22} />
              </div>
              <div>
                <h3 className="text-base font-semibold text-amber-950">
                  Add your expenses (or connect bank data) to see shortage risk
                </h3>
                <p className="mt-1 max-w-2xl text-xs leading-5 text-amber-900">
                  {forecast.warnings?.[0] ?? "No expenses entered: forecast only shows invoice receipts"}.
                  Without recurring obligations (payroll, rent, taxes) or supplier bills, cash only accumulates or stays flat from receivables. Enter your planned expenses to calculate a true cash shortage risk.
                </p>
              </div>
            </div>
            <button
              type="button"
              className="button-primary shrink-0 !bg-amber-600 hover:!bg-amber-700 !text-white"
              onClick={() => onNavigate("expenses")}
            >
              <CalendarDays size={16} />
              Add your expenses
            </button>
          </div>
        </aside>
      )}
      {!hasForecastInputs && !hasExpenseWarning && (
        <aside aria-label="Forecast inputs guidance" className="mb-6 rounded-2xl border border-amber-200 bg-amber-50/90 p-5 text-amber-950">
          <div className="flex items-start gap-3">
            <span className="kpi-icon driver-amber mt-0.5"><FileText size={18} /></span>
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-amber-900">Your forecast currently has no business activity to project</h3>
              <p className="mt-1 text-xs leading-5 text-amber-800">
                The balance line below is flat because this workspace has no open invoices, recurring obligations, or supplier bills yet. Cash remains static at your opening cash balance.
              </p>
              <div className="mt-3 flex flex-wrap gap-2.5">
                <button
                  type="button"
                  className="button-secondary !py-1.5 !px-3 !text-xs !bg-white"
                  onClick={() => onNavigate('ledger')}
                >
                  Add or import invoices
                </button>
                <button
                  type="button"
                  className="button-secondary !py-1.5 !px-3 !text-xs !bg-white"
                  onClick={() => onNavigate('expenses')}
                >
                  Add recurring expenses & bills
                </button>
              </div>
            </div>
          </div>
        </aside>
      )}
      <section className="panel-card p-4 sm:p-6">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              Projected cash balance
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              Daily balance range · {formatDate(forecast.dates[0])} to{" "}
              {formatDate(forecast.dates.at(-1) ?? "")}
            </p>
          </div>
          <ForecastLegend />
        </div>
        {hasExpenseWarning && (
          <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50/70 px-4 py-2.5 text-xs text-amber-900 flex flex-wrap items-center justify-between gap-2">
            <span>
              <strong>Notice:</strong> This projection only shows expected customer collections. Real-world cash will be significantly lower once expenses are included.
            </span>
            <button
              type="button"
              className="font-medium underline hover:text-amber-950"
              onClick={() => onNavigate("expenses")}
            >
              Add expenses now
            </button>
          </div>
        )}
        <ForecastChart forecast={forecast} />
        <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 border-t border-slate-100 pt-4 text-xs text-slate-500">
          <span>
            <span className="font-semibold text-slate-700">Safety floor</span>{" "}
            {money(forecast.safety_floor)}
          </span>
          <span>
            <span className="font-semibold text-slate-700">Lowest P50</span>{" "}
            {money(forecast.min_balance_p50)}
          </span>
          <span>
            <span className="font-semibold text-slate-700">Shortage chance</span>{" "}
            {hasExpenseWarning ? "Unestimated (no expenses)" : hasForecastInputs ? probability(forecast.shortage_prob) : "—"}
          </span>
        </div>
      </section>
      <aside aria-label="Observation date accounting principle" className="mt-4 rounded-xl border border-slate-200 bg-slate-50/80 p-4 text-xs leading-relaxed text-slate-600">
        <div className="flex items-start gap-3">
          <CalendarDays size={18} className="mt-0.5 shrink-0 text-slate-500" />
          <div className="space-y-1">
            <h3 className="font-semibold text-slate-800">
              Observation Date Principle (<span className="font-mono text-slate-700">{business.as_of}</span>)
            </h3>
            <p className="text-slate-600">
              <strong>It does not automatically tick forward with your computer&apos;s clock:</strong> The application anchors to an Observation Date (<code className="rounded bg-slate-200/70 px-1 py-0.5 font-mono text-[11px] text-slate-800">as_of: {business.as_of}</code>).
              When tomorrow arrives, the app does not silently advance the date by 1 day and pretend bank debits happened.
              In financial accounting, bank balances must be reconciled against actual bank statements, not guessed by a timer.
            </p>
          </div>
        </div>
      </aside>
      <section className="mt-6">
        <div className="mb-4">
          <p className="eyebrow">WHAT’S DRIVING THE FORECAST</p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight">
            Why cash may get tight
          </h2>
        </div>
        {forecast.drivers.length ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {forecast.drivers.map((driver) => (
              <DriverCard key={`${driver.type}-${driver.ref}`} driver={driver} />
            ))}
          </div>
        ) : (
          <div className="panel-card p-5 text-sm text-slate-500">
            {!hasForecastInputs
              ? "No cash pressure points or late payments can be calculated until invoices or expense obligations are added."
              : "No significant cash pressure points or late payment drivers were identified."}
          </div>
        )}
      </section>
    </>
  );
}

function ForecastLegend() {
  return (
    <div className="flex flex-wrap items-center gap-3 text-[10px] font-medium text-slate-500 sm:gap-4 sm:text-xs">
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-sm bg-indigo-100 ring-1 ring-indigo-200" />
        P10–P90 range
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-[2px] w-4 rounded bg-indigo-600" />
        P50
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-4 border-t border-dashed border-rose-500" />
        Safety floor
      </span>
    </div>
  );
}

function ForecastChart({
  forecast,
  compact = false,
}: {
  forecast: Forecast;
  compact?: boolean;
}) {
  const data = useMemo(() => chartData(forecast), [forecast]);

  return (
    <div className={compact ? "h-[250px] sm:h-[290px]" : "h-[320px] sm:h-[410px]"}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid
            stroke="#eef0f4"
            strokeDasharray="3 5"
            vertical={false}
          />
          <XAxis
            dataKey="date"
            tickFormatter={shortDate}
            tickLine={false}
            axisLine={false}
            minTickGap={compact ? 42 : 32}
            tick={{ fill: "#94a3b8", fontSize: 10 }}
            dy={10}
          />
          <YAxis
            domain={[
              (dataMin: number) => {
                const floor = forecast.safety_floor ?? 0;
                const min = Math.min(Number.isFinite(dataMin) ? dataMin : floor, floor);
                return Math.floor(Math.max(0, min * 0.85));
              },
              (dataMax: number) => {
                const floor = forecast.safety_floor ?? 0;
                const max = Math.max(Number.isFinite(dataMax) ? dataMax : floor, floor, 1000);
                return Math.ceil(max * 1.15);
              },
            ]}
            tickFormatter={(value: number) =>
              compactInr.format(value).replace(/\s/g, "")
            }
            tickLine={false}
            axisLine={false}
            width={compact ? 58 : 70}
            tick={{ fill: "#94a3b8", fontSize: 10 }}
          />
          <Tooltip content={<ForecastTooltip />} />
          <Area
            dataKey="range"
            type="monotone"
            fill="#818cf8"
            fillOpacity={0.18}
            stroke="#818cf8"
            strokeOpacity={0.25}
            strokeWidth={1}
            isAnimationActive={false}
            name="P10–P90 range"
          />
          <ReferenceLine
            y={forecast.safety_floor}
            stroke="#e97474"
            strokeDasharray="6 5"
            strokeWidth={1.5}
            label={{
              value: "Safety floor",
              position: "insideTopRight",
              fill: "#c85c5c",
              fontSize: 10,
            }}
          />
          <Line
            dataKey="p50"
            type="monotone"
            stroke="#4f46e5"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4, fill: "#4f46e5", stroke: "#fff", strokeWidth: 2 }}
            name="P50"
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function ForecastTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { dataKey: string; value: number | [number, number]; payload?: Record<string, unknown> }[];
  label?: string;
}) {
  if (!active || !payload?.length || !label) return null;
  const point = payload[0]?.payload as { p10?: number; p50?: number; p90?: number } | undefined;
  const p10 = point?.p10 ?? 0;
  const p50 = point?.p50 ?? 0;
  const p90 = point?.p90 ?? 0;

  return (
    <div className="rounded-xl border border-slate-100 bg-white px-3.5 py-3 shadow-xl shadow-slate-900/10">
      <p className="mb-2 text-[11px] font-medium text-slate-400">
        {formatDate(label)}
      </p>
      <div className="flex items-center justify-between gap-6 py-0.5">
        <span className="text-xs text-slate-500">P90 (OPTIMISTIC)</span>
        <span className="text-xs font-semibold text-slate-800">{money(p90)}</span>
      </div>
      <div className="flex items-center justify-between gap-6 py-0.5">
        <span className="text-xs text-indigo-600 font-semibold">P50 (MEDIAN)</span>
        <span className="text-xs font-bold text-indigo-700">{money(p50)}</span>
      </div>
      <div className="flex items-center justify-between gap-6 py-0.5">
        <span className="text-xs text-slate-500">P10 (PESSIMISTIC)</span>
        <span className="text-xs font-semibold text-slate-800">{money(p10)}</span>
      </div>
    </div>
  );
}

function DriverCard({ driver }: { driver: ForecastDriver }) {
  const config: Record<
    ForecastDriver["type"],
    { label: string; icon: LucideIcon; color: string }
  > = {
    late_invoice: {
      label: "Late payment",
      icon: Clock3,
      color: "driver-amber",
    },
    obligation: {
      label: "Upcoming obligation",
      icon: CalendarDays,
      color: "driver-blue",
    },
    supplier_bill: {
      label: "Supplier bill",
      icon: FileText,
      color: "driver-purple",
    },
  };
  const item = config[driver.type];
  const Icon = item.icon;
  return (
    <article className="panel-card flex gap-3 p-4">
      <div
        className={`mt-0.5 grid size-9 shrink-0 place-items-center rounded-xl ${item.color}`}
      >
        <Icon size={17} />
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-slate-800">
            {item.label}
          </span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-400">
            {driver.ref}
          </span>
        </div>
        <p className="mt-1.5 text-xs leading-5 text-slate-500">{driver.text}</p>
      </div>
    </article>
  );
}

function ActionsPage({
  actions,
  shortageProbability,
  apiUrl,
  delayModel,
}: {
  actions: Action[];
  shortageProbability: number;
  apiUrl: string;
  delayModel: string;
}) {
  const [view, setView] = useState<'collections' | 'other'>('collections');
  const otherActions = actions.filter(action => action.type !== 'chase_invoice');
  return (
    <>
      <PageHeading
        eyebrow="SMALL STEPS, MORE RUNWAY"
        title="Recommended actions"
        description="Prioritized ways to help protect your cash position. Review the trade-offs before choosing what works for you."
        action={
          <span className="flex w-fit items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-500">
            <Sparkles size={14} className="text-emerald-700" />
            Sorted by impact
          </span>
        }
      />
      <nav className="section-tabs" aria-label="Corrective action types"><button aria-pressed={view === 'collections'} onClick={() => setView('collections')}>Prioritised collections</button><button aria-pressed={view === 'other'} onClick={() => setView('other')}>Other corrective actions</button></nav>
      {view === 'collections' ? <CollectionsPanel apiUrl={apiUrl} delayModel={delayModel} /> : <>
      <div className="mb-5 flex items-center gap-3 rounded-2xl border border-emerald-100 bg-emerald-50/70 p-4">
        <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-white text-emerald-700">
          <Gauge size={17} />
        </div>
        <p className="text-xs leading-5 text-slate-600">
          Current shortage probability is{" "}
          <span className="font-semibold text-slate-900">
            {probability(shortageProbability)}
          </span>
          . The actions below estimate probability if their assumptions hold.
          They do not establish that an action or reminder will succeed.
        </p>
      </div>
      {otherActions.length ? (
        <div className="grid gap-3 xl:grid-cols-2">
          {otherActions.map((action, index) => (
            <ActionCard
              action={action}
              before={shortageProbability}
              key={action.id}
              rank={index + 1}
            />
          ))}
        </div>
      ) : (
        <div className="panel-card p-8 text-center text-sm text-slate-500">
          No actions were returned by the API.
        </div>
      )}
      </>}
    </>
  );
}

function ActionCard({
  action,
  before,
  rank,
}: {
  action: Action;
  before: number;
  rank: number;
}) {
  return (
    <article
      className={`panel-card relative overflow-hidden p-5 sm:p-6 ${
        action.risk === "high" ? "border-rose-200" : ""
      }`}
    >
      {action.risk === "high" && (
        <span className="absolute right-0 top-0 rounded-bl-xl bg-rose-600 px-3 py-1.5 text-[10px] font-semibold text-white">
          <AlertTriangle className="mr-1 inline-block" size={12} />
          Review carefully
        </span>
      )}
      <div className="flex items-start gap-3 pr-2">
        <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-slate-50 text-xs font-bold text-slate-500">
          {String(rank).padStart(2, "0")}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-[15px] font-semibold leading-6 text-slate-900">
              {action.title}
            </h2>
            <RiskBadge risk={action.risk} />
          </div>
          <p className="mt-1.5 text-sm leading-6 text-slate-500">
            {action.note}
          </p>
        </div>
      </div>
      <div className="mt-5 grid grid-cols-2 gap-2 border-t border-slate-100 pt-4 sm:grid-cols-3">
        <div className="metric-cell">
          <span className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
            Action cost
          </span>
          <span className="mt-1 text-sm font-semibold text-slate-800">
            {money(action.cost)}
          </span>
        </div>
        <div className="metric-cell">
          <span className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
            Shortage chance
          </span>
          <span className="mt-1 text-sm font-semibold text-slate-800">
            {probability(before)}{" "}
            <ArrowDownRight className="mx-0.5 inline-block text-emerald-600" size={14} />
            {probability(action.shortage_prob_after)}
          </span>
        </div>
        <div className="metric-cell col-span-2 sm:col-span-1">
          <span className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
            Runway gained
          </span>
          <span className="mt-1 text-sm font-semibold text-emerald-700">
            +{action.runway_days_gained} days
          </span>
        </div>
      </div>
      {action.risk === "high" && (
        <div className="mt-4 flex gap-2 rounded-xl border border-rose-100 bg-rose-50/70 p-3 text-xs leading-5 text-rose-800">
          <AlertTriangle className="mt-0.5 shrink-0" size={15} />
          <span>
            Delaying an MSME payment may defer the buyer’s tax deduction under
            Section 43B(h). Confirm terms and the statutory due date before
            proceeding.
          </span>
        </div>
      )}
    </article>
  );
}

function RiskBadge({ risk }: { risk: Action["risk"] }) {
  const label = risk.charAt(0).toUpperCase() + risk.slice(1);
  return (
    <span className={`risk-badge risk-${risk}`}>
      {risk === "high" && <AlertTriangle size={11} />}
      {label} risk
    </span>
  );
}

function LoadingScreen() {
  return (
    <main className="grid min-h-screen place-items-center bg-[#f7f8fa] px-5">
      <div className="text-center">
        <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-[#4f46e5] text-white shadow-lg shadow-emerald-950/15">
          <LoaderCircle className="animate-spin" size={25} />
        </div>
        <p className="mt-4 text-sm font-medium text-slate-600">
          Loading your cash-flow picture…
        </p>
        <p className="mt-1 text-xs text-slate-400">Connecting to your business data</p>
      </div>
    </main>
  );
}

export default App;
