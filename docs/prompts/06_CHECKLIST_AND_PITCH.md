# CHECKLIST, ORDER AND PITCH

## Run order (one laptop, nothing cut)
Do now (5 min, in parallel with P00): register Setu Bridge (FIU + AA data product, sandbox credentials).
1. Foundation: P00 P01 P02 P03 P04 P05 P06 P07 P08 P09
2. Product: P10 P11 P12 P13 P14 P15 P16 P17 P18 P19 P20
3. Data: P21 P22 P23 P24 P25 P26 P27 P28 P29
4. Tier 3: P30 (Android SMS) P31 (OCR) P32 (WhatsApp API)
5. Finish: P33

If time runs short, the earlier-agreed priority is: Tier 1 = P03-P20 (no demo, dates, real invoices, forecast screen, reminders, alerts, actions, UI);
Tier 2 = P21-P29 (statement, recurring, matching, SMS, Setu); Tier 3 = P30-P32 (+ legal PDF polish). Do not skip P00, P02, P08, P33.

## Checklist (tick as you go)
- [ ] P00 cleanup + tag  - [ ] P01 forecast diagnosis  - [ ] P02 contract kit  - [ ] P03 demo removed  - [ ] P04 dynamic dates
- [ ] P05 invoice import  - [ ] P06 model A  - [ ] P07 model B  - [ ] P08 backtest  - [ ] P09 forecast view API
- [ ] P10 shell  - [ ] P11 Home  - [ ] P12 Invoices  - [ ] P13 ladder  - [ ] P14 delivery  - [ ] P15 alerts
- [ ] P16 legal  - [ ] P17 action cards  - [ ] P18 customers worklist  - [ ] P19 actions + schedules  - [ ] P20 UX pass
- [ ] P21 transactions  - [ ] P22 statements  - [ ] P23 recurring  - [ ] P24 weekly/yearly  - [ ] P25 matching  - [ ] P26 synthetic
- [ ] P27 SMS  - [ ] P28 Setu  - [ ] P29 Connect screen  - [ ] P30 Android  - [ ] P31 OCR  - [ ] P32 WhatsApp API  - [ ] P33 QA + pitch

## Straight answers to keep in the pitch
- Replace an accountant? No. Cash-flow copilot: reads invoices and bank data, predicts shortages, recommends actions. Owner approves each action. No GST/TDS/ITR filing, books, audit or legal advice.
- Mobile and laptop: one React codebase; web app plus Android APK via Capacitor. iOS cannot read SMS. Play Store restricts SMS permission, so the demo APK is sideloaded.
- Setu: "AA-integrated, tested on Setu sandbox." Sandbox data is mock data. Production needs KYC, product review, Sahamati onboarding, and a regulated FIU partner. Do not say it reads real users' expenses.
- Accuracy: "Backtest on public data" plus live forecast-vs-actual tracking that builds over time. Not a claim about each customer business.
- Legal: draft notices marked "for advocate review"; MSMED interest uses an editable RBI rate; verify current portal and rules with an advocate.
- Data privacy: invoice images go to a third party only in LLM-OCR mode (disclosed); SMS filtered on-device; account numbers masked.

## Demo script (5 min)
1. Home: headline "Likely short by Rs X around <date> (Y% chance)", chart bands, why list.
2. Connect data: upload a bank statement -> recurring expenses detected -> approve -> credits matched to invoices -> forecast updates.
3. Customers: one-tap reminder (WhatsApp link), log "customer promised to pay on <date>", forecast shifts.
4. Actions: instalment plan card, effect on shortage probability, revised schedule.
5. Overdue 30+ days: statutory interest and the "DRAFT - for advocate review" notice.
6. Alerts bell: shortage alert naming the cause. Accuracy badge: backtest metrics.
