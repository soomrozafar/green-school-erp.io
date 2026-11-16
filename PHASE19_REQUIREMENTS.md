# Phase 19 Requirements

## Admission Officer least privilege
- Admission Dashboard
- New Admission
- Students (admission domain)
- Families
- Admission Reports
- Fee voucher generation and print/PDF only
- No fee payment posting, payroll, HR, inventory, hostel, transport, library, exams, settings, backups, audit administration, or general finance exports.

## Voucher workflow
- Admission can select a fee structure and generate an invoice/voucher.
- Voucher prints Student Copy, Bank Copy, School Copy.
- Payment posting remains Accountant/Admin only.

## Authorization
- Server-side role checks return HTTP 403 for unauthorized routes.
- UI hiding is not relied upon for security.
