# AGENT RULES (read before every task)

You are working in the existing repo "CashFlow" (FastAPI backend + Python engine + ml + React/Vite/Tailwind/Recharts frontend).
Product: a cash-flow forecaster and copilot for small Indian businesses that invoice on credit. It predicts WHEN cash runs short
(with probability), explains WHY, and tells the owner WHAT to do. It is NOT an accountant: no GST/TDS/ITR filing, books, audit or legal advice.

RULES (follow strictly)
1. Single developer, single laptop. Work ONE task at a time in the order given. After each task run the checks listed and fix failures before moving on.
2. Do NOT rewrite working code. Extend it. Keep existing tests green: `python -m pytest engine/tests ml/tests backend/tests -q`, `python -m engine.check_contract`, `cd frontend && npm run build`. If a test must change because behaviour intentionally changed, update the test and say why.
3. Money = integer INR. Dates = ISO "YYYY-MM-DD". Timezone Asia/Kolkata. Indian number format in UI (Rs with lakh/crore grouping, e.g. Rs 1,20,000).
4. Multi-tenant: every new table has business_id; every query is scoped by the session's business_id. Never accept a tenant id from the client. All mutations keep the existing CSRF + Origin checks.
5. "No silent changes": nothing extracted, detected, guessed or matched is saved until the owner reviews and confirms it in a table (preview -> correct -> confirm). Never auto-send any message. Never auto-send legal notices.
6. Honesty: label estimates as estimates, show data freshness, never claim accuracy that was not measured, never claim production Account Aggregator access or that this replaces an accountant.
7. Each new backend module is a standalone file with plain JSON/dict in and out, type hints, a docstring stating its input/output, and its own pytest file. No hidden global state.
8. Create small files. Do not grow frontend/src/App.tsx or backend/main.py further than needed; put new routes in new routers under backend/routers/ and include them from main.py.
9. Before editing, read the files you will touch. After finishing, list files created/changed and the commands you ran with their output summary.
10. Commit after each finished prompt: `git add -A && git commit -m "P<NN>: <title>"`.
11. Do not install heavy or paid dependencies without saying so. Keep requirements.txt / package.json updated.
12. No secrets in code. Read credentials from environment variables, document them in backend/.env.example.

# SINGLE-LAPTOP MODE
- I work alone on ONE laptop and ONE copy of the repo. Ignore any mention of Laptop A/B, ownership, NEEDS files, drops, pack/unpack or sync in docs/prompts: they do not apply. Run ALL numbered items of every prompt you are given.
- Routers: put new routes in new files under backend/routers/ and include them from backend/main.py with a few lines; new tables in backend/tables/ or backend/database.py, whichever is simpler.

# WORKING STYLE (saves session budget)
- Do tasks in the order given without asking me questions between tasks. If blocked, note it in PROGRESS.md and continue with the next task.
- After each task (P-number): run only that task's tests, `git add -A && git commit -m "<P-number>"`, and append to PROGRESS.md: task id, DONE/PARTIAL, files changed, open issues.
- Keep replies short: files changed and test results only. Do not re-read files you just wrote. Do not paste large files back.
- Prompt texts live in docs/prompts/. 'Run P05' means open the file named in the bundle, find the section '## P05', and execute every numbered item in it.

# DEFINITION OF DONE (no half-finished or broken features)
A task is DONE only when ALL are true; otherwise mark it PARTIAL and finish it before starting the next task:
1. Works end to end through the real UI and the real API (not only unit tests or mock data): you ran it, and the result is correct.
2. Its tests pass, the full suite still passes, `npm run build` passes, and there are no console errors or failing network calls on that screen.
3. Empty, loading and error states exist, with a clear message. No dead buttons, no placeholder text, no TODO or "coming soon" in the UI.
4. Any setting it needs (SMTP, Setu, WhatsApp, OCR) has a clearly labelled working mock/fallback mode, so the feature still works without credentials. Never a silent failure.
5. It has an entry in docs/FEATURE_STATUS.md: feature, status PASS/FAIL, how to test it in under 1 minute, and what was tested.
6. If you cannot make a feature work, do NOT leave it visible and broken: put it behind a flag in frontend/src/lib/features.ts (hidden by default), mark FAIL in FEATURE_STATUS.md and tell me the exact reason in your reply. Never fake success.
Never mark DONE based on code that merely compiles.
