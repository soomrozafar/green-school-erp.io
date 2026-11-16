# Phase 17 Database Migration

## Existing Phase 16 SQLite database
For a local upgrade, keep:
```text
SCHOOL_ERP_AUTO_CREATE_DB=1
SCHOOL_ERP_AUTO_SCHEMA_UPGRADE=1
```
Start the application once. The additive compatibility upgrade creates the new Phase 17 columns and tables. Back up `instance/school.db` first.

## PostgreSQL production
Do not rely on automatic schema mutation in production. Set:
```text
SCHOOL_ERP_AUTO_CREATE_DB=0
SCHOOL_ERP_AUTO_SCHEMA_UPGRADE=0
```
Use the approved migration process in staging, verify the database, then promote the migration to production.

Required additions:
- `parent.mobile`
- `parent.cnic`
- `parent.latitude`
- `parent.longitude`
- `student.latitude`
- `student.longitude`
- `transport_route.map_points`
- `mess_menu` table
- `sequence_counter` table

Back up the database before applying changes.
