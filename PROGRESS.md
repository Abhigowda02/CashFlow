# CashFlow Build Progress

## P00: Safe cleanup and git rollback point
- **Status**: DONE
- **Files Changed**: `.gitignore`, `ml/sample/payment_date_sample.csv`, cleanup of temp files, deleted cache/dist/local databases
- **Open Issues**: None
- **Commit**: `3df0e0b P00: cleanup and rollback point`, Tag: `rollback-before-rebuild`

## P01: Reproduce "the forecaster isn't forecasting" and fix the root cause
- **Status**: DONE
- **Files Changed**:
  - `scripts/diagnose_forecast.py`
  - `backend/main.py`
  - `frontend/src/App.tsx`
  - `backend/tests/test_forecast_api.py`
- **Open Issues**: None
- **Tests**: `backend/tests/test_forecast_api.py` (3 passed), `engine.check_contract` (PASS), `frontend build` (PASS)
- **Commit**: `a1bf91f P01: diagnose and fix forecast on real workspaces`

## P02: Shared schema and contract kit
- **Status**: DONE
- **Files Changed**:
  - `shared/schema.py`
  - `shared/samples/*.json` (11 models)
  - `shared/validate.py`
  - `shared/ENDPOINTS.md`
  - `shared/mock_server.py`
  - `shared/README.md`
  - `shared/tests/test_samples.py`
  - `frontend/src/types/contract.ts`
- **Open Issues**: None
- **Tests**: `python shared/validate.py` (PASS), `pytest shared/tests` (15 passed), `frontend npm run build` (PASS)
- **Commit**: `e12526a P02: shared schema and contract kit`

## P03: Remove demo code and fix the onboarding path
- **Status**: DONE
- **Files Changed**:
  - Deleted: `backend/demo.py`, `backend/tests/test_demo.py`, `frontend/src/DemoControl.tsx`, `examples/jury_*`, `examples/make_jury_demo.py`
  - Moved: sample datasets to `tests/sample_data/`
  - Modified: `backend/main.py`, `frontend/src/App.tsx`, `frontend/src/AuthGate.tsx`, `frontend/src/LedgerPage.tsx`, `engine/tests/test_engine.py`, `scripts/diagnose_forecast.py`, `README.md`
- **Open Issues**: None
- **Tests**: `git grep -i "demo" backend frontend/src` (0 results), `engine.check_contract` (PASS), `npm run build` (PASS), `pytest backend/tests shared/tests` (136 passed)

## P05: Review-first invoice import API
- **Status**: PARTIAL
- **Files Changed**: `backend/modules/invoice_mapper.py`, `backend/modules/gst_einvoice.py`, `backend/routers/invoices.py`, `backend/ledger.py`, `backend/main.py`, `backend/tests/test_invoice_import_router.py`, `docs/FEATURE_STATUS.md`
- **Open Issues**: The requested UI upload/review workflow and XLSX/PDF multi-invoice support are not yet implemented. Full backend suite has an unrelated date-sensitive failure in `test_expenses_totals_and_forecast_agree`; frontend build is currently blocked by existing unstaged unused declarations in `App.tsx`.
- **Tests**: invoice-import router tests (3 passed), `engine.check_contract` (PASS)

## Module batch 1: payment model helpers
- **Status**: DONE
- **Files Changed**: `backend/modules/payment_adjust.py`, `backend/tests/test_payment_adjust.py`
- **Open Issues**: Integration into the forecast engine remains a later batch step.
- **Tests**: `python -m pytest backend/tests/test_payment_adjust.py -q` (10 passed)

## Module batch 2: forecast accuracy helpers
- **Status**: DONE
- **Files Changed**: `backend/modules/accuracy.py`, `backend/tests/test_accuracy.py`
- **Open Issues**: API and forecast-log integration remains a later batch step.
- **Tests**: `python -m pytest backend/tests/test_accuracy.py -q` (9 passed)

## Module batch 3: forecast-view helpers
- **Status**: DONE
- **Files Changed**: `backend/modules/forecast_view_builder.py`, `backend/tests/test_forecast_view_builder.py`
- **Open Issues**: Endpoint integration remains a later batch step.
- **Tests**: `python -m pytest backend/tests/test_forecast_view_builder.py -q` (8 passed)

## P00 follow-up: generated-artifact cleanup
- **Status**: PARTIAL
- **Files Changed**: removed `.venv`, `.pytest_cache`, `frontend/dist`, `data/payment_date.csv`
- **Open Issues**: `backend/.local/saas.sqlite3` is locked by an unidentified external process after the locally started API was stopped. `.gitignore` already covers all requested generated paths.

## P09: UI-ready forecast API
- **Status**: PARTIAL
- **Files Changed**: `backend/routers/forecast_view.py`, `backend/main.py`, `backend/tests/test_forecast_view.py`
- **Open Issues**: The legacy monolithic frontend has not yet been switched to this endpoint; invoice payment distributions and accuracy history need their later integrations.
- **Tests**: forecast-view test (1 passed), `python -m engine.check_contract` (PASS)


