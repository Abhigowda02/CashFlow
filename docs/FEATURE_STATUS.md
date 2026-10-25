# Feature status

| Feature | Status | Test in under a minute | Tested |
| --- | --- | --- | --- |
| Review-first CSV/GST invoice import API | PARTIAL | Sign in, POST a CSV to `/api/invoices/preview`, then submit its edited rows to `/api/invoices/commit` with INR confirmation. | Mapper, GST error handling and preview/commit tests pass. UI upload/review flow remains to be added. |
| Customer payment reminder ladder & delivery (P13, P14) | PASS | Open "Payment reminders" tab, click "Review & Approve" on any customer draft, select channel (Email/WhatsApp/SMS), and click Send reminder. Email sends via SMTP or logs safe mock send with mailto fallback; WhatsApp/SMS generates chat link. | Escalation rungs (-3, 0, +7, +15, +30), grouping by customer, relationship tone, SMTP mock/fallback delivery, immutable audit logs, ReminderSheet UI, and route tests pass. |
| Owner cash shortage & due alerts (P15) | PASS | Click the Bell in top navigation to open Notification Center. See shortage warnings with root causes and upcoming consolidated due obligations. Open preferences to adjust risk threshold or send a test alert email. | Shortage risk detection, stale balance suppression, threshold/horizon filtering, 7/3/1 day due expense consolidation, dedupe keys, mark read, snooze, email alerts, and route tests pass. |
