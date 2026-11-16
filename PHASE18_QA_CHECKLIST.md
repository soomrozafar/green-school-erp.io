# Phase 18 QA Checklist

## Admissions
- [ ] Create admission with new guardian.
- [ ] Repeat same mobile/CNIC/email and confirm existing guardian is reused.
- [ ] Verify family tree contains all linked children.
- [ ] Verify student code increments without duplication.
- [ ] Select fee structure and verify voucher is generated.

## Roles
- [ ] Admission Officer can access students/admissions/parents/reports/vouchers.
- [ ] Admission Officer cannot access Hostel/Mess/Transport/Inventory.
- [ ] Operations Admin can access only Operations modules from navigation and routes.
- [ ] Accountant can access finance workflows.

## GIS/Transport
- [ ] Set student/guardian location on map.
- [ ] Draw route points and verify saved route geometry.
- [ ] Assign active student to route.

## Finance
- [ ] Voucher displays Student/Bank/School copies.
- [ ] Voucher PDF downloads.
- [ ] Receipt number increments.

## Reports
- [ ] Filter by status.
- [ ] Filter by class.
- [ ] Export filtered CSV.
- [ ] Export filtered XLSX.

## Security
- [ ] Invalid CSRF token rejected.
- [ ] Cross-origin POST rejected.
- [ ] Authenticated responses use no-store.
- [ ] Production HTTPS sets HSTS.

## Database
- [ ] Fresh PostgreSQL migration succeeds.
- [ ] Existing production database backup is taken before migration.
- [ ] No production deployment relies on automatic create_all.
