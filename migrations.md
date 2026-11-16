# Database Migration Readiness

The application currently keeps `db.create_all()` for simple local setup. Phase 8 adds Flask-Migrate as the supported production migration path.

Recommended production workflow:

```bash
flask --app run.py db init
flask --app run.py db migrate -m "initial schema"
flask --app run.py db upgrade
```

For future schema changes:

```bash
flask --app run.py db migrate -m "describe change"
flask --app run.py db upgrade
```

Before production deployment, create a database backup and review generated migration scripts.
