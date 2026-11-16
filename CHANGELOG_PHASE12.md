# Phase 12 Changelog

## Security & Administration
- Added persistent login event history for successful and failed logins.
- Added admin audit log viewer.
- Added data integrity checks for common fee, student, inventory, hostel and transport issues.
- Added admin backup management screen.

## Backup & Operations
- Added SQLite backup listing and safe download route.
- Existing SQLite backup endpoint remains available.
- Added system health and operational visibility.

## API
- Added `/api/v1/metrics` for authenticated ERP KPIs.

## QA
- Source compilation and archive integrity were validated during package creation.
- Live Flask/pytest execution still requires installing the project's dependencies in the target environment.
