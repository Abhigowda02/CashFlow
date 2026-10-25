# START HERE: handoff file (for a NEW Claude account / new session)

If you are a Claude instance reading this: the user is building **CashFlow**, a
cash-flow forecaster for small Indian businesses that invoice on credit, for a hackathon.
They work **alone on ONE laptop** with an AI coding agent (**Google Antigravity**, a GLM-type
agent) and have a limited number of hours. A previous Claude session produced the plan below,
and the user's request was: **"Do not cut anything. Give me every Antigravity prompt, start to end,
for everything we discussed."**

## What you must do
1. Read `01_PROJECT_MEMORY.md` fully (every decision, fact and requirement).
2. Read `CashFlow.zip` (uploaded with this file). List it first; do not extract `.git`, `.venv`,
   `node_modules`. Key paths: `backend/main.py`, `backend/ledger.py`, `backend/pdf_import.py`,
   `backend/database.py`, `engine/forecast.py`, `engine/actions.py`, `engine/collections.py`,
   `engine/schedules.py`, `engine/check_contract.py`, `engine/datagen.py`, `ml/delay_model.py`,
   `frontend/src/App.tsx` (1,317 lines), `docs/NOTIFICATIONS_PLAN.md`, `contracts/CONTRACT.md`.
3. Check which prompts in `03_`, `04_`, `05_` the user has already run. Ask ONE question: "Which prompt
   number did you finish last?" Then give them the next prompts in order, one block at a time, ready
   to paste. Do not shorten or drop any feature.
4. If a prompt file is missing or truncated, regenerate it from `01_PROJECT_MEMORY.md` using the
   format in `02_MASTER_PREAMBLE.md` (preamble + numbered tasks + acceptance checks).

## Prompt files in this pack (run in numeric order, P00 to P33)
| File | Prompts | Content |
|---|---|---|
| 02_MASTER_PREAMBLE.md | n/a | Paste at the top of EVERY Antigravity prompt |
| 03_PROMPTS_PART1_FOUNDATION.md | P00-P09 | Cleanup, git safety, schema/contract, remove demo, dynamic dates, invoice import, model upgrades, backtest |
| 04_PROMPTS_PART2_PRODUCT.md | P10-P20 | Forecast screen, reminders ladder, alerts, legal, action cards, customers worklist, UI rebuild |
| 05_PROMPTS_PART3_DATA_AND_POLISH.md | P21-P33 | Transactions, statements, recurring detection, matching, synthetic data, SMS, Setu, Connect screen, OCR, WhatsApp, Android, QA, pitch |
| 06_CHECKLIST_AND_PITCH.md | n/a | Progress checklist, honest pitch lines, demo script |

## Facts the next Claude must NOT get wrong
- The zip does NOT contain the earlier "contract kit" (`shared/`). Prompt P02 recreates it inside the project.
- The project has a `.git` folder with branches (`main`, `feat/platform`, `feat/integration`, remote `feat/engine`). P00 must inspect it before touching anything.
- The README says imports start with no obligations and zero future sales, so a real imported workspace draws a flat forecast. That is the most likely cause of "forecaster isn't forecasting".
- The README says `as_of` is deliberately frozen. The user now wants today's date (Asia/Kolkata). P04 changes this and keeps a "balance last updated" date.
- Session limit warning: the user may switch accounts. Always keep answers as files or copy-paste blocks.

## UPDATE: 4 hours left, two laptops (A = backend/engine, B = frontend + parser modules)
Read `07_TWO_LAPTOP_SPLIT.md`, then `08_LAPTOP_A_RUNBOOK.md` or `09_LAPTOP_B_RUNBOOK.md` (whichever laptop the user names) and `10_EXTRA_PROMPTS_INT_SYNC.md`.
All 34 prompts remain; they are divided by item numbers. Ask: "Which laptop are you and which step (A1/B1...) did you finish?" then give the next prompt(s) using only the listed items.

## UPDATE 2: bundled prompts
Use `11_BUNDLED_PROMPTS_FEWER.md` (12 bundles A-1..A-6, B-1..B-6; prompt texts are copied into the repo at docs/prompts/ and AGENTS.md holds the rules). Ask which bundle the user finished last (see PROGRESS_A.md / PROGRESS_B.md).

## UPDATE 3 (LATEST): ONE laptop, 8 prompts
The user now works alone on one laptop. Ignore files 07-11. Use `12_SINGLE_LAPTOP_8_PROMPTS.md` (bundles S-1..S-8) and `AGENTS_SINGLE.md` (copied to repo root as AGENTS.md). Ask which bundle S-1..S-8 is finished (see PROGRESS.md).
