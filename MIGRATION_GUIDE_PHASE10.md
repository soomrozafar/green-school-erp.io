# Phase 10 Migration Guide

Production deployments should use Flask-Migrate rather than relying on `db.create_all()` for schema changes.

```bash
flask --app run.py db init
flask --app run.py db migrate -m "initial schema"
flask --app run.py db upgrade
```

For an existing production database, review the generated migration before applying it. Keep database backups before every upgrade.

The application retains `db.create_all()` for simple fresh/local installations. A future production hardening step can make migration-only startup mandatory.
