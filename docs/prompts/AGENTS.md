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

# TWO-LAPTOP RULES (override rules 8 and 10 above)
You are on ONE of two laptops working on the same project in separate copies. Your laptop letter is: <A or B>.
- Edit ONLY files owned by your laptop (see OWNERSHIP.md). If a change is needed in a file the other laptop owns, write the request in NEEDS.md (if you are B, asking A) or NEEDS_A.md (if you are A, asking B) and do not touch the file.
- Never edit backend/main.py or backend/database.py (auto-loaders discover backend/routers/*.py and backend/tables/*.py).
- Use only the frozen interfaces IF-0..IF-5 from OWNERSHIP.md. If an interface is not delivered yet, create a stub in a file YOU own (e.g. backend/stubs_b.py) and swap it when the real one arrives.
- Commit after each prompt. Run only the tests for your own files plus the full suite at sync time.

# WORKING STYLE (saves session budget)
- Do tasks in the order given without asking me questions between tasks. If blocked, log it in NEEDS.md / NEEDS_A.md and continue with the next task.
- After each task: run only the tests for that task, commit `git commit -am "<task id>"`, and append to PROGRESS_<A|B>.md: task id, DONE/PARTIAL, files changed, open issues.
- Keep replies short: list files changed and test results only. No long explanations.
- Do not re-read files you just wrote. Do not paste large files back to me.
- Prompt texts live in docs/prompts/. When told 'run P05 items 3-7', open docs/prompts/03_PROMPTS_PART1_FOUNDATION.md, find the section '## P05', and execute ONLY those numbered items.
