# Phase 22 – Automatic Billing Month & Multi-Month Dues

- Voucher defaults to the recommended billing month based on today's date.
- Default schedule: normal months use the current month; April recommends June; May recommends July.
- The recommendation is optional and can be overridden from the month calendar.
- Multiple months can be selected for students with 2–3 months dues.
- Fee items are generated per selected billing month, e.g. Tuition Fee - October 2026.
- Existing unpaid month/fee invoices are included in the generated PDF instead of being duplicated.
- Bulk voucher generation supports the same month selection and existing-due handling.
- `FeeInvoiceItem.fee_month` records the actual billing month for reporting and auditability.
