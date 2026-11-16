# Phase 9 QA Checklist

## Automated smoke tests
- Health endpoint returns HTTP 200 and JSON status `ok`.
- Login page renders.
- Protected API summary rejects anonymous requests.
- Reports page imports its database dependency correctly.

## Functional test areas
- Authentication: valid login, invalid login, logout, inactive user.
- Students: create, edit, status change, parent assignment, profile.
- Attendance: present/absent/late/leave and duplicate-date handling.
- Fees: invoice, partial payment, full payment, overpayment rejection, receipt.
- Academics: exam, marks validation, update, report card, grade calculation.
- HR/payroll: employee, monthly payroll, duplicate month update, deductions.
- Operations: transport, hostel capacity, inventory IN/OUT, library return.
- Exports: CSV, XLSX, printable receipt, PDF report card.
- Authorization: admin-only management screens and role portals.

## Production acceptance
- Change default admin password.
- Set a strong `SCHOOL_ERP_SECRET_KEY`.
- Use PostgreSQL/MySQL for multi-user production workloads.
- Run behind HTTPS and a production WSGI server.
- Configure scheduled database backups.
- Review logs and audit records.
- Run full browser/end-to-end tests before go-live.
