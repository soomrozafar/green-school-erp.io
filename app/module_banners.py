from datetime import date


# Endpoint keys keep the banner stable when titles contain a record name.
BANNERS = {
    "main.dashboard": ("School dashboard", "dashboard"),
    "students.new_student": ("New Student Admission", "admissions"),
    "students.list_students": ("Student Directory", "students"),
    "students.attendance": ("Attendance", "attendance"),
    "students.parents": ("Parents & Guardians", "parents"),
    "academics.teachers": ("Teacher Management", "teachers"),
    "academics.exams": ("Exams", "exams"),
    "academics.results": ("Results", "results"),
    "admin.subjects": ("Subjects", "subjects"),
    "finance.fees": ("Fee Management", "fees"),
    "hr.payroll": ("Payroll", "payroll"),
    "reports.index": ("Reports & Analytics", "reports"),
    "notifications.index": ("Notifications", "notifications"),
    "library.books": ("Library Catalogue", "library"),
    "timetable.import_schedule": ("Import timetable", "timetable-import"),
    "hr.teacher_attendance": ("Teacher Attendance", "teacher-attendance"),
    "timetable.index": ("Timetable", "timetable"),
    "operations.transport": ("Transport & Routes", "transport"),
    "operations.inventory": ("Inventory", "inventory"),
    "operations.hostel": ("Hostel", "hostel"),
    "mess.index": ("Mess & Dining", "mess"),
    "operations.transport_assign": ("Transport Assignments", "transport-assignment"),
    "students.id_card": ("Student ID Card", "student-id"),
    "academics.grades": ("Grade Scale", "grades"),
    "operations.dashboard": ("Operations Dashboard", "operations"),
    "portal.index": ("My Portal", "portal"),
    "hr.employees": ("Employee Master", "employees"),
    "online_payments.history": ("Online Fee Payments", "online-fee-history"),
    "online_payments.status": ("Online Payment Status", "online-fee-status"),
    "finance.voucher": ("Fee Voucher", "voucher"),
    "finance.payment": ("Record Payment", "payment"),
    "finance.voucher_batch": ("Challan Batch", "batch-review"),
    "finance.bulk_vouchers": ("Bulk Fee Vouchers", "bulk-vouchers"),
    "finance.structures": ("Fee Structures", "fee-structures"),
    "accounts.collection": ("Fee Collection", "collection"),
    "accounts.dashboard": ("Accounts & Finance", "accounts"),
    "library.issue": ("Library Circulation", "lending"),
    "notifications.whatsapp": ("WhatsApp Notifications", "messages"),
    "admin.banks": ("Bank Accounts", "banks"),
    "admin.classes": ("Classes & Sections", "classes"),
    "admin.data_edit": ("Data Edit Center", "data-edit"),
    "admin.data_edit_record": ("Edit Record", "data-form"),
    "admin.modules": ("System Modules & Integrations", "modules"),
    "admin.permissions": ("Permissions", "permissions"),
    "admin.sessions": ("Academic Sessions", "sessions"),
    "admin.users": ("User Management", "users"),
    "production.login_history": ("Login History", "login-history"),
    "production.integrity": ("Data Integrity", "integrity"),
    "production.backups": ("Database Backups", "backups"),
    "production.system_health": ("System Health", "system-health"),
    "profile.password": ("Change Password", "password"),
    "students.attendance_report": ("Attendance Report", "attendance-report"),
    "academics.teacher_subjects": ("Teacher Subjects", "teacher-subjects"),
    "students.profile": ("Student Profile", "student-profile"),
    "academics.report_card": ("Report Card", "report-card"),
    "students.admission_report": ("Admission Reports", "admission-report"),
    "students.promotion": ("Student Promotion", "promotion"),
    "students.family": ("Family Profile", "family"),
    "students.verify_card": ("Student Card Verification", "card-verification"),
    "admin.data_edit_list": ("Edit Records", "data-list"),
    "production.audit": ("Audit Log", "audit"),
    "students.edit_student": ("Edit Student Record", "edit-student"),
    "finance.generate_voucher": ("Generate Fee Voucher", "generate-voucher"),
    "exports.verify_voucher": ("Voucher Verification", "verify-voucher"),
    "exports.receipt": ("Payment Receipt", "payment-receipt"),
}


def module_banner(endpoint, role):
    if endpoint == "main.dashboard":
        if role == "admission_officer":
            return "Admission Dashboard", "assets/banners/admission-dashboard.webp", date.today()
        if role == "operations_admin":
            endpoint = "operations.dashboard"
    title, image = BANNERS.get(endpoint, ("School ERP", "website"))
    filename = "assets/erp-library.webp" if image == "dashboard" else f"assets/banners/{image}.webp"
    return title, filename, date.today()
