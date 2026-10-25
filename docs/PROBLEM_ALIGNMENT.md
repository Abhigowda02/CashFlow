# Problem-statement alignment

The supplied BUSINESS FINANCE FORECASTING statement requires current liquidity,
uncertain future cash flows, scenario comparison, and financially quantified
corrective actions. It does not explicitly require subscriptions, bank links,
WhatsApp, vernacular support, statutory calendars, or an optimiser. Those are
product extensions. A multi-business SaaS is the selected delivery model.

| Required capability | Current implementation | Gap or limit |
| Current liquidity and cash reserves | Entered available cash, safety floor, receipt recording, aging and concentration anchored to an Observation Date (`as_of`) | Cash does not silently auto-advance with system clock; bank balances must be reconciled against actual statements rather than guessed by a timer. Projected runway is time until median balance crosses the floor |
| Expected revenue and outstanding receivables | Invoice import, outstanding balances, future sales assumptions | Template import only; no automatic Tally or bank mapping |
| Expected versus received | Partial/full receipt tracking; receipt increases cash once; outstanding portion alone enters forecasts | Owners must avoid recording receipts already included in entered cash |
| Supplier obligations | Editable supplier bills and forecasted due-date outflows | Actual supplier debit reconciliation is pending |
| Payroll, loan instalments, operating expenses | Editable named monthly obligations | User-entered schedules; no automatic recognition or statutory-date verification |
| Consolidated expense visibility | Expenses dashboard with categories, monthly recurring totals, due-date schedule and overdue supplier totals, sharing forecast recurrence logic | Scheduled commitments; actual bank-spending reconciliation and recurring settlement state remain pending |
| Payment schedules | Invoice due dates, supplier due dates and monthly obligation dates | Revised invoice instalment schedules remain pending |
| Uncertain payment timing and activity | 500 Monte Carlo paths, customer/segment historical delays, selectable survival model, sales variability | No explicit seasonal model; future-sales delays remain empirical |
| Customer payment understanding | Per-customer observed delay/variability, business-specific survival fits and conditional invoice probability dates | Minimum-history gate; probability accuracy is not yet validated on each business |
| Identify shortages | 90-day P10/P50/P90, shortage probability, date and safety floor | Forecasts are assumption-dependent, with no proven real-business accuracy claim |
| Delayed customer payments | Simulator customer-delay control | No saved scenario library |
| Unexpected expenses | Simulator amount and date | Same saved-scenario gap |
| Reduced sales | Simulator percentage change | Not seasonality-aware |
| Changed supplier terms | Simulator payment extension | Basic supplier risk flags, not a compliance engine |
| Revised payment schedules | Not implemented | Required remaining functional work |
| Compare responses financially | Each action is simulated and ranked with cost, risk, shortage chance and runway gained | Individual actions only; a cheapest-combination optimiser is optional, not explicitly required |
| Customer collection prioritisation | Paired cash-impact ranking across overdue customers, with owner-provided relationship and service/dispute guidance | What-if acceleration only; no learned outreach effectiveness, message sending, or future customer-value valuation |

Assessment: the forecasting core substantially matches the expected outcome,
but full completion requires revised schedules and representative real-business
validation. SaaS accounts do not substitute for those financial requirements.

## SaaS MVP foundation

Real email/password signup and login, revocable sessions, onboarding and one
isolated business per owner are implemented. All finance API routes require
authentication. Business identity comes from the server-side session, never a
client-selected tenant ID. Receipt keys are unique within a business. New accounts
start empty and never inherit another account's records or the legacy local demo.

SQLite is the development database; the SQLAlchemy schema supports PostgreSQL
through `DATABASE_URL`. PostgreSQL deployment has not been exercised against a
live server here. Public rollout still needs verified hosting, database backups,
schema migration procedures, email verification/password recovery, operational
monitoring and security review. Billing, invitations and accountant roles are
later product features; this MVP currently has one owner per business.

The current product targets INR-based businesses that invoice customers on credit.
It is not yet a universal model for retail, subscriptions, stock-heavy businesses,
multiple currencies, or every accounting workflow.
