# CashFlow

The demo uses synthetic business and cash-flow data; it is not financial advice.

## Run the API

From the repository root, install the backend requirements and start the API:

```powershell
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

The API is available under `/api` on port 8000. CORS is enabled for the frontend
at `http://localhost:5173`.