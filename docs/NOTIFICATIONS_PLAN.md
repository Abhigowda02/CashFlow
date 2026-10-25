# Proposed cash-aware notifications

Status: recommendation only. No email, SMS, WhatsApp or push delivery has been enabled.

Start with a persistent in-app notification centre, then opt-in email. Add WhatsApp
only after the owner explicitly chooses it and the provider setup is complete.
The notification recipient is the business owner, not the owner's customers.

## Useful alerts

| Event | Suggested behaviour |
| --- | --- |
| Upcoming expense | Configurable 7/3/1-day reminders, consolidated when several payments share a date |
| Financial pressure | Escalate a due reminder when a fresh forecast crosses the owner's risk threshold before the payment |
| Weekly expense digest | Next week's commitments, last-updated date, and links to the expense dashboard |
| Collections opportunity | Link a shortage warning to the ranked collections/actions page, preserving service/dispute guidance |
| Stale records | Ask the owner to update cash and receipts; suppress claims about current cash risk until data is fresh |

An illustrative alert: “Payroll is scheduled in 3 days. Your latest forecast shows
a possible gap before then. Review the forecast and compare collection options.”
Actual amounts, probability and dates must come from the owner's saved records,
and show the forecast's observation timestamp. Estimates are not guarantees.

## Implementation outline

1. Add tenant-scoped preferences, notification events, read/snoozed state and a
   delivery outbox to the database. Use a unique key based on business, obligation,
   occurrence date and reminder stage; meaningful forecast changes can create a
   new risk event without duplicating the same reminder.
2. Run a scheduled server worker in the business timezone, independent of whether
   the browser is open. Use Asia/Kolkata initially. Do not roll the cash balance
   forward automatically when bank movements have not been reconciled.
3. Create in-app events first. Add email after address verification and consent.
   Apply quiet hours and digest preferences, retries, delivery status and deduplication.
4. Link alerts to the relevant expense, forecast and action page. Read/snooze does
   not change accounting. Recording an actual expense payment would need its own
   idempotent cash transaction and per-occurrence settlement state.
5. Keep messages privacy conscious: allow a minimal “payment reminder available”
   notification instead of exposing balances on a lock screen. Never send another
   business's data or contact a customer's debtor automatically.

In-app notifications do not require OS notification permission. Browser system
notifications are a separate feature that needs explicit permission and HTTPS:
[MDN Notifications API](https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API).
WhatsApp business-initiated alerts require recipient opt-in and the appropriate
approved-template flow outside the service window:
[Twilio WhatsApp overview](https://www.twilio.com/docs/whatsapp/api).

Before external delivery: choose the provider, configure credentials on the server,
verify sender/recipient identities as required, and test unsubscribe, tenant
isolation, stale-data suppression, quiet hours, expiry and retry idempotency.
