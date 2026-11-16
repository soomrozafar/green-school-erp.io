# Phase 17 QA Checklist

## Admissions
- [ ] New admission automatically receives a unique student code.
- [ ] Duplicate student code cannot be created.
- [ ] Required admission fields validate correctly.
- [ ] Invalid phone/CNIC is rejected without a 500 error.
- [ ] Existing guardian is found by mobile.
- [ ] Existing guardian is found by email.
- [ ] Existing guardian is found by CNIC.
- [ ] Second/third child links to the same guardian.
- [ ] Family tree displays all linked children.
- [ ] Student map stores latitude/longitude.

## Finance
- [ ] Invoice number auto-generates uniquely.
- [ ] Admission fee structure can create a voucher automatically.
- [ ] Voucher displays Student/Bank/School copies.
- [ ] Voucher prints cleanly.
- [ ] Voucher PDF downloads.
- [ ] Receipt number auto-generates uniquely.
- [ ] Payment cannot exceed invoice balance.

## Transport/GIS
- [ ] Route can be created.
- [ ] Pickup points can be mapped in order.
- [ ] Route polyline is visible.
- [ ] Student route assignment works.
- [ ] Student/home coordinates display on profile map.

## Roles
- [ ] Admin has full administration access.
- [ ] Admission Officer sees admissions/family/report functions only.
- [ ] Operations Admin sees Hostel, Mess, Transport and Inventory only.
- [ ] Operations Admin is redirected to Operations Dashboard.
- [ ] Direct URL access to restricted modules is denied.

## Reports
- [ ] Status filter works.
- [ ] Class filter works.
- [ ] CSV export works.
- [ ] XLSX export works.

## Security
- [ ] CSRF token is required for browser form POST requests.
- [ ] Cross-origin POST is rejected.
- [ ] Five failed logins trigger temporary throttling.
- [ ] New user password must be at least 8 characters.
- [ ] Production uses HTTPS and secure cookies.
- [ ] Production uses PostgreSQL.

## Deployment
- [ ] `DATABASE_URL` points to PostgreSQL.
- [ ] `SCHOOL_ERP_SECRET_KEY` is a strong random value.
- [ ] `SCHOOL_ERP_SECURE_COOKIES=1` is enabled behind HTTPS.
- [ ] Database backup is tested before migration.
- [ ] Full end-to-end tests are executed in a staging environment.
