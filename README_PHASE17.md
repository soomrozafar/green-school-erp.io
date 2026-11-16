# Public School Gadap ERP — Phase 17

Phase 17 extends the ERP with admission/family workflows, GIS-ready addresses, mapped transport routes, role separation, fee vouchers and PostgreSQL production support.

## Local Windows
```powershell
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
$env:SCHOOL_ERP_SECRET_KEY="replace-with-a-long-random-secret"
$env:SCHOOL_ERP_SECURE_COOKIES="0"
python run.py
```

## PostgreSQL
Set:
```text
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/schoolerp
SCHOOL_ERP_AUTO_CREATE_DB=0
SCHOOL_ERP_AUTO_SCHEMA_UPGRADE=1
SCHOOL_ERP_SECURE_COOKIES=1
```
Run migrations/approved schema upgrades in staging first. For a fresh deployment, the application's table creation can be used only for development; production should use a controlled migration process.

## New roles
- `admin` — full administration
- `admission_officer` — admissions, family records and admission reporting/vouchers
- `operations_admin` — Hostel, Mess, Transport and Inventory
- existing academic/finance/library roles remain available

## Map provider
The admission and transport screens use Leaflet with OpenStreetMap tiles. Address lookup is user-initiated and optional; manual map pinning remains available if geocoding is unavailable.
