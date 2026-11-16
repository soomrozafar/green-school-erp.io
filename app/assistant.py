from datetime import date
from sqlalchemy import or_
import json
import os
from config import ollama_address
import re
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

from flask import Blueprint, abort, current_app, jsonify, request, url_for
from flask_login import current_user, login_required

from .extensions import db
from .notifications import announcements, support_url
from .access import module_enabled
from .models import Attendance, Exam, FeeInvoice, FeePayment, Result, Student, TeacherAttendance

assistant_bp = Blueprint("assistant", __name__)
ADMISSIONS = {"admin", "admission_officer", "staff"}
ATTENDANCE = {"admin", "teacher", "staff"}
FINANCE = {"admin", "accountant"}
REPORTS = {"admin", "accountant", "teacher", "staff"}
GRADES = {"admin", "teacher"}

ACTIONS = {
    "admission_review": (ADMISSIONS, "Review students", "students.list_students", "Check admissions and incomplete student records."),
    "overdue": (FINANCE, "Review overdue invoices", "finance.fees", "Review past-due invoices with an outstanding balance."),
    "grades": (GRADES, "Open results", "academics.results", "Check exams that still need marks."),
    "admission": (ADMISSIONS, "New admission", "students.new_student", "Open the new student form."),
    "students": (ADMISSIONS | ATTENDANCE, "Student directory", "students.list_students", "Find students by name or admission number."),
    "timetable_import": ({"admin", "staff"}, "Import timetable", "timetable.import_schedule", "Upload a timetable or paste rows, then review clashes before saving."),
    "course_allocation": ({"admin", "staff"}, "Import subject assignments", "academics.import_allocations",
                          "Upload Excel, CSV or a document, or paste one teacher and subject per row. Review the matched records and confirm to add the assignments."),
    "communication": ({"admin", "staff", "principal", "vice_principal"}, "Manage announcements", "notifications.index",
                      "Choose an audience, publish the notice and archive it when it is no longer relevant."),
    "whatsapp_drafts": ({"admin", "staff", "accountant", "admission_officer"}, "Prepare WhatsApp drafts", "notifications.whatsapp",
                        "Select recipients and prepare drafts. Open WhatsApp to send each draft."),
    "family_portal": ({"parent"}, "My family portal", "portal.index", "Open your portal to see linked children and recent fee invoices."),
    "teacher_portal": ({"teacher"}, "My teacher portal", "portal.index", "Open My Portal to see the timetable assigned to your teacher profile."),
    "contact_school": ({"student", "parent", "teacher"}, "School support", "portal.index",
                       "Use Administrator WhatsApp in your portal to contact the school."),
    "mess": ({"admin", "operations_admin"}, "Mess & Dining", "mess.index",
             "Create a meal plan or open an existing record to update menu and estimated cost."),
    "hostel": ({"admin", "operations_admin"}, "Hostel", "operations.hostel",
               "Open Hostel to manage rooms, bed capacity and student allocations."),
    "inventory": ({"admin", "operations_admin"}, "Inventory", "operations.inventory",
                  "Open an item to edit its details. Record stock movements using the stock transaction form."),
    "library": ({"admin", "librarian"}, "Library", "library.books",
                "Search the catalogue by title, author or ISBN. Open Issue / Return to record a loan."),
    "leave": ({"admin", "hr_officer", "principal", "vice_principal"}, "Staff leave", "hr.leave",
              "Select an employee and date range, then submit leave for review."),
    "payroll": (FINANCE, "Payroll", "hr.payroll",
                "Load the employee and month to see approved leave and calculate payroll."),
    "transport": ({"admin", "operations_admin"}, "Transport", "operations.transport",
                  "Set up the vehicle and route, then allocate students to a route."),
    "teacher_attendance": ({"admin", "staff"}, "Teacher attendance", "hr.teacher_attendance", "Choose a date and review each teacher's status before saving."),
    "timetable_view": (ATTENDANCE, "View timetable", "timetable.index", "Open the scheduled classes and assigned teachers."),
    "attendance": (ATTENDANCE, "Mark attendance", "students.attendance", "Choose a class and date to record attendance."),
    "payment": (FINANCE, "Record a payment", "finance.payment", "Open the fee payment form."),
    "balance": (FINANCE, "Fee balances", "finance.fees", "Review invoices and balances."),
    "system_review": ({"admin"}, "Open ERP health review", "production.integrity", "Check data quality and prepare a Codex request."),
    "vouchers": (FINANCE | {"admission_officer"}, "Bulk vouchers", "finance.bulk_vouchers", "Select a class and fee month for bulk vouchers."),
    "reports": (REPORTS, "Reports", "reports.index", "Open the reports workspace."),
    "portal": ({"student"}, "My student portal", "portal.index", "Open your attendance, results and invoices."),
    "password": ({"student", "admin", "teacher", "staff", "accountant", "admission_officer",
                  "operations_admin", "librarian", "parent"},
                 "Change password", "profile.password", "Open your account password settings."),
}
TRIGGERS = {
    "contact_school": ("contact administrator", "contact admin", "administrator whatsapp", "contact school", "school contact", "admin se baat"),
    "communication": ("announcement", "announcements", "notification", "notifications", "notice", "notices"),
    "whatsapp_drafts": ("whatsapp", "message parents"),
    "family_portal": ("my child", "my children", "family portal", "parent portal", "child fees", "mere bachay"),
    "teacher_portal": ("my timetable", "teacher portal", "my schedule"),
    "mess": ("mess", "dining", "meal plan"),
    "hostel": ("hostel", "boarding"),
    "inventory": ("inventory", "stock"),
    "library": ("library", "book loan"),
    "leave": ("leave", "chutti"),
    "payroll": ("payroll", "payslip", "salary", "bonus"),
    "transport": ("transport", "bus", "vehicle"),
    "password": ("password", "passcode", "login credentials"),
    "overdue": ("overdue", "past due", "late fees"),
    "admission_review": ("admissions today", "admission review", "missing guardian", "incomplete admissions", "dakhla report"),
    "portal": ("my results", "my grades", "portal"),
    "grades": ("grades", "marks", "results", "result", "grade", "number lagana"),
    "balance": ("outstanding", "balance", "pending fees", "baqaya", "baqi", "due fees"),
    "vouchers": ("voucher", "vouchers", "challan", "challans", "bulk fees"),
    "system_review": ("system health", "performance", "software issues", "data integrity", "codex request", "improve software"),
    "payment": ("payment", "payments", "collect fee", "jama"),
    "teacher_attendance": ("teacher attendance", "teachers attendance", "staff attendance", "teacher hazri"),
    "course_allocation": ("course allocation", "subject allocation", "assign subjects", "teacher allocation", "import subjects", "import teacher subjects", "subject allow"),
    "timetable_import": ("import timetable", "create timetable", "timetable import", "timetable bana", "upload timetable"),
    "timetable_view": ("timetable", "schedule"),
    "attendance": ("attendance", "hazri", "haazri", "roll call", "absences"),
    "admission": ("admission", "admissions", "new student", "dakhla"),
    "reports": ("report", "reports", "school analytics"),
    "students": ("student", "students", "directory", "talib"),
}


def available_actions(role):
    options = {key: action for key, action in ACTIONS.items() if role in action[0]}
    if current_user.is_authenticated and current_user.family_or_demo_teacher:
        options = {key: action for key, action in options.items()
                   if key in ("family_portal", "teacher_portal", "contact_school", "password")}
    for key in ("mess", "inventory", "library", "hostel", "transport"):
        if key in options and not module_enabled(key, key != "hostel"):
            del options[key]
    return options


def ollama_model():
    return os.environ.get("SCHOOL_ERP_OLLAMA_MODEL", "").strip()


def classify_locally(question, options):
    model = ollama_model()
    if not model:
        return None
    action_schema = {
        "type": "object",
        "properties": {"action": {"type": "string", "enum": [*options, "unknown"]}},
        "required": ["action"],
        "additionalProperties": False,
    }
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": (
                "Match a school ERP request in English or Roman Urdu to one workflow. "
                "Use unknown for unrelated requests. Return JSON with one action key. "
                "Roll call, absences and class presence refer to attendance. "
                "Looking up a name or admission number refers to the student directory. "
                "If the matching workflow is unavailable, use unknown. Available workflows: "
                + "; ".join(f"{key}: {action[1]}. {action[3]}" for key, action in options.items())
            )},
            {"role": "user", "content": question},
        ],
        "format": action_schema,
        "stream": False,
        "options": {"num_predict": 48, "temperature": 0},
    }).encode()
    call = Request(f"http://{ollama_address()}/api/chat", data=payload,
                   headers={"Content-Type": "application/json"})
    try:
        with build_opener(ProxyHandler({})).open(call, timeout=20) as response:
            result = json.loads(response.read(16384))
        action = json.loads(result["message"]["content"]).get("action")
        return action if isinstance(action, str) and action in options else None
    except (OSError, URLError, ValueError, TypeError, KeyError, AttributeError):
        current_app.logger.info("Local assistant model unavailable or returned an invalid action.")
        return None


def answer(key, fallback):
    if key == "vouchers":
        return ("Select the students, fee items and billing months, then generate the batch. "
                "Open each student's WhatsApp draft and attach only that student's PDF. "
                "Rows with no valid number need a contact update before sharing.")
    if key == "system_review":
        from .production import integrity_checks

        failed = sum(not passed for _, passed, _ in integrity_checks())
        return f"{failed} data integrity checks need review. Open the report for details and a development request you can copy to Codex."
    if key == "admission":
        return "Before starting, have the student's date of birth, class, admission date and guardian contact or ID ready."
    if key == "admission_review":
        today = Student.query.filter_by(admission_date=date.today()).count()
        incomplete = admission_gaps().count()
        return f"{today:,} admissions recorded today. {incomplete:,} active student records are missing a class or guardian."
    if key == "overdue":
        invoices = overdue_invoices()
        amount = invoices.with_entities(
            db.func.coalesce(db.func.sum(FeeInvoice.amount - db.func.coalesce(FeeInvoice.paid, 0)), 0)
        ).scalar()
        return f"{invoices.count():,} overdue invoices have PKR {amount:,.2f} remaining."
    if key == "grades":
        pending = exams_without_results().count()
        return f"{pending:,} finished exams have no marks recorded. Open Results to check the exam and enter marks."
    if key == "balance":
        billed = db.session.query(db.func.coalesce(db.func.sum(FeeInvoice.amount), 0)).scalar()
        collected = db.session.query(db.func.coalesce(db.func.sum(FeePayment.amount), 0)).scalar()
        return f"Total outstanding fees across the school are PKR {max(billed - collected, 0):,.2f}."
    if key == "students":
        active = Student.query.filter_by(status="Active").count()
        return f"There are {active:,} active students. Open the directory to find a record."
    if key == "teacher_attendance":
        totals = dict(db.session.query(TeacherAttendance.status, db.func.count(TeacherAttendance.id))
                      .filter(TeacherAttendance.date == date.today()).group_by(TeacherAttendance.status).all())
        if not totals:
            return "No teacher attendance has been entered today. Open the roster to start."
        return f"Today: {totals.get('Present', 0)} present, {totals.get('Late', 0)} late, {totals.get('Absent', 0)} absent and {totals.get('Leave', 0)} on leave."
    if key == "attendance":
        today = Attendance.query.filter_by(date=date.today())
        total = today.count()
        if total:
            present = today.filter(Attendance.status.in_(("Present", "Late"))).count()
            return f"Today, {present:,} of {total:,} students with recorded attendance are present or late."
        return "No attendance has been recorded today. Open attendance to select a class."
    return fallback



def admission_gaps():
    return Student.query.filter(
        Student.status == "Active", or_(Student.class_id.is_(None), Student.parent_id.is_(None)),
    )


def overdue_invoices():
    return FeeInvoice.query.filter(
        FeeInvoice.due_date < date.today(),
        FeeInvoice.amount > db.func.coalesce(FeeInvoice.paid, 0),
    )


def exams_without_results():
    return Exam.query.filter(
        Exam.end_date < date.today(),
        ~db.session.query(Result.id).filter(Result.exam_id == Exam.id).exists(),
    )


def action_link(key, action):
    query = {"overdue": {"overdue": 1}, "admission_review": {"incomplete": 1}}
    if key == "contact_school":
        link = support_url()
        if link:
            return {"label": "Open Administrator WhatsApp", "url": link}
    return {"label": action[1], "url": url_for(action[2], **query.get(key, {}))}


@assistant_bp.get("/assistant/overview")
@login_required
def overview():
    role = current_user.role
    options = available_actions(role)
    cards = []
    for key, title, suggestion in (
        ("admission_review", "Admissions", "Review missing class and guardian details before preparing class lists."),
        ("overdue", "Fees", "Check the due date and record any recent payment before following up."),
        ("grades", "Grades", "Start with finished exams that still have no marks."),
        ("vouchers", "Bulk challans", "Review contacts and download one student PDF at a time for WhatsApp."),
        ("system_review", "ERP health", "Review issues and copy a development request to Codex."),
    ):
        if key in options:
            summary = options[key][3] if key == "vouchers" else answer(key, options[key][3])
            cards.append({"title": title, "summary": summary,
                          "suggestion": suggestion, "action": action_link(key, options[key])})

    notices = announcements(role, limit=5)
    return jsonify(cards=cards, notices=[{"title": n.title, "message": n.message} for n in notices])


@assistant_bp.post("/assistant")
@login_required
def ask():
    options = available_actions(current_user.role)
    if not options:
        abort(403)
    question = request.form.get("question", "").strip()
    if not 1 <= len(question) <= 280:
        return jsonify(message="Enter a question of up to 280 characters.", actions=[]), 400

    normalized = " ".join(re.findall(r"\w+", question.lower()))
    recognized = [key for key, phrases in TRIGGERS.items()
                  if any(f" {phrase} " in f" {normalized} " for phrase in phrases)]
    matched = next((key for key in recognized if key in options), None)
    key = matched
    if key is None and current_user.role in ("student", "parent", "teacher"):
        portal_key = {"student": "portal", "parent": "family_portal", "teacher": "teacher_portal"}[current_user.role]
        aliases = {"student": ("result", "marks", "fees", "attendance", "timetable", "challan", "hazri"),
                   "parent": ("fee", "fees", "challan", "child", "bachay"),
                   "teacher": ("timetable", "schedule")}[current_user.role]
        if set(normalized.split()).intersection(aliases):
            matched = key = portal_key
    if key is None and not recognized:
        key = classify_locally(question, options)
    if key:
        fallback = options[key][3]
        if key == "contact_school" and not support_url():
            fallback = "The school WhatsApp number has not been configured. Contact the school office."
        return jsonify(
            message=answer(key, fallback),
            actions=[action_link(key, options[key])],
            source="ollama" if matched is None else "builtin",
        )
    return jsonify(
        message="Try one of the workflows available to your account.",
        source="suggestions",
        actions=[action_link(key, action) for key, action in options.items()],
    )
