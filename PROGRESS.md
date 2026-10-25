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


