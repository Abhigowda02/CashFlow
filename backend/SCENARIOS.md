# Scenario planner

Open **Scenario planner** in the application, then choose a business event. Customer
delays require an explicit customer selection and extra days; add another delay
to test a second customer independently. Only customers with outstanding invoices
are eligible. Partial receipts reduce the outstanding balance shown. A customer
delay applies to all that customer's currently unpaid invoices.

Customer stress changes shift the selected customer's sampled receipts after
conditioning on the invoice still being unpaid. This also shifts fallback receipts
for very overdue invoices. Baseline and scenario forecasts use the same random
draws, preserving other customers' receipts and future sales when only a customer
delay changes. Existing explicit collection-action overrides retain precedence.

Customer delays may optionally name invoice IDs, in which case only those open
invoices are delayed. Extra expenses can be labelled and categorised and may be
repeated monthly for an explicit count. Sales changes can carry a future date
window, and supplier terms can shorten as well as extend terms (an MSME extension
must be reviewed if it would cross the applicable 45-day guard). A revised payment
schedule can replace one outstanding invoice with up to six reviewed instalments;
it is a what-if only and unreliable instalments fall back to normal payment delay.

Other events are an additional expense on a selected date, a percentage change in
planned future sales, and an agreed extension of all open supplier bills. There
are no preselected stress changes. Existing invoice amounts are unaffected by a
sales assumption. Supplier extensions assume agreement and display a caution when
micro/small suppliers are included. This planner does not revise individual loan
instalments or individual supplier schedules.

Review the plain-language assumptions and select **Compare cash impact**. The
result compares shortage probability, estimated first shortage date, lowest median
cash, the gap below the safety floor, and median runway against the current plan.
The chart compares P50 balances; it does not represent a guaranteed outcome.
The estimated shortage date summarises paths that experience a shortage, whereas
median runway uses the P50 line. Editing assumptions marks old results as needing
recalculation.

Each returned `baseline` and `scenario` forecast has additive
`shortage_analysis` metrics: timing, probability, P10/P50 minima, peak funding
gap, days below the floor and scenario deltas. The top-level response remains
`{baseline, scenario}` for backward compatibility.

Give the scenario a name and save its assumptions. The database stores each saved
definition against the signed-in business. Open **Saved scenarios**, select up to
two, and compare them alongside a freshly computed baseline. Forecasts are never
saved as if they were current, and scenario calculations never update invoices,
obligations, or recorded cash. Saved definitions are revalidated against the
current ledger before every comparison.

## API

- `POST /api/scenario?delay_model=empirical|survival`: compare a definition with the
  current baseline.
- `GET /api/scenarios`: list the signed-in business's saved definitions.
- `POST /api/scenarios`: save `{ "name": "...", "changes": [...] }`.
- `DELETE /api/scenarios/{id}`: delete a definition owned by that business.

All endpoints require an authenticated session. Mutations require the existing
CSRF token and trusted origin. Definition validation allows at most 20 changes,
customer/supplier extensions of 1–180 days, one sales adjustment in -100% to +100%,
and positive integer INR expenses within the inclusive 90-day forecast. Duplicate
customer delays are rejected. Sales and supplier changes require planned sales
and open bills respectively. Saved assumptions may need editing after payment
receipts or an observation-date change.

Run `npm run test:scenario` and `npm run build` from `frontend/`, and
`python -m pytest backend/tests/test_scenarios.py -q` from the repository root.
