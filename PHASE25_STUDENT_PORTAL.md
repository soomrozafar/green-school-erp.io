# Phase 25 — Student Portal

## Student self-service
- Dedicated `student` role linked to exactly one Student record.
- Student login redirects directly to the Student Portal.
- Students can view only their own:
  - results and report cards
  - attendance summary and recent attendance
  - fee invoices, paid amount and outstanding amount
  - class timetable
  - school announcements
  - library issues
  - transport assignment when Transport is enabled
  - hostel/boarding allocation when Hostel is enabled
  - student ID card
  - password change
- Server-side ownership checks prevent a student from opening another student's report card or ID card by URL.

## Student account management
- Admin > Users can create a `student` user and link it to an active student.
- One portal account is allowed per student.
- Student passwords require the existing minimum of 8 characters.
- `student_id` is added to User and is also handled by the additive schema upgrade for existing databases.

## Security
- Student portal does not expose global search, finance management, attendance entry, admissions, HR, admin or other operational modules.
- Module-specific transport/hostel information respects the ERP module toggles.

## QA
- Python compileall validation: passed.
- Runtime Flask/pytest execution was not available in the build environment because Flask dependencies were not installed; perform full runtime QA after installing `requirements.txt` and connecting the target database.
