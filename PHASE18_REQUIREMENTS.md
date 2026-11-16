# Phase 18 Requirements & Acceptance Criteria

1. Guardian matching must ignore empty identifiers and match normalized mobile/phone/email/CNIC.
2. New admissions require at least one guardian contact identifier unless an existing guardian is selected.
3. Family tree must expose all children linked to the same guardian.
4. Admission officer may create admissions and generate vouchers but cannot access operations-only areas.
5. Operations admin is limited in navigation to Hostel, Mess, Transport and Inventory workflows.
6. Student CSV/XLSX exports preserve report status/class filters.
7. Authenticated responses are not browser-cacheable; HTTPS deployments receive HSTS.
8. PostgreSQL remains the production database target; SQLite remains development-only.
9. Automatic codes remain unique and sequential using the SequenceCounter table.
10. Voucher PDF contains Student, Bank and School copies.
