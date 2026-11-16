# Phase 40 — Fee Voucher Logo + QR Rendering Fix

## Fixed
- Fee voucher logo is now rendered from `app/static/assets/school-logo.png` as a fresh ReportLab Image for every copy.
- QR is generated as a real PNG in memory using `qrcode`, then embedded as a ReportLab Image.
- This avoids nested ReportLab `QrCodeWidget` rendering issues in some PDF builds.
- Student, Bank, and School copies each receive their own logo and QR image.
- Bulk voucher PDF uses the same corrected renderer.
- Added `qrcode==8.2` dependency.

## QR destination
The QR contains the signed public voucher verification URL:
`/exports/verify-voucher/<invoice_no>?token=<signed-token>`

## Existing database
No database deletion or reset is required.
