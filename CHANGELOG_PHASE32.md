# Phase 32 - Teacher Subject Assignment Compatibility Fix

- Fixed `sqlite3.IntegrityError: NOT NULL constraint failed: teacher.employee_no` on existing databases.
- Existing legacy `teacher` tables may still contain NOT NULL columns from the old Teacher master. New Teacher assignment now detects those columns and supplies compatible values from the Employee master only when required.
- Employee remains the single source of truth; legacy fields are compatibility-only.
- New/fresh databases continue using the simplified Employee-linked Teacher model.
- Subject assignments continue to use the `teacher_subject` many-to-many table.
- Python compile validation passed.
- ZIP integrity validation passed.
