# Phase 12 Final Checklist

- [x] Admin audit viewer with pagination
- [x] Login success/failure history
- [x] SQLite backup creation and backup listing/download
- [x] Read-only data integrity checks
- [x] API metrics endpoint
- [x] Login event persistence
- [x] Administration navigation for Phase 12 tools
- [x] Python source compilation
- [x] ZIP integrity validation

## Before production
- Change the default admin password immediately.
- Set a strong `SCHOOL_ERP_SECRET_KEY`.
- Use HTTPS and `SCHOOL_ERP_SECURE_COOKIES=1`.
- Configure PostgreSQL/MySQL for multi-user production workloads.
- Run `flask --app run.py db migrate` / `db upgrade` according to the migration guide after reviewing generated migrations.
- Schedule external database backups for non-SQLite production databases.
- Run the full pytest suite on a machine with dependencies installed.
