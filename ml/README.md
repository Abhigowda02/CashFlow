# Payment delay model

Authenticated SaaS calls now supply an internal `_model_scope` from the server's
session business ID. For these calls, `fit` uses `ml.personalization` to fit/cache
only that business's records, never the shared offline dataset artifact. Scope
must never be taken from browser input. See the root README's customer-behaviour
section for the data gate, private artifact lifecycle, and prediction limits.

Python 3.10+. Install with `python -m pip install -r ml/requirements.txt`.
Run tests with `python -m pytest ml/tests`.

Train the first dataset and persist the model:

```powershell
python -m ml.train --csv data/payment_date.csv
```

This always trains afresh and atomically saves `ml/artifacts/delay_model.joblib`
(ignored by Git). `fit()` or `fit(table_or_business)` loads a compatible file
when it exists; without an artifact it trains from the supplied table/business.
Feature-policy version 2 prevents legacy artifacts from silently retaining the
unsafe nominal-amount feature. An old artifact is refitted when data is supplied;
loading an old artifact without data gives an explicit retraining instruction.
Use `fit(table, use_saved=False)` to explicitly retrain. Evaluation always uses
this override so a saved full-data model cannot leak into held-out evaluation.
Only load trusted local joblib artifacts.

The CLI accepts canonical CSVs or the raw payment-date export. Its adapter removes
exact duplicate rows, rejects conflicting document IDs, uses business_code/doc_id
as invoice identity and business_code/cust_number as customer identity, and uses
posting_date, due_in_date, clear_date and isOpen for dates and censoring. Missing
invoice_id values are harmless because doc_id is used. Segments are `unknown`.
Open rows remain censored even if they contain a stale clear_date.
Without snapshot metadata it infers as_of from the latest posting or closed
payment date; specify `--as-of YYYY-MM-DD` when the true observation date is known.
An inferred date is an assumption, not verified dataset provenance. The original
publisher and the semantics of `total_open_amount` have not been verified. The
USD/CAD labels are retained without conversion, and **the nominal amount feature
is excluded for this raw export**, including a single-currency subset. No customer
segments are inferred. Offline training is pipeline development, not validation
on representative real businesses.

`build_training_table(business)` accepts the contract Business dictionary or a
canonical CSV path. `load_csv(path)` validates canonical data. Required columns:
`invoice_id,customer_id,issue_date,due_date,segment,amount,issue_month,past_delay,prior_count,duration,event`.
Optional `paid_date` and `as_of` preserve observation provenance. Dates are ISO.
The optional metadata columns `currency`, `amount_unit_verified`,
`amount_semantics`, `currency_provenance`, `source_kind`, `source_provenance`,
`observation_date_source`, `source_rows`, and `duplicates_removed` survive canonical
CSV export/reload. Legacy CSVs remain readable with safe unknown/unverified defaults.
`past_delay` is the mean delay of this customer's invoices paid strictly before
the invoice's issue date; `prior_count` counts only those invoices. No history
uses a zero mean and count. CSV producers must apply this same rule.
Canonical loading also reconstructs payment/censor end dates and, when `as_of`
is present, recensors any future payment. Conflicting `paid_date`/duration metadata
is rejected. Supplied `past_delay`/`prior_count` values are rebuilt from observed
settlements in the file, strictly before each invoice's issue date. This is a
conservative policy: earlier history omitted from a canonical file is not assumed
known. Evaluation additionally freezes history at each training origin.

`ml.train.training_table_from_csv(path, as_of=None)` exposes the adapter for
exporting a canonical table with `.to_csv(path, index=False)`.
See [forecast evidence instructions](../docs/FORECAST_EVIDENCE.md) for the
forward-in-time evaluation workflow, provenance requirements, censored metrics,
uncertainty, and limitations. A canonical table can be passed to the evaluator:

```powershell
python -m ml.evaluate ml/results/payment_date_canonical.csv
```

This writes `ml/results/metrics.csv` and `ml/results/calibration.png`.
Training does not run evaluation or overwrite the synthetic evaluation artifacts.
Checked-in result artifacts, when present with source `ml/results/synthetic.csv`,
are synthetic smoke-test outputs only. Each metrics row records its source and split.

The model fits a penalized lifelines Weibull AFT using issue month, segment, prior
count, and past delay. Log amount is optional and excluded by default. It is used
only when **every row** explicitly confirms `amount_unit_verified=true`,
`amount_semantics=original_invoice_amount`, and a single known currency. A currency
label alone never authorizes the feature. For the SaaS importer this confirmation
is the owner's declaration, not independent verification; old workspaces without
confirmation keep amount excluded. The model records `amount_feature_used` and
`amount_feature_policy`, and private fingerprints include the policy metadata.
A saved unit-sensitive model is not reused with unknown or differing supplied
units; no exchange rate or conversion is guessed. Duration is paid date minus due date for
observed payments (event 1); open invoices use as_of minus due date (event 0).
Paid dates after as_of are censored too. Open invoices are right censored because
their final payment date is unknown: treating as_of as payment would bias delays
downward. A shared shift makes all training durations positive, including early
payments and open invoices not yet due. Sampling reverses this shift.

Customers with fewer than three observed training payments use an intercept-only segment
Weibull fit (a censored estimate of segment average delay); unseen segments use
the pooled fit. This preserves a distribution and conditions it on survival,
unlike substituting a deterministic arithmetic average. With no observed payments,
fit raises ValueError because the delay scale cannot be identified reliably.

`fit(table_or_business)` returns a model and sets the module-level default for
the contract's `sample_delay(invoice, customer, rng, days_overdue=0)` function.
Prefer returned-model methods for concurrent use. Pass a NumPy Generator for
reproducibility. Positive days_overdue conditions on still being unpaid at that
delay; zero requests an unconditional sample, including possible early payment.
Returned days are rounded upward and bounded below by the negative shift.

Evaluation must keep tied issue dates together, recensor training outcomes at
each origin, and build customer histories without post-origin settlements.
Baselines use zero delay and customer medians computed from training-observed
payments (a pooled median for unseen customers). Paid-only MAE and known-outcome
calibration have selection/censoring limitations and must not be presented as
definitive accuracy evidence. See the evidence instructions for exact metrics
and supported comparison windows.

Limits: Weibull shape assumptions, small segments, calendar drift, missing
covariates, and informative censoring can affect accuracy. Historical table
features must be computed by a trusted adapter. Synthetic data validates the
pipeline only; it does not demonstrate real-world forecasting accuracy. This
module does not depend on engine/, and makes no changes to application code.

`conditional_quantile` and `conditional_cdf` accept elapsed days relative to the
due date (negative before due). The engine's `sample_after` path uses the same
survival conditioning for already-unpaid invoices. The older `sample_delay`
interface remains available for offline callers and contract compatibility.
