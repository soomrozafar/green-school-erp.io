# School Management ERP — Phase 2

Python + Flask + SQLAlchemy + SQLite + HTML/CSS/JavaScript + Bootstrap.

### Added in Phase 2
- Academic sessions
- Classes and sections
- Subjects
- Parent records model
- Relational student/class/parent structure
- User management with roles
- Timetable management
- Teacher designations
- Exam/session/class relationships

### Run
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py

Open http://127.0.0.1:5001
Create the first administrator or reset the former default administrator password with:

    python -m flask --app run set-admin-password

Local startup generates a persistent key in instance/session-secret when SCHOOL_ERP_SECRET_KEY is unset. Keep that file private. For HTTPS deployments set SCHOOL_ERP_SECRET_KEY to a randomly generated value of at least 32 characters and set SCHOOL_ERP_SECURE_COOKIES=1.

The updated session format requires users to sign in again. If the app was using the former built-in key, regenerate verification vouchers and ID cards that were signed with it.

### Important
For an existing database, back it up before applying schema migrations.
For production, use Flask-Migrate/Alembic migrations, environment variables for secrets, CSRF protection, PostgreSQL/MySQL, granular permissions, audit logs, backups, HTTPS and automated tests.

## Phase 3 — Finance, Payments, Reports & Notifications

Added:
- Fee payment workflow with automatic invoice balance/status update.
- Receipt number generation and payment history.
- Management dashboard reports for students, teachers, fees and attendance.
- Notification publishing with audience selection.
- Finance/communication audit log entries.

Important: this project currently uses `db.create_all()` for simplicity. Before production, migrate to Flask-Migrate/Alembic and use PostgreSQL/MySQL, environment-based secrets, CSRF protection, granular permissions, backups and automated tests.

## Phase 5 additions
- Exam management with academic session/class relationships
- Marks entry with validation and update support
- Subject-based results and printable report card
- Configurable grade scale
- Employee/HR management
- Payroll processing with basic salary, allowances, deductions and net salary

### New routes
- `/academics/exams`
- `/academics/results`
- `/academics/report-card/<student_id>/<exam_id>`
- `/academics/grades`
- `/hr/employees`
- `/hr/payroll`

> For a fresh development database, delete the old SQLite database before first run because the project currently uses `db.create_all()` rather than database migrations.

## Phase 7 additions
- Role-aware portal dashboard at `/portal/`
- Password change workflow with minimum 8-character validation
- Permission model foundation (`Permission`) and reusable permission decorator
- CSV exports for students, fee invoices, and employees
- Printable fee receipt route `/exports/receipt/<payment_id>`
- Safer session cookie configuration and environment-based secret key (`SCHOOL_ERP_SECRET_KEY`)

Production note: move to PostgreSQL/MySQL, Flask-Migrate/Alembic, CSRF protection, HTTPS, rate limiting, centralized logging, and automated tests before public deployment.


## Phase 13 Production Release
See `PRODUCTION_RELEASE.md` and `PHASE13_FINAL_QA.md` for the deployment runbook and final verification checklist. For local development, keep `SCHOOL_ERP_AUTO_CREATE_DB=1`; for production, use migrations with `SCHOOL_ERP_AUTO_CREATE_DB=0`.

## ERP assistant

Open Assistant after signing in. Common English and Roman Urdu workflow questions work with the built-in command matching. Examples include "Attendance today", "New admission", "Outstanding fees", and "Bulk vouchers". Available answers and shortcuts depend on the signed-in account's role.

When the Windows portable runtime and qwen2.5:0.5b are present under instance/ollama, run.py starts the local Ollama service automatically and the Assistant shows Ollama configured. The bundled service uses CPU inference, binds to localhost, and has cloud features disabled. If startup fails, check instance/ollama/server.log. Built-in commands still work.

To use an existing Ollama service and a different local model, start that service and set the installed model name in the PowerShell window that starts Flask:

    $env:SCHOOL_ERP_OLLAMA_MODEL = "<installed-model-name>"
    .\venv\Scripts\python.exe run.py

The app sends unmatched question text and the allowed action names to Ollama's local chat endpoint at 127.0.0.1:11434. It calculates ERP totals itself. The assistant looks up aggregates and opens workflow screens. Users complete record changes in those screens.

## Online fee payments through Safepay

The student portal can send the outstanding balance of an invoice to Safepay's hosted checkout. Accounts staff can review attempts under Fee Management > Online Payments. A local sandbox checkout can be tried from Windows without a public webhook. Stop the ERP before running the following in PowerShell. Use Developer > API Keys in Safepay's TEST MODE dashboard. The private key prompt masks input.

    cd C:\SchoolManagementERP
    $env:SCHOOL_ERP_PORT = '5004'
    $env:SAFEPAY_ENVIRONMENT = 'sandbox'
    $env:SCHOOL_ERP_PUBLIC_URL = 'http://127.0.0.1:5004'
    $env:SAFEPAY_PUBLIC_KEY = Read-Host 'Safepay sandbox public API key'
    $env:SAFEPAY_SECRET_KEY = [pscredential]::new('Safepay', (Read-Host 'Safepay sandbox secret API key' -AsSecureString)).GetNetworkCredential().Password
    .\venv\Scripts\python.exe run.py

Sign in as a student with an unpaid invoice. Choose Test payment, use the provider's sandbox test card, then select Verify test payment on the return screen. The ERP queries Safepay directly with the server key. If the browser does not return automatically, return to the Student Portal and select Check status next to the invoice.

Production requires a Safepay live merchant account and a public HTTPS ERP URL with a signed webhook.

Set these variables on the ERP server, keeping all secret values in the deployment environment:

    SAFEPAY_ENVIRONMENT=sandbox
    SAFEPAY_PUBLIC_KEY=<sandbox public API key>
    SAFEPAY_SECRET_KEY=<sandbox secret API key>
    SAFEPAY_WEBHOOK_SECRET=<sandbox endpoint signing secret>
    SCHOOL_ERP_PUBLIC_URL=https://<school-erp-host>

Register the HTTPS endpoint /payments/safepay/webhook in the matching Safepay dashboard for payment success, refund and void events. Sandbox confirmations are shown as test payments and never change invoice balances or create receipts. Verify the complete sandbox flow before switching to production credentials and a production webhook. The ERP records a live receipt after validating the signed capture and matching both the currency and amount. Refunds, voids and balance discrepancies are flagged for Accounts review.

The online_fee_payment table is created by the ERP's standard local database initialization. Deployments with automatic table creation disabled must apply the matching schema migration before enabling checkout.
