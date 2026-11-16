# Phase 39 QA Checklist

## Fee Voucher
- [x] School logo asset exists in app/static/assets/school-logo.png
- [x] Each Student/Bank/School copy creates its own ReportLab logo flowable
- [x] Each copy creates its own QR Drawing
- [x] QR encodes the signed voucher verification URL
- [x] Verification endpoint validates the HMAC token before displaying data
- [x] Verification page displays school logo and voucher details
- [x] Bulk vouchers use the same voucher builder

## Attendance
- [x] Selecting a class submits the filter form automatically
- [x] Changing date also submits the filter form automatically
- [x] No Load button is required
- [x] Existing attendance statuses are loaded for the selected date
- [x] Save remains a separate POST action

## Validation
- [x] Python compile validation
- [x] ZIP integrity validation
- [ ] Full runtime Flask/PostgreSQL test requires the project's installed dependencies and database
