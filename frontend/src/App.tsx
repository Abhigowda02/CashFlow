import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Banknote,
  CalendarDays,
  Check,
  ChevronDown,
  Clock3,
  Factory,
  FileText,
  Gauge,
  LayoutDashboard,
  LoaderCircle,
  Play,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import {
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const API_URL = (
  import.meta.env.VITE_API_URL ?? "http://localhost:8000/api"
).replace(/\/+$/, "");

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
};

type Business = {
  name: string;
  as_of: string;
  opening_cash: number;
  safety_floor: number;
  customers: Customer[];
  invoices: Invoice[];
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

type ScenarioChange =
  | { type: "delay_customer"; customer_id: string; extra_days: number }
  | { type: "sales_change"; pct: number }
  | { type: "extra_expense"; amount: number; date: string }
  | { type: "supplier_terms"; extra_days: number };

type ScenarioForecast = {
  baseline: Forecast;
  scenario: Forecast;
};

type TabId = "dashboard" | "forecast" | "simulator" | "actions";

const tabs: { id: TabId; label: string; icon: LucideIcon }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "forecast", label: "Forecast", icon: TrendingDown },
  { id: "simulator", label: "Simulator", icon: Sparkles },
  { id: "actions", label: "Actions", icon: Check },
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
  const response = await fetch(`${API_URL}${path}`, { signal });
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}) for ${path}`);
  }
  return (await response.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(
      `Request failed (${response.status}) for ${path}${detail ? `: ${detail}` : ""}`,
    );
  }
  return (await response.json()) as T;
}

function chartData(forecast: Forecast) {
  return forecast.dates.map((date, index) => ({
    date,
    p10: forecast.p10[index] ?? 0,
    p50: forecast.p50[index] ?? 0,
    p90: forecast.p90[index] ?? 0,
  }));
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

function App() {
  const [activeTab, setActiveTab] = useState<TabId>("dashboard");
  const [business, setBusiness] = useState<Business | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [actions, setActions] = useState<Action[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedCustomer, setSelectedCustomer] = useState("");
  const [customerDelay, setCustomerDelay] = useState(30);
  const [salesChange, setSalesChange] = useState(-15);
  const [expenseAmount, setExpenseAmount] = useState(150000);
  const [expenseDate, setExpenseDate] = useState("");
  const [supplierDelay, setSupplierDelay] = useState(15);
  const [scenarioResult, setScenarioResult] =
    useState<ScenarioForecast | null>(null);
  const [scenarioLoading, setScenarioLoading] = useState(false);
  const [scenarioError, setScenarioError] = useState<string | null>(null);

  const loadData = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setLoadError(null);
    try {
      const [businessData, forecastData, actionsData] = await Promise.all([
        getJson<Business>("/business", signal),
        getJson<Forecast>("/forecast", signal),
        getJson<Action[]>("/actions", signal),
      ]);
      setBusiness(businessData);
      setForecast(forecastData);
      setActions(actionsData);
      setSelectedCustomer((current) =>
        businessData.customers.some((customer) => customer.id === current)
          ? current
          : (businessData.customers[0]?.id ?? ""),
      );
      setExpenseDate((current) => current || businessData.as_of);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setLoadError(displayError(error));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

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
      .reduce((total, invoice) => total + invoice.amount, 0);
  }, [business]);

  const runwayDays = useMemo(() => {
    if (!business || !forecast) return null;
    const firstBelowFloor = forecast.p50.findIndex(
      (balance) => balance < forecast.safety_floor,
    );
    if (firstBelowFloor < 0) return null;
    const firstDate = forecast.dates[firstBelowFloor];
    return firstDate ? dayDifference(business.as_of, firstDate) : null;
  }, [business, forecast]);

  const runScenario = async () => {
    if (!business) return;
    const changes: ScenarioChange[] = [];
    if (selectedCustomer && customerDelay > 0) {
      changes.push({
        type: "delay_customer",
        customer_id: selectedCustomer,
        extra_days: customerDelay,
      });
    }
    if (salesChange !== 0) {
      changes.push({ type: "sales_change", pct: salesChange });
    }
    if (expenseAmount > 0 && expenseDate) {
      changes.push({
        type: "extra_expense",
        amount: expenseAmount,
        date: expenseDate,
      });
    }
    if (supplierDelay > 0) {
      changes.push({ type: "supplier_terms", extra_days: supplierDelay });
    }

    setScenarioLoading(true);
    setScenarioError(null);
    try {
      const result = await postJson<ScenarioForecast>("/scenario", {
        name: "Custom cash-flow scenario",
        changes,
      });
      setScenarioResult(result);
    } catch (error) {
      setScenarioError(displayError(error));
    } finally {
      setScenarioLoading(false);
    }
  };

  if (loading) return <LoadingScreen />;

  if (loadError || !business || !forecast) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#f6f8f5] px-5">
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

  const tone = shortageTone(forecast.shortage_prob);
  const firstShortage =
    forecast.dates.find(
      (_, index) => forecast.p50[index] < forecast.safety_floor,
    ) ?? null;

  return (
    <div className="min-h-screen bg-[#f6f8f5] text-slate-900">
      <div className="mx-auto flex min-h-screen max-w-[1600px]">
        <aside className="sidebar-shell hidden w-[252px] shrink-0 flex-col border-r border-slate-200/70 bg-white/80 px-5 py-6 lg:flex">
          <Brand />
          <div className="mt-12">
            <p className="nav-caption">WORKSPACE</p>
            <nav className="mt-3 space-y-1.5">
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
          <div className="mt-auto rounded-2xl border border-emerald-100 bg-emerald-50/70 p-4">
            <div className="flex size-9 items-center justify-center rounded-xl bg-white text-emerald-700 shadow-sm">
              <ShieldAlert size={18} />
            </div>
            <p className="mt-3 text-sm font-semibold text-slate-800">
              Keep a steady eye
            </p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              A little visibility today can prevent a cash crunch tomorrow.
            </p>
          </div>
          <div className="mt-5 flex items-center gap-3 border-t border-slate-100 pt-5">
            <div className="grid size-9 place-items-center rounded-full bg-[#e6ede4] text-xs font-bold text-emerald-900">
              NS
            </div>
            <div className="min-w-0">
              <p className="truncate text-xs font-semibold text-slate-800">
                {business.name}
              </p>
              <p className="mt-0.5 text-[11px] text-slate-400">Bengaluru, IN</p>
            </div>
          </div>
        </aside>

        <main className="min-w-0 flex-1 px-4 pb-10 pt-5 sm:px-7 lg:px-10 lg:pt-8">
          <header className="mb-7 flex items-center justify-between gap-3">
            <div className="lg:hidden">
              <Brand />
            </div>
            <div className="hidden lg:block">
              <p className="text-xs font-medium text-slate-400">
                {new Intl.DateTimeFormat("en-IN", {
                  weekday: "long",
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                }).format(new Date(`${business.as_of}T12:00:00`))}
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-700">
                Good morning, Namma Stitch
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="hidden rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-[11px] font-semibold text-emerald-800 sm:inline-flex">
                <span className="mr-2 mt-1 size-1.5 rounded-full bg-emerald-500" />
                Live forecast
              </span>
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

          <div className="mb-6 flex gap-2 overflow-x-auto pb-1 lg:hidden">
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
          </div>

          {activeTab === "dashboard" && (
            <Dashboard
              business={business}
              forecast={forecast}
              overdueReceivables={overdueReceivables}
              runwayDays={runwayDays}
              firstShortage={firstShortage}
              tone={tone}
              onNavigate={setActiveTab}
            />
          )}
          {activeTab === "forecast" && <ForecastPage forecast={forecast} />}
          {activeTab === "simulator" && (
            <SimulatorPage
              business={business}
              forecast={forecast}
              selectedCustomer={selectedCustomer}
              setSelectedCustomer={setSelectedCustomer}
              customerDelay={customerDelay}
              setCustomerDelay={setCustomerDelay}
              salesChange={salesChange}
              setSalesChange={setSalesChange}
              expenseAmount={expenseAmount}
              setExpenseAmount={setExpenseAmount}
              expenseDate={expenseDate}
              setExpenseDate={setExpenseDate}
              supplierDelay={supplierDelay}
              setSupplierDelay={setSupplierDelay}
              result={scenarioResult}
              loading={scenarioLoading}
              error={scenarioError}
              onRun={() => void runScenario()}
            />
          )}
          {activeTab === "actions" && (
            <ActionsPage
              actions={actions}
              shortageProbability={forecast.shortage_prob}
            />
          )}

          <footer className="mt-10 flex flex-col items-center justify-between gap-2 border-t border-slate-200/70 pt-5 text-[11px] text-slate-400 sm:flex-row">
            <span>Demo uses synthetic data</span>
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
      <div className="grid size-10 place-items-center rounded-[14px] bg-[#163b2e] text-white shadow-md shadow-emerald-950/15">
        <Factory size={21} strokeWidth={1.8} />
      </div>
      <div>
        <p className="text-[17px] font-bold tracking-tight text-slate-900">
          cashflow<span className="text-emerald-700">.</span>
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
        <h1 className="mt-2 text-[27px] font-semibold tracking-[-0.04em] text-slate-900 sm:text-[32px]">
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
  onNavigate,
}: {
  business: Business;
  forecast: Forecast;
  overdueReceivables: number;
  runwayDays: number | null;
  firstShortage: string | null;
  tone: "danger" | "warning" | "success";
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
      label: "Opening cash",
      value: money(business.opening_cash),
      subtext: "Available at start of forecast",
      icon: Wallet,
      accent: "green",
    },
    {
      label: "Cash runway",
      value: runwayDays === null ? "90+" : `${runwayDays} days`,
      subtext:
        runwayDays === null
          ? "Above safety floor for 90 days"
          : `Safety floor crossed ${formatDate(firstShortage)}`,
      icon: Gauge,
      accent: "blue",
      trend: runwayDays === null ? "up" : "down",
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
      value: probability(forecast.shortage_prob),
      subtext: "Chance of falling below your safety floor",
      icon: AlertTriangle,
      accent: "purple",
    },
  ];

  return (
    <>
      <PageHeading
        eyebrow="YOUR CASH AT A GLANCE"
        title="Good morning, Namma Stitch"
        description="Here’s what your cash flow is telling you today."
        action={
          <div className="flex w-fit items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 shadow-sm">
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
            {forecast.shortage_prob >= 0.5
              ? `Cash shortage likely around ${firstShortage ? shortDate(firstShortage) : "the forecast period"} (${probability(forecast.shortage_prob)} probability)`
              : forecast.shortage_prob >= 0.2
                ? `Cash flow needs attention — ${probability(forecast.shortage_prob)} chance of falling below your safety floor`
                : `Looking steady — just ${probability(forecast.shortage_prob)} chance of a cash shortage`}
          </p>
          <p className="mt-0.5 text-xs text-white/75">
            {forecast.shortage_prob >= 0.5
              ? "Take a look at your forecast and consider an action."
              : "Your 90-day forecast is based on expected receipts and upcoming obligations."}
          </p>
        </div>
        <button
          className="hidden items-center gap-1.5 rounded-xl bg-white/15 px-3 py-2 text-xs font-semibold text-white transition hover:bg-white/25 sm:flex"
          onClick={() => onNavigate("forecast")}
        >
          View forecast <ArrowUpRight size={14} />
        </button>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <KpiCard key={card.label} {...card} />
        ))}
      </div>

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
        <ForecastChart forecast={forecast} compact />
      </section>

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
              <p className="eyebrow">YOUR NEXT BEST MOVE</p>
              <h2 className="mt-1 text-lg font-semibold tracking-tight">
                Start with collections
              </h2>
            </div>
            <div className="grid size-9 place-items-center rounded-xl bg-emerald-50 text-emerald-700">
              <Banknote size={18} />
            </div>
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-500">
            Following up on overdue invoices can help close the gap before
            upcoming payroll and supplier payments.
          </p>
          <button
            className="button-primary mt-5 w-full sm:w-auto"
            onClick={() => onNavigate("actions")}
          >
            View recommended actions <ArrowUpRight size={16} />
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
              {money(invoice.amount)}
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

function ForecastPage({ forecast }: { forecast: Forecast }) {
  return (
    <>
      <PageHeading
        eyebrow="PLAN WITH MORE CONFIDENCE"
        title="Cash forecast"
        description="A 90-day view of your expected balance, with a range of outcomes and the safety floor to watch."
        action={
          <span className="flex w-fit items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-500">
            <span className="size-2 rounded-full bg-emerald-500" />
            90-day outlook
          </span>
        }
      />
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
            {probability(forecast.shortage_prob)}
          </span>
        </div>
      </section>
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
            No forecast drivers were returned by the API.
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
        <span className="size-2.5 rounded-sm bg-emerald-100 ring-1 ring-emerald-200" />
        P10–P90 range
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-[2px] w-4 rounded bg-emerald-700" />
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
        <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid
            stroke="#e9eeea"
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
            tickFormatter={(value: number) =>
              compactInr.format(value).replace(/\s/g, "")
            }
            tickLine={false}
            axisLine={false}
            width={compact ? 58 : 70}
            tick={{ fill: "#94a3b8", fontSize: 10 }}
          />
          <Tooltip content={<ForecastTooltip />} />
          {data.slice(0, -1).map((point, index) => {
            const nextPoint = data[index + 1];
            return nextPoint ? (
              <ReferenceArea
                key={point.date}
                x1={point.date}
                x2={nextPoint.date}
                y1={point.p10}
                y2={point.p90}
                fill="#34a779"
                fillOpacity={0.13}
                stroke="none"
                ifOverflow="hidden"
              />
            ) : null;
          })}
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
            stroke="#16754f"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4, fill: "#16754f", stroke: "#fff", strokeWidth: 2 }}
            name="P50"
            isAnimationActive={false}
          />
        </AreaChart>
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
  payload?: { dataKey: string; value: number }[];
  label?: string;
}) {
  if (!active || !payload?.length || !label) return null;
  const values = new Map(payload.map((item) => [item.dataKey, item.value]));
  return (
    <div className="rounded-xl border border-slate-100 bg-white px-3.5 py-3 shadow-xl shadow-slate-900/10">
      <p className="mb-2 text-[11px] font-medium text-slate-400">
        {formatDate(label)}
      </p>
      {["p10", "p50", "p90"].map((key) => {
        const value = values.get(key);
        if (value === undefined) return null;
        return (
          <div className="flex items-center justify-between gap-6 py-0.5" key={key}>
            <span className="text-xs text-slate-500">{key.toUpperCase()}</span>
            <span className="text-xs font-semibold text-slate-800">
              {money(value)}
            </span>
          </div>
        );
      })}
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

function SimulatorPage({
  business,
  forecast,
  selectedCustomer,
  setSelectedCustomer,
  customerDelay,
  setCustomerDelay,
  salesChange,
  setSalesChange,
  expenseAmount,
  setExpenseAmount,
  expenseDate,
  setExpenseDate,
  supplierDelay,
  setSupplierDelay,
  result,
  loading,
  error,
  onRun,
}: {
  business: Business;
  forecast: Forecast;
  selectedCustomer: string;
  setSelectedCustomer: (value: string) => void;
  customerDelay: number;
  setCustomerDelay: (value: number) => void;
  salesChange: number;
  setSalesChange: (value: number) => void;
  expenseAmount: number;
  setExpenseAmount: (value: number) => void;
  expenseDate: string;
  setExpenseDate: (value: string) => void;
  supplierDelay: number;
  setSupplierDelay: (value: number) => void;
  result: ScenarioForecast | null;
  loading: boolean;
  error: string | null;
  onRun: () => void;
}) {
  const selectedName =
    business.customers.find((customer) => customer.id === selectedCustomer)
      ?.name ?? "Customer";
  const comparison = result
    ? result.baseline.dates.map((date, index) => ({
        date,
        baseline: result.baseline.p50[index] ?? 0,
        scenario: result.scenario.p50[index] ?? 0,
      }))
    : [];

  return (
    <>
      <PageHeading
        eyebrow="TRY A WHAT-IF"
        title="Cash-flow simulator"
        description="Explore how a late payment, a change in sales, or a surprise bill could affect your cash."
      />
      <div className="grid items-start gap-5 xl:grid-cols-[0.88fr_1.12fr]">
        <section className="panel-card p-5 sm:p-6">
          <div className="mb-5 flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-emerald-50 text-emerald-700">
              <Sparkles size={19} />
            </div>
            <div>
              <h2 className="text-base font-semibold">Scenario inputs</h2>
              <p className="mt-0.5 text-xs text-slate-400">
                Adjust the details to see what changes
              </p>
            </div>
          </div>

          <div className="space-y-5">
            <div className="scenario-field">
              <div className="flex items-center justify-between gap-3">
                <label className="field-label" htmlFor="customer">
                  Customer pays later
                </label>
                <span className="field-value">{customerDelay} days</span>
              </div>
              <div className="relative mt-2">
                <select
                  className="field-input appearance-none pr-9"
                  id="customer"
                  value={selectedCustomer}
                  onChange={(event) => setSelectedCustomer(event.target.value)}
                >
                  {business.customers.map((customer) => (
                    <option key={customer.id} value={customer.id}>
                      {customer.name} · {customer.segment}
                    </option>
                  ))}
                </select>
                <ChevronDown
                  className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
                  size={15}
                />
              </div>
              <RangeControl
                label="Extra delay"
                min={0}
                max={60}
                value={customerDelay}
                unit="days"
                onChange={setCustomerDelay}
              />
            </div>

            <div className="scenario-field">
              <div className="flex items-center justify-between gap-3">
                <label className="field-label" htmlFor="sales-change">
                  Sales change
                </label>
                <span className="field-value">
                  {salesChange > 0 ? "+" : ""}
                  {salesChange}%
                </span>
              </div>
              <RangeControl
                id="sales-change"
                label="Monthly sales"
                min={-40}
                max={20}
                value={salesChange}
                unit="%"
                onChange={setSalesChange}
              />
            </div>

            <div className="scenario-field">
              <div className="flex items-center justify-between gap-3">
                <label className="field-label" htmlFor="expense-amount">
                  Add an unexpected expense
                </label>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <div className="relative">
                  <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-400">
                    ₹
                  </span>
                  <input
                    className="field-input pl-7"
                    id="expense-amount"
                    min={0}
                    step={10000}
                    type="number"
                    value={expenseAmount}
                    onChange={(event) =>
                      setExpenseAmount(
                        Math.max(0, Number(event.target.value) || 0),
                      )
                    }
                  />
                </div>
                <input
                  className="field-input"
                  aria-label="Extra expense date"
                  type="date"
                  value={expenseDate}
                  min={business.as_of}
                  onChange={(event) => setExpenseDate(event.target.value)}
                />
              </div>
            </div>

            <div className="scenario-field">
              <div className="flex items-center justify-between gap-3">
                <label className="field-label" htmlFor="supplier-delay">
                  Extend supplier terms
                </label>
                <span className="field-value">{supplierDelay} days</span>
              </div>
              <RangeControl
                id="supplier-delay"
                label="Extra time"
                min={0}
                max={30}
                value={supplierDelay}
                unit="days"
                onChange={setSupplierDelay}
              />
            </div>
          </div>

          {error && (
            <div className="mt-5 flex gap-2 rounded-xl border border-rose-100 bg-rose-50 p-3 text-xs leading-5 text-rose-700">
              <AlertCircle className="mt-0.5 shrink-0" size={15} />
              <span>{error}</span>
            </div>
          )}
          <button
            className="button-primary mt-6 w-full"
            disabled={loading}
            onClick={onRun}
          >
            {loading ? (
              <LoaderCircle className="animate-spin" size={17} />
            ) : (
              <Play size={16} fill="currentColor" />
            )}
            {loading ? "Running scenario…" : "Run scenario"}
          </button>
        </section>

        <div className="space-y-5">
          {result ? (
            <>
              <section className="panel-card p-4 sm:p-6">
                <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="eyebrow">YOUR CUSTOM SCENARIO</p>
                    <h2 className="mt-1 text-lg font-semibold tracking-tight">
                      Baseline vs. what-if
                    </h2>
                  </div>
                  <div className="flex flex-wrap gap-3 text-[11px] font-medium text-slate-500">
                    <span className="flex items-center gap-1.5">
                      <span className="h-[2px] w-4 bg-slate-400" />
                      Baseline
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="h-[2px] w-4 bg-emerald-600" />
                      Scenario
                    </span>
                  </div>
                </div>
                <ScenarioChart data={comparison} floor={forecast.safety_floor} />
              </section>
              <div className="grid gap-3 sm:grid-cols-2">
                <ScenarioComparisonCard
                  label="Baseline shortage chance"
                  probabilityValue={result.baseline.shortage_prob}
                  date={result.baseline.first_shortage_date}
                  tone="slate"
                />
                <ScenarioComparisonCard
                  label="Scenario shortage chance"
                  probabilityValue={result.scenario.shortage_prob}
                  date={result.scenario.first_shortage_date}
                  tone={shortageTone(result.scenario.shortage_prob)}
                  change={result.scenario.shortage_prob - result.baseline.shortage_prob}
                />
              </div>
            </>
          ) : (
            <div className="panel-card flex min-h-[420px] flex-col items-center justify-center px-8 py-12 text-center sm:min-h-[540px]">
              <div className="grid size-14 place-items-center rounded-2xl bg-emerald-50 text-emerald-700">
                <Sparkles size={24} />
              </div>
              <h2 className="mt-5 text-lg font-semibold text-slate-800">
                See the impact before it happens
              </h2>
              <p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">
                Try a what-if with {selectedName}, adjust sales or add an
                expense. Your baseline forecast will stay here for comparison.
              </p>
              <div className="mt-6 flex items-center gap-2 rounded-full bg-slate-50 px-3 py-2 text-xs text-slate-500">
                <Gauge size={15} />
                Current shortage chance{" "}
                <span className="font-semibold text-slate-800">
                  {probability(forecast.shortage_prob)}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function RangeControl({
  id,
  label,
  min,
  max,
  value,
  unit,
  onChange,
}: {
  id?: string;
  label: string;
  min: number;
  max: number;
  value: number;
  unit: string;
  onChange: (value: number) => void;
}) {
  return (
    <div className="mt-3">
      <div className="flex justify-between text-[10px] text-slate-400">
        <label htmlFor={id} className="sr-only">
          {label}
        </label>
        <span>{min}{unit === "%" ? "%" : ` ${unit}`}</span>
        <span>{max}{unit === "%" ? "%" : ` ${unit}`}</span>
      </div>
      <input
        className="range-control mt-1.5 w-full"
        id={id}
        max={max}
        min={min}
        type="range"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </div>
  );
}

function ScenarioChart({
  data,
  floor,
}: {
  data: { date: string; baseline: number; scenario: number }[];
  floor: number;
}) {
  return (
    <div className="h-[300px] sm:h-[360px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid
            stroke="#e9eeea"
            strokeDasharray="3 5"
            vertical={false}
          />
          <XAxis
            dataKey="date"
            tickFormatter={shortDate}
            tickLine={false}
            axisLine={false}
            minTickGap={32}
            tick={{ fill: "#94a3b8", fontSize: 10 }}
            dy={9}
          />
          <YAxis
            tickFormatter={(value: number) =>
              compactInr.format(value).replace(/\s/g, "")
            }
            tickLine={false}
            axisLine={false}
            width={65}
            tick={{ fill: "#94a3b8", fontSize: 10 }}
          />
          <Tooltip content={<ScenarioTooltip />} />
          <ReferenceLine
            y={floor}
            stroke="#e97474"
            strokeDasharray="6 5"
            strokeWidth={1.4}
          />
          <Line
            dataKey="baseline"
            name="Baseline"
            type="monotone"
            stroke="#94a3b8"
            strokeDasharray="5 5"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: "#94a3b8", stroke: "#fff", strokeWidth: 2 }}
            isAnimationActive={false}
          />
          <Line
            dataKey="scenario"
            name="Scenario"
            type="monotone"
            stroke="#168157"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4, fill: "#168157", stroke: "#fff", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function ScenarioTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { dataKey: string; value: number }[];
  label?: string;
}) {
  if (!active || !payload?.length || !label) return null;
  return (
    <div className="rounded-xl border border-slate-100 bg-white px-3.5 py-3 shadow-xl shadow-slate-900/10">
      <p className="mb-2 text-[11px] font-medium text-slate-400">
        {formatDate(label)}
      </p>
      {payload.map((item) => (
        <div
          className="flex items-center justify-between gap-6 py-0.5"
          key={item.dataKey}
        >
          <span className="text-xs capitalize text-slate-500">
            {item.dataKey}
          </span>
          <span className="text-xs font-semibold text-slate-800">
            {money(item.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

function ScenarioComparisonCard({
  label,
  probabilityValue,
  date,
  tone,
  change,
}: {
  label: string;
  probabilityValue: number;
  date: string | null;
  tone: string;
  change?: number;
}) {
  return (
    <div className={`comparison-card comparison-${tone} p-4 sm:p-5`}>
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <div className="mt-2 flex items-end justify-between gap-2">
        <p className="text-2xl font-semibold tracking-tight text-slate-900">
          {probability(probabilityValue)}
        </p>
        {change !== undefined && change !== 0 && (
          <span
            className={`mb-1 text-xs font-semibold ${
              change > 0 ? "text-rose-600" : "text-emerald-700"
            }`}
          >
            {change > 0 ? "+" : ""}
            {Math.round(change * 100)} pts
          </span>
        )}
      </div>
      <p className="mt-1 text-[11px] text-slate-400">
        First below-floor day: {formatDate(date)}
      </p>
    </div>
  );
}

function ActionsPage({
  actions,
  shortageProbability,
}: {
  actions: Action[];
  shortageProbability: number;
}) {
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
      <div className="mb-5 flex items-center gap-3 rounded-2xl border border-emerald-100 bg-emerald-50/70 p-4">
        <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-white text-emerald-700">
          <Gauge size={17} />
        </div>
        <p className="text-xs leading-5 text-slate-600">
          Current shortage probability is{" "}
          <span className="font-semibold text-slate-900">
            {probability(shortageProbability)}
          </span>
          . The actions below show their estimated probability after taking
          action.
        </p>
      </div>
      {actions.length ? (
        <div className="grid gap-3 xl:grid-cols-2">
          {actions.map((action, index) => (
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
    <main className="grid min-h-screen place-items-center bg-[#f6f8f5] px-5">
      <div className="text-center">
        <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-[#163b2e] text-white shadow-lg shadow-emerald-950/15">
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
