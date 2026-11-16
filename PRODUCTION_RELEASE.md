# Phase 13 — Production Release Runbook

## 1. Before deployment
- Change the default `admin` password.
- Generate a strong `SCHOOL_ERP_SECRET_KEY`.
- Set `SCHOOL_ERP_SECURE_COOKIES=1`.
- Set `SCHOOL_ERP_AUTO_CREATE_DB=0` for production.
- Configure PostgreSQL/MySQL rather than SQLite for multi-user production.
- Configure HTTPS and an Nginx/reverse proxy.

## 2. Database migration
The application includes Flask-Migrate. Initialize the migration repository once in the source tree if it does not exist:

```bash
flask --app run:app db init
flask --app run:app db migrate -m "Initial schema"
flask --app run:app db upgrade
```

For subsequent model changes:

```bash
flask --app run:app db migrate -m "Describe change"
flask --app run:app db upgrade
```

Review generated migrations before applying them to production.

## 3. Local Windows smoke test
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
$env:SCHOOL_ERP_SECRET_KEY="replace-with-a-long-random-secret"
$env:SCHOOL_ERP_AUTO_CREATE_DB="1"
python run.py
```

## 4. Gunicorn
```bash
gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 120 run:app
```

## 5. Docker Compose
Copy `docker-compose.yml`, replace every `CHANGE_ME_BEFORE_DEPLOYMENT`, then:

```bash
docker compose build
docker compose up -d
```

Run migrations from the web container before first production use:

```bash
docker compose exec web flask --app run:app db upgrade
```

## 6. Operational checks
- Open `/api/v1/health`.
- Login as admin.
- Verify dashboard counts.
- Test one student admission.
- Test one attendance record.
- Test one invoice and payment.
- Test Excel/PDF exports.
- Test backup download where SQLite is used.
- Review `/admin/system/audit` and `/admin/system/login-history`.
- Verify HTTPS, secure cookies, logs and database backups.

## 7. Rollback
Never overwrite a production database blindly. Take a database backup/snapshot before migrations, record the migration revision, and use the database provider's restore procedure if rollback is required.
