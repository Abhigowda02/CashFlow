# TWO-LAPTOP SPLIT (4 hours left, nothing removed)
All 34 prompts (P00-P33) stay. They are divided so the two laptops never edit the same file.
Laptop A = "Brain": database, engine, ML, API, backend services. Laptop B = "Face": frontend + pure parser modules.
Deadline plan: 4:00 total. Last 45 minutes are integration + QA, so build time is about 3h15.

## 1. The five rules that prevent merge errors
1. **File ownership** (section 3). Never edit a file the other laptop owns. If you need a change, write it in `NEEDS.md` and tell the other person.
2. **Auto-loaders** (created once by A in prompt INT-1): routers in `backend/routers/*.py` and tables in `backend/tables/*.py` are discovered automatically. Nobody edits `backend/main.py` or `backend/database.py` after INT-1.
3. **Frozen interfaces** (section 4). A promises these function signatures; B codes to them, with a stub until A's drop arrives.
4. **Sync points** (section 5): the owner runs `python scripts/pack.py <A|B>` -> zip of ONLY their files -> other laptop runs `python scripts/unpack.py <zip> --me <A|B>` (refuses to overwrite files owned by the other side). Transfer by Google Drive / WhatsApp / USB / email.
5. **Requirements**: A edits `backend/requirements.txt`; B writes its needs in `requirements_B.txt` (A merges at S3). Frontend `package.json` belongs to B only.

## 2. Timeline (minutes from now)
| Time | Laptop A | Laptop B | Sync |
|---|---|---|---|
| 0:00-0:25 | P00, P02, INT-1, INT-2 (base kit) | Start immediately on the ORIGINAL zip: pure modules batch 1 (see B runbook, B1-B4) | **S0 at 0:25:** A sends BASE zip -> B applies |
| 0:25-1:15 | P21 (transactions layer), P01, P03a, P04 | B5-B8 more modules, then P03b, P10 (shell) | **S1 at 1:15** |
| 1:15-2:15 | P05a, P06, P07, P08, P09 | P11 Home, P12 Invoices (against mock server, then real API) | **S2 at 2:15** |
| 2:15-3:00 | P13b, P14a, P15a, P17, P16 | P14b UI, P15b UI, P18, P19b | **S3 at 3:00** |
| 3:00-3:15 | P19a, P24, P26 | P29, Expenses frequency UI | |
| 3:15-3:30 | P28, P31, P32 | P20, P30 | **S4 at 3:30** (both finish) |
| 3:30-4:00 | Integration, P33 (hosting, QA, docs) | Test script, bug fixes, rehearse demo | Final check |
Times are targets; if a prompt takes longer, finish it and keep order. Items nearest the end of each column are the ones at risk, so do not reorder the early ones.

## 3. File ownership
**Laptop A owns:** `engine/`, `ml/`, `contracts/`, `shared/`, `scripts/` (except e2e), `backend/` EXCEPT the B files below, `docs/` (except UX/TEST docs), `README.md`, `.gitignore`, `Dockerfile/render.yaml`, `requirements.txt`, `tests/sample_data/`.
**Laptop B owns:** all of `frontend/` (incl. `android/`, `package.json`), and these backend files only:
`backend/modules/{invoice_mapper,gst_einvoice,reminder_engine,statement_parser,recurring_detector,invoice_matcher,sms_parser}.py`,
`backend/routers/{b_statements,b_sms,b_recurring,b_matches}.py`, `backend/tables/b_*.py`, their tests `backend/tests/test_b_*.py`, `docs/UX_CHECKLIST.md`, `docs/TEST_SCRIPT.md`, `scripts/e2e_smoke.py`, `requirements_B.txt`, `NEEDS.md` (B's requests to A), `NEEDS_A.md` is A's requests to B.
Everything else not listed = A.

## 4. Frozen interfaces (A implements by S1; B uses stubs until then)
Transaction row dict: `{"date":"YYYY-MM-DD","amount":int (positive INR),"direction":"credit|debit","description":str,"balance":int|None,"source":"statement|sms|aa|manual|synthetic","ref":str|None}`
- **IF-0** `backend/deps.py` (INT-1): `business_id_dep` (FastAPI dependency returning the session's business id) and `csrf_dep` (CSRF/Origin check for mutations). B's routers import only these.
- **IF-1** `backend/transactions.py` (P21): `save_transactions(rows, source, business_id, filename=None) -> {"batch_id","new_rows","duplicate_rows"}`; `mark_duplicates(rows, business_id) -> rows with "duplicate": bool`; `list_transactions(business_id, status=None, direction=None, since=None) -> list[dict]`; `set_status(business_id, ids, status)`; `closing_balance(business_id) -> {"balance","date"}|None`; `normalize_description(text) -> str`.
- **IF-2** `backend/ledger_api.py` (INT-2, later extended): `list_open_invoices(business_id) -> list[dict]` (id, customer_id, customer_name, amount, outstanding, issue_date, due_date); `record_receipt_for_invoice(business_id, invoice_id, amount, date, receipt_id) -> dict`; `add_obligations(business_id, items) -> list[dict]` (item = name, amount, frequency monthly|weekly|yearly, day_of_month|weekday|month, category, source); `get_customers(business_id) -> list[dict]`.
- **IF-3** Reminder engine (B, pure): `next_steps(invoices, customers, sent_log, promises, today, settings) -> list[dict]` and `render(step, settings) -> {"subject","body"}`; A's router calls it.
- **IF-4** Invoice mapper (B, pure): `map_columns(headers) -> {mapping, confidence, unmapped}`, `parse_rows(rows, mapping) -> list[dict]`; `parse_gst_einvoice(json) -> list[dict]`.
- **IF-5** API shapes: the sample JSON in `shared/samples/` plus `shared/ENDPOINTS.md` (A creates in P02). B builds UI against `uvicorn shared.mock_server:app --port 8000`.
If either side must change an interface: write it in NEEDS.md / NEEDS_A.md and both agree before coding.

## 5. Sync procedure (5 minutes each)
**A to B:** `python scripts/pack.py A` -> `A_drop_<n>.zip` -> send -> B: `python scripts/unpack.py A_drop_<n>.zip --me B` -> `pip install -r backend/requirements.txt` -> run B's tests.
**B to A:** `python scripts/pack.py B` -> `B_drop_<n>.zip` -> send -> A: `python scripts/unpack.py B_drop_<n>.zip --me A` -> run all tests + `python shared/validate.py --live http://localhost:8000`.
Each side commits (`git add -A && git commit`) right before and after unpacking. If something breaks: `git reset --hard HEAD~1`.
**Optional safety net:** upload either drop zip here and I will unpack it, run the tests and tell you exactly what is wrong.

## 6. If you lose a session
New Claude account: upload CashFlow.zip + CashFlow_Prompt_Pack.zip, say "Read 00_START_HERE_HANDOFF.md and 07_TWO_LAPTOP_SPLIT.md. I am Laptop A (or B). I finished <step>. Continue."
