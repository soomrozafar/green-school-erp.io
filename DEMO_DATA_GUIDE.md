# Demo / Dummy Data

This release includes `seed_demo.py` to populate a complete Public School Gadap ERP test environment.

## What it creates
- Role-based demo users
- Academic session, classes and sections
- Subjects and teacher-subject assignments
- Employee master for teachers and non-teaching staff
- Parent/family records with sibling relationships
- 10 demo students
- Student portal login
- Attendance history
- Exam and results
- Fee structures, invoices, invoice items and payments
- Library books and issued books
- Timetable
- Transport vehicle, route and assignments
- Hostel rooms and allocations
- Inventory items and stock transactions
- Mess menus
- Payroll
- Grade scales
- Notifications, audit/login history
- Promotion/status history
- Bank account
- Prepared WhatsApp messages
- Demo permissions
- Enables optional modules so the full ERP can be demonstrated

## Run
From the project root:

```bash
python seed_demo.py
```

The seeder does **not delete existing data**. It uses a system-setting marker (`demo.seed.v1`) so a second run will not duplicate the demo dataset.

### Demo accounts
All demo passwords are:

Use the password entered when running the seeder. Reset existing demo passwords from Admin > Users or remove unused demo accounts.

| Username | Role |
|---|---|
| admin_demo | Admin |
| accountant_demo | Accountant |
| admission_demo | Admission Officer |
| staff_demo | Staff |
| teacher_demo | Teacher |
| student_demo | Student |

For a production deployment, use a separate test database and change/remove these demo accounts after testing.
