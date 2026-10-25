# EXTRA PROMPTS (needed by the two-laptop plan). Paste the TWO-LAPTOP PREAMBLE (below) first.

## TWO-LAPTOP PREAMBLE (replaces rule 8 and 10 of the master preamble; keep the others)
```
You are on ONE of two laptops working on the same project in separate copies. Your laptop letter is: <A or B>.
- Edit ONLY files owned by your laptop (see OWNERSHIP.md). If a change is needed in a file the other laptop owns, write the request in NEEDS.md (if you are B, asking A) or NEEDS_A.md (if you are A, asking B) and do not touch the file.
- Never edit backend/main.py or backend/database.py (auto-loaders discover backend/routers/*.py and backend/tables/*.py).
- Use only the frozen interfaces IF-0..IF-5 from OWNERSHIP.md. If an interface is not delivered yet, create a stub in a file YOU own (e.g. backend/stubs_b.py) and swap it when the real one arrives.
- Commit after each prompt. Run only the tests for your own files plus the full suite at sync time.
```

## INT-1 (Laptop A): auto-loaders, deps, ownership, pack/unpack
```
TASK:
1. Edit backend/main.py ONE last time: at startup, import every module in backend/routers/ (pkgutil) and include `router` objects with prefix "" (routes declare their own /api paths). Do the same for backend/tables/*.py (modules just import `metadata` from backend.database and define Tables; make sure metadata.create_all runs after discovery). Create backend/routers/__init__.py and backend/tables/__init__.py.
2. Create backend/deps.py exposing business_id_dep and csrf_dep by reusing the exact logic main.py uses today for session auth, business id, CSRF and Origin checks (read backend/auth.py and main.py first; do not duplicate security code, wrap it). Add a test showing a router using these deps rejects unauthenticated calls and mutation without CSRF.
3. Create OWNERSHIP.md from section 3 and 4 of docs (copy the ownership lists and interfaces IF-0..IF-5 verbatim from 07_TWO_LAPTOP_SPLIT.md, which I will paste below).
4. scripts/pack.py <A|B>: zips only files matching that owner's globs from OWNERSHIP.md (store globs in scripts/ownership.json), excluding node_modules, .venv, dist, __pycache__, *.sqlite3, .git; names it <letter>_drop_<n>.zip. scripts/unpack.py <zip>: refuses to write any file owned by the OTHER owner? No: refuses to overwrite files owned by ITS OWN laptop; it prints a list of new/changed files and asks for y/n.
5. Run all tests. Commit "INT-1".
```
(Paste section 3 and 4 of 07_TWO_LAPTOP_SPLIT.md under this prompt.)

## INT-2 (Laptop A): ledger_api.py and transactions stub for B
```
TASK: Create backend/ledger_api.py implementing IF-2 on top of backend/ledger.py (read it first; reuse existing import, receipt and plan logic, tenant scoping, idempotent receipts, no duplicated logic). Create backend/transactions.py with the IF-1 signatures; if P21 is not done yet, implement a minimal working version now (table backend/tables/transactions.py, dedupe hash, save/list/mark/closing_balance) and mark TODO for the rest of P21. Add tests. Then run `python scripts/pack.py A` to make the BASE drop for Laptop B.
```

## SYNC-OUT (either laptop, at each sync point)
```
TASK: Run all tests for my files, fix failures, `git add -A && git commit -m "sync <n>"`, then `python scripts/pack.py <A|B>`. Print the zip name and the list of files inside, and any open items I should write in NEEDS.md / NEEDS_A.md.
```

## SYNC-IN (either laptop, when receiving a drop)
```
TASK: `git add -A && git commit -m "before unpack"`, run `python scripts/unpack.py <zip> --me <A|B>`, `pip install -r backend/requirements.txt`, (B only: `cd frontend && npm install`), run the full test suite, `python -m engine.check_contract`, and (if backend running) `python shared/validate.py --live http://localhost:8000`. Report failures with file and line, and propose fixes ONLY inside files I own; for others write the request in NEEDS.md / NEEDS_A.md.
```
