# Payment delay model

Python 3.10+. Install with `python -m pip install -r ml/requirements.txt`.
Run tests with `python -m pytest ml/tests`.

Train the first dataset and persist the model:

```powershell
python -m ml.train --csv data/payment_date.csv
```

This always trains afresh and atomically saves `ml/artifacts/delay_model.joblib`
(ignored by Git). `fit()` or `fit(table_or_business)` loads this file when it
exists; without an artifact it trains from the supplied table/business.
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
An inferred date is an assumption, not verified dataset provenance. Amounts retain
their original nominal units: the USD/CAD export is not converted to INR and
mixed-currency amounts limit interpretation. No customer segments are inferred.

`build_training_table(business)` accepts the contract Business dictionary or a
canonical CSV path. `load_csv(path)` validates canonical data. Required columns:
`invoice_id,customer_id,issue_date,due_date,segment,amount,issue_month,past_delay,prior_count,duration,event`.
Optional `paid_date` and `as_of` preserve observation provenance. Dates are ISO.
`past_delay` is the mean delay of this customer's invoices paid strictly before
the invoice's issue date; `prior_count` counts only those invoices. No history
uses a zero mean and count. CSV producers must apply this same rule.

`ml.train.training_table_from_csv(path, as_of=None)` exposes the adapter for
exporting a canonical table with `.to_csv(path, index=False)`.
The evaluator accepts canonical tables only. After adapting:

```powershell
python -m ml.evaluate ml/results/payment_date_canonical.csv
```

This writes `ml/results/metrics.csv` and `ml/results/calibration.png`.
Training does not run evaluation or overwrite the synthetic evaluation artifacts.
Checked-in result artifacts, when present with source `ml/results/synthetic.csv`,
are synthetic smoke-test outputs only. Each metrics row records its source and split.

The model fits a penalized lifelines Weibull AFT using log amount, issue month,
segment, prior count, and past delay. Duration is paid date minus due date for
observed payments (event 1); open invoices use as_of minus due date (event 0).
Paid dates after as_of are censored too. Open invoices are right censored because
their final payment date is unknown: treating as_of as payment would bias delays
downward. A shared shift makes all training durations positive, including early
payments and open invoices not yet due. Sampling reverses this shift.

Customers with fewer than three training invoices use an intercept-only segment
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

Evaluation trains on issue dates strictly before the ~70% boundary; tied dates
stay together. Training outcomes are censored again at the boundary. MAE is
reported only for observed test payments, so it has selection bias. Calibration
compares shares paid at 10/20/30/45/60 days using only invoices with known outcome
at each horizon (payments or sufficient censor follow-up); its sample size is
reported and it can also be biased by informative censoring. Baselines use zero
delay and training-only customer medians (pooled median for unseen customers).

Limits: Weibull shape assumptions, small segments, calendar drift, missing
covariates, and informative censoring can affect accuracy. Historical table
features must be computed by a trusted adapter. Synthetic data validates the
pipeline only; it does not demonstrate real-world forecasting accuracy. This
module does not depend on engine/, and makes no changes to application code.
