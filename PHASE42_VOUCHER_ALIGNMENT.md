# Phase 42 — Fee Voucher Alignment + Transparent Logo

## Changes
- Reworked the 3-column A4 fee voucher header so logo, school title and QR stay inside each copy's column.
- Fixed header column widths that previously exceeded the available voucher-copy width and caused QR/logo overlap into adjacent copies.
- Kept QR as a real PNG image generated in memory for reliable ReportLab rendering.
- Increased/standardized logo and QR sizing while keeping the layout compact.
- Removed the pale background around the school crest by converting the background to transparency and cropping the asset to the crest.
- Tightened info/amount table widths and typography for consistent alignment.
- Student, Bank and School copies retain the same voucher data and QR verification URL.
- Bulk voucher generation continues to use the same layout.

## Validation
- Python compileall passed.
- Standalone ReportLab render test passed and was visually inspected for 3-column alignment, logo, and QR placement.
- Existing database is not modified by these changes.
