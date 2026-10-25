import { useEffect, useState, type FormEvent } from 'react';
import App from './App';
import { API_BASE, ApiError, apiRequest, setCsrfToken, type Account } from './api';
import DemoControl from './DemoControl';
import { Wallet, TrendingUp, FileText, ArrowLeftRight, Eye, EyeOff } from 'lucide-react';

export default function AuthGate() {
  const [account, setAccount] = useState<Account | null>(null);
  const [checking, setChecking] = useState(true);
  const [signup, setSignup] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [sessionError, setSessionError] = useState('');
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState('');
  const [asOf, setAsOf] = useState(() => {
    const parts = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
    return ['year', 'month', 'day'].map(type => parts.find(part => part.type === type)?.value).join('-');
  });
  const [cash, setCash] = useState('');
  const [floor, setFloor] = useState('');
  function accept(user: Account) { setCsrfToken(user.csrf_token); setAccount(user); }
  useEffect(() => {
    let active = true;
    function expired() { setAccount(null); setCsrfToken(''); }
    window.addEventListener('cashflow-session-expired', expired);
    apiRequest<Account>(`${API_BASE}/auth/me`).then(user => { if (active) accept(user); })
      .catch(e => {
        if (active && !(e instanceof ApiError && e.status === 401)) {
          setSessionError('Unable to reach your workspace right now. You can still sign in, but your account service may be unavailable.');
        }
      })
      .finally(() => { if (active) setChecking(false); });
    return () => { active = false; window.removeEventListener('cashflow-session-expired', expired); };
  }, []);
  async function authenticate(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setSessionError('');
    try {
      accept(await apiRequest<Account>(`${API_BASE}/auth/${signup ? 'signup' : 'login'}`, { email, password }));
      setPassword('');
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not sign in'); }
    finally { setBusy(false); }
  }
  async function setup(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      await apiRequest(`${API_BASE}/onboarding`, { name, as_of: asOf, opening_cash: Number(cash), safety_floor: Number(floor) });
      accept(await apiRequest<Account>(`${API_BASE}/auth/me`));
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save your business'); }
    finally { setBusy(false); }
  }
  async function signout() {
    setError('');
    try { await apiRequest(`${API_BASE}/auth/logout`, {}); setAccount(null); setCsrfToken(''); }
    catch (e) { setError(e instanceof Error ? e.message : 'Sign out failed'); throw e; }
  }
  if (checking) return <main className="grid min-h-screen place-items-center bg-[#f6f8f5]">Checking your session…</main>;
  if (account && !account.onboarding_required) return <App key={account.business_id} account={account} onSignout={signout} />;
  return <main className="auth-shell">
      <section className="auth-intro">
        <div className="auth-wordmark"><span className="brand-symbol"><Wallet size={18} /></span>cashflow<span className="text-indigo-600">.</span></div>
        <div className="auth-message">
          <p className="eyebrow mb-4">FINANCIAL CLARITY FOR YOUR BUSINESS</p>
          <h1>A clearer view of the cash ahead.</h1>
          <p>One workspace to understand your position, plan for uncertainty, and decide your next move.</p>
          <div className="mt-8 border-t border-slate-200 pt-1">
            <div className="auth-feature"><TrendingUp size={18} /><div><strong>Look ahead with confidence</strong><p>Explore a 90-day cash forecast with a range of possible outcomes.</p></div></div>
            <div className="auth-feature"><FileText size={18} /><div><strong>Know what has actually arrived</strong><p>Keep outstanding invoices separate from received payments.</p></div></div>
            <div className="auth-feature"><ArrowLeftRight size={18} /><div><strong>Compare your next steps</strong><p>Test scenarios and understand the financial effect of each action.</p></div></div>
          </div>
        </div>
        <footer className="text-[11px] text-slate-500">CashFlow · Business finance workspace</footer>
      </section>
      <div className="auth-form-shell"><section className="auth-form-panel">
        <p className="eyebrow mb-3">{account ? 'BUSINESS SETUP' : signup ? 'GET STARTED' : 'YOUR WORKSPACE'}</p>
        <h2 className="text-2xl font-semibold">{account ? 'Set up your business' : signup ? 'Create your account' : 'Welcome back'}</h2>
        <p className="mt-2 text-sm text-slate-500">{account ? 'Start with your actual cash position. You can import invoices and add obligations next.' : 'Your business records are kept in a separate workspace.'}</p>
        {error && <p role="alert" className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
        {sessionError && <p role="alert" className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-5 text-amber-900">{sessionError}</p>}
        {account && <DemoControl onLoaded={async () => accept(await apiRequest<Account>(`${API_BASE}/auth/me`))} />}
        {account ? <form onSubmit={setup} className="mt-6 space-y-4">
          <label className="block text-sm">Business name<input className="field-input mt-1" required maxLength={120} value={name} onChange={e => setName(e.target.value)} /></label>
          <div>
            <label className="block text-sm">Observation date<input className="field-input mt-1" type="date" required value={asOf} onChange={e => setAsOf(e.target.value)} /></label>
            <p className="mt-1 text-[11px] leading-normal text-slate-500">
              Anchors your initial financial snapshot (as_of). The app does not silently tick forward with your computer clock; accounting balances advance only when reconciled against actual bank statements.
            </p>
          </div>
          <label className="block text-sm">Cash available now (INR)<input className="field-input mt-1" type="number" min="0" step="1" required value={cash} onChange={e => setCash(e.target.value)} /></label>
          <label className="block text-sm">Minimum cash buffer (INR)<input className="field-input mt-1" type="number" min="0" step="1" required value={floor} onChange={e => setFloor(e.target.value)} /></label>
          <p className="text-xs leading-5 text-slate-500">Include receipts already in your bank balance. Expected invoice payments are added separately. Your workspace starts empty, without synthetic data.</p>
          <button disabled={busy} className="button-primary w-full">{busy ? 'Saving…' : 'Open my workspace'}</button>
          <button className="button-secondary w-full" type="button" disabled={busy} onClick={() => { void signout().catch(() => {}); }}>Sign out</button>
        </form> : <form onSubmit={authenticate} className="mt-6 space-y-4">
          <label className="block text-sm">Email address<input className="field-input mt-1" type="email" autoComplete="username" required maxLength={254} value={email} onChange={e => setEmail(e.target.value)} /></label>
          <label className="block text-sm">Password<div className="relative"><input className="field-input mt-1 !pr-11" type={showPassword ? 'text' : 'password'} autoComplete={signup ? 'new-password' : 'current-password'} required minLength={signup ? 5 : 1} maxLength={signup ? 10 : 128} pattern={signup ? '(?=.*[^A-Za-z0-9]).{5,10}' : undefined} title={signup ? 'Use 5–10 characters and include at least one special character.' : undefined} value={password} onChange={e => setPassword(e.target.value)} /><button type="button" className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div></label>
          <p className="text-xs text-slate-500">{signup ? 'Use 5–10 characters, including at least one special character (for example, Cash!7).' : 'Enter your account password. Existing accounts remain supported.'}</p>
          <button disabled={busy} className="button-primary w-full">{busy ? 'Please wait…' : signup ? 'Create account' : 'Sign in'}</button>
          <button type="button" disabled={busy} className="auth-toggle" onClick={() => { setSignup(!signup); setError(''); }}>{signup ? 'Already have an account? ' : 'New to CashFlow? '}<span>{signup ? 'Sign in' : 'Create an account'}</span></button>
        </form>}
      </section></div>
  </main>;
}
