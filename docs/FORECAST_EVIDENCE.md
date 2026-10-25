# Forecast evidence and reproducible evaluation

**Not yet validated on representative real businesses.** The judge demonstration
and the checked-in small invoice fixture are synthetic pipeline smoke tests.
They demonstrate import, censoring, training, prediction and evaluation plumbing;
they do not establish forecast accuracy or calibration on Indian businesses.
An observed payment history, a model estimate and a hypothetical collection action
are different kinds of information. None guarantees that a customer will pay.

## Data and feature policy

`data/payment_date.csv` is a local invoice-payment export whose original publisher,
licence and collection protocol have not been independently verified. It contains
USD and CAD nominal values. Neither their units nor the meaning of
`total_open_amount` as an original invoice face amount is established. The adapter
does not convert them to INR. Amount is excluded unless the canonical metadata
explicitly establishes a single known currency/unit and original-invoice-amount
semantics. A declaration is not proof of representativeness.

The raw adapter removes exact duplicates, refuses conflicting document identities,
keeps business/customer identities separate, and preserves open rows as censored
even when they contain stale clearing dates. Supply the real observation snapshot
date when known. Inferring it from the latest posting/closed-payment date is an
assumption that can materially affect censoring; report that provenance.

Canonical CSVs retain `source_kind`, `source_provenance`,
`observation_date_source`, currency/unit metadata and available deduplication counts.
Missing provenance remains unknown. Synthetic source metadata cannot be silently
upgraded to real-business evidence. Existing files without metadata are unverified,
even when their file name sounds realistic.

## Run an explicitly labelled pipeline smoke test

From the repository root, with `ml/requirements.txt` installed:

```powershell
python -m ml.evaluate ml/results/synthetic.csv --source-kind synthetic --folds 3 --bootstrap 200 --seed 42 --output ml/results/smoke
```

This writes `metrics.csv`, `calibration.png` and `report.json` in that output
directory. The chart title and every metric row identify the run as synthetic
pipeline smoke only. The JSON records input SHA256, provenance, environment,
fold origins and periods, paid/censored counts, amount-feature policy, skipped
folds, random seed and statistical limitations. Preserve all three outputs
together. Changing the input file changes its hash; comparing untracked results
without their source and protocol is not meaningful evidence.
If every fold is skipped or fails to fit, the CLI exits with status 2 after writing
the explicit failure report. The Python API returns those status rows for audit.

For an adapted canonical export, use the same command with its actual file path,
`--source-kind unverified` and a separate output directory. This does not certify
the export as representative. `ml.train.training_table_from_csv` performs raw
payment-export adaptation; the evaluator deliberately accepts canonical tables
so that units and snapshot provenance remain explicit.

## Time-aware protocol

The default uses three expanding origins after the oldest approximately half of
invoices. Subsequent issue-date windows are disjoint test sets. Tied issue dates
stay together. `--folds 1` retains an approximately 70/30 chronological split.
Requested origins that coincide because of ties collapse; the report distinguishes
requested and emitted counts. Folds with fewer than ten training rows, three test
rows or three observed training settlements are explicitly skipped. Failed fits
are reported rather than presented as successful zero-error scores.

At each origin, outcomes on or after the origin are re-censored. Every training
and test row's supplied `past_delay`, `prior_count` and issue-month features are
rebuilt. History uses only training invoices paid strictly before the earlier of
the row's issue date and the origin. Later payments on training invoices, earlier
test invoices' eventual payments and precomputed full-export features cannot enter
predictions. The model fits afresh with `use_saved=False`; a shared full-data
artifact is never loaded into held-out evaluation. The protocol freezes history
at the origin even for invoices issued later in that test window.

Baselines are zero delay (payment on due date) and the customer's training-observed
median delay, with a pooled training median for unseen customers. Neither baseline
can pay before invoice issue: its point date is clamped to that earliest boundary.
Their probabilities are explicit point-mass distributions. The survival model's
CDF and median condition on the invoice being unpaid at issue; a shifted early-
payment distribution cannot allocate probability before the invoice exists. These
are predictions made at issue, not conditional estimates for an already-overdue
portfolio. This evaluation does not validate 90-day cash-shortage
probabilities or the effect of reminders/financing actions.

## Censored metrics and uncertainty

At 10/20/30/45/60 days after due date, the primary score is IPCW Brier error.
A reverse Kaplan-Meier estimate of the censoring distribution is fitted on the
training outcomes only. An event by a horizon receives inverse censor-survival
weight at its event time; an observation extending beyond that horizon receives
the horizon weight. Earlier censored observations contribute zero to the numerator,
but remain in the full test-cohort denominator. They are never labelled paid.
Payment events precede censoring events tied on the same recorded date.

The calibration chart compares the full-cohort mean predicted paid share with a
Horvitz-Thompson IPCW estimate of the actual paid share at each supported horizon.
It is an aggregate horizon diagnostic, not proof of individual probability calibration.
Finite-sample weighted shares and intervals can exceed one; the evaluator does not
hide that by clipping. Reports include known-outcome counts, censor counts,
effective weighted sample size, maximum weight and training follow-up support.

Horizons at or beyond maximum training follow-up, censor-survival probabilities
at or below 0.05, and horizons without known test outcomes are marked unavailable.
Weights are not silently truncated. Missing values mean unsupported evidence,
not perfect predictions. MAE is reported only for observed test settlements and
is explicitly labelled selection-biased secondary evidence.

Pointwise 95% intervals use a seeded customer-cluster bootstrap with at least 200
replicates by default. They require at least 20 rows and five customer clusters;
smaller samples explicitly have no interval. Intervals condition on the fitted
model and training censor estimate. They do not capture model-fitting uncertainty,
serial/calendar dependence, or censor-model misspecification. Bootstrap replicates
below 100 produce no interval, rather than a precision claim.

IPCW relies on independent censoring and a censor process transferable from train
to test. Invoice disputes, changes in collection practices, calendar-based snapshots
and customer attrition can violate those assumptions. Several forward splits do
not remove these limitations. More representative, consented business records,
known snapshots, consistent currency semantics and prospective follow-up are
needed before a real-business accuracy or calibration claim.

Metric definitions follow the primary
[scikit-survival Brier-score documentation](https://scikit-survival.readthedocs.io/en/stable/api/generated/sksurv.metrics.brier_score.html)
and its
[reverse Kaplan-Meier tie convention](https://scikit-survival.readthedocs.io/en/stable/api/generated/sksurv.nonparametric.kaplan_meier_estimator.html).
The implementation uses NumPy directly and does not add a scikit-survival dependency.

## Verification

```powershell
python -m pytest ml/tests/test_evaluation.py ml/tests/test_pipeline.py -q -p no:cacheprovider
```

Tests check hand-computed censored scores, support failures, early payments,
deterministic uncertainty, tied issue-date boundaries, train/test feature leakage,
future-payment censoring, fresh fits and synthetic/report provenance labels.
