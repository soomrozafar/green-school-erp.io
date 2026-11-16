# Phase 17 — Admissions, Family, GIS, Operations & Production Standards

## Implemented
- Automatic student code: `STD-YYYY-00001`
- Automatic invoice code: `INV-YYYY-00001`
- Automatic receipt code: `RCPT-YYYY-00001`
- Automatic employee code: `EMP-YYYY-00001`
- Guardian lookup by mobile/phone/email/CNIC
- Reuse of an existing guardian record instead of duplicate creation
- Family tree showing all students linked to the same guardian
- Guardian CNIC, mobile, email and address fields
- Student and guardian latitude/longitude
- OpenStreetMap/Leaflet address map and manual pinning
- Transport route map with ordered pickup points and polyline
- Hostel, Mess, Transport and Inventory restricted to `operations_admin`
- Admission Officer workflow for student admission and admission voucher generation
- Three-copy fee voucher: Student Copy, Bank Copy, School Copy
- PDF voucher download
- Filtered reporting with CSV/XLSX download options
- PostgreSQL connection support and Docker PostgreSQL stack
- Additive schema compatibility migration for Phase 17 fields
- Browser CSRF token plus same-origin protection
- Failed-login throttling (5 failed attempts / 15 minutes per username)
- Password minimum of 8 characters for newly-created users
- Audit/role separation foundation

## Security standards applied
- Least-privilege role separation
- Server-side validation for phone/CNIC
- Unique generated financial/student identifiers
- Audit trail retained for student status changes
- Secure session cookie configuration inherited from production configuration
- Security headers inherited from previous phases
- PostgreSQL supported for multi-user deployment
- No CNIC/password values are written to application logs

## Data/privacy note
CNIC, mobile, email, address and student location are personal data. Production access should be restricted by role, database credentials should be kept in environment variables, backups should be encrypted and access should be limited to authorized school staff.
