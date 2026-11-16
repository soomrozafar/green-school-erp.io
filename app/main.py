from datetime import date, datetime, time, timedelta
from flask import Blueprint, Response, jsonify, redirect, render_template, request, url_for
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from .extensions import db
from .assistant import ADMISSIONS, ATTENDANCE, FINANCE
from .models import Student, Teacher, FeeInvoice, FeePayment, Book, Employee, Attendance, AuditLog, Notification

main_bp = Blueprint("main", __name__)

@main_bp.get("/")
def index():
    return redirect(url_for("main.dashboard" if current_user.is_authenticated else "auth.login"))


@main_bp.get("/robots.txt")
def robots_txt():
    return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    from flask import redirect, url_for
    from flask_login import current_user
    if current_user.role == "student" or current_user.family_or_demo_teacher:
        return redirect(url_for("portal.index"))
    if current_user.role == "operations_admin":
        return redirect(url_for("operations.dashboard"))
    if current_user.role == "admission_officer":
        from .models import Parent
        admissions_today = Student.query.filter(Student.admission_date == date.today()).count()
        active = Student.query.filter_by(status="Active").count()
        families = Parent.query.count()
        return render_template("admission_dashboard.html", admissions_today=admissions_today, active_students=active, families=families, recent_students=Student.query.order_by(Student.id.desc()).limit(8).all())
    today = date.today()
    active_students = Student.query.filter_by(status="Active").count()
    attendance_total = Attendance.query.count()
    attendance_present = Attendance.query.filter(Attendance.status.in_(["Present", "Late"])).count()
    attendance_pct = round((attendance_present / attendance_total) * 100, 1) if attendance_total else 0
    can_view_finance = current_user.role in FINANCE
    finance = None
    if can_view_finance:
        billed = db.session.query(func.coalesce(func.sum(FeeInvoice.amount), 0)).scalar()
        collected = db.session.query(func.coalesce(func.sum(FeePayment.amount), 0)).scalar()
        collections = []
        end = today.replace(day=1)
        end = (end + timedelta(days=32)).replace(day=1)
        for _ in range(6):
            month = (end - timedelta(days=1)).replace(day=1)
            amount = db.session.query(func.coalesce(func.sum(FeePayment.amount), 0)).filter(
                FeePayment.paid_at >= datetime.combine(month, time.min),
                FeePayment.paid_at < datetime.combine(end, time.min),
            ).scalar()
            collections.append((month.strftime("%b %Y"), float(amount)))
            end = month
        finance = {
            "collected": collected,
            "outstanding": max(billed - collected, 0),
            "invoice_count": FeeInvoice.query.count(),
            "collections": list(reversed(collections)),
            "peak": max(1, *(amount for _, amount in collections)),
            "payments": FeePayment.query.order_by(FeePayment.paid_at.desc()).limit(6).all(),
        }
    statuses = db.session.query(Student.status, func.count(Student.id)).group_by(Student.status).all()
    statuses = sorted(((label or "Unspecified", count) for label, count in statuses),
                      key=lambda item: (-item[1], item[0]))
    recent_audit = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(6).all() if current_user.role == "admin" else []
    return render_template(
        "dashboard.html", today=today, students=sum(count for _, count in statuses),
        active_students=active_students, teachers=Teacher.query.count(),
        employees=Employee.query.count(), attendance_pct=attendance_pct,
        attendance_total=attendance_total, statuses=statuses, finance=finance,
        recent_audit=recent_audit,
    )

@main_bp.route("/search")
@login_required
def global_search():
    role = current_user.role
    q = request.args.get("q", "").strip()[:80]
    results = {"query": q, "students": [], "employees": [], "invoices": []}
    if not q:
        return jsonify(results)

    def matching(query, columns):
        prefixes = or_(*(column.istartswith(q, autoescape=True) for column in columns))
        matches = prefixes if len(q) == 1 else or_(*(column.icontains(q, autoescape=True) for column in columns))
        return query.filter(matches).order_by(db.case((prefixes, 0), else_=1))

    if role in ADMISSIONS | ATTENDANCE:
        names = func.trim(Student.first_name + " " + func.coalesce(Student.last_name, ""))
        students = matching(db.session.query(Student.id, names, Student.admission_no),
                            (Student.admission_no, Student.first_name, Student.last_name, Student.father_name, names)
                            ).order_by(Student.first_name, Student.id).limit(8).all()
        results["students"] = [{"id": row_id, "name": name, "admission_no": number}
                               for row_id, name, number in students]
    if role == "admin":
        employees = matching(db.session.query(Employee.id, Employee.name, Employee.employee_no),
                             (Employee.employee_no, Employee.name, Employee.phone)
                             ).order_by(Employee.name, Employee.id).limit(8).all()
        results["employees"] = [{"id": row_id, "name": name, "employee_no": number}
                                for row_id, name, number in employees]
    if role in FINANCE:
        invoices = matching(db.session.query(FeeInvoice.id, FeeInvoice.invoice_no, FeeInvoice.status),
                            (FeeInvoice.invoice_no,)).order_by(FeeInvoice.invoice_no, FeeInvoice.id).limit(8).all()
        results["invoices"] = [{"id": row_id, "invoice_no": number, "status": status}
                               for row_id, number, status in invoices]
    if request.args.get("scope") != "workspace":
        return jsonify(results)

    from .access import module_enabled
    from .models import HostelRoom, InventoryItem, MessMenu, Teacher
    records = []
    if role in ("admin", "staff"):
        teachers = matching(Teacher.query.join(Employee).with_entities(Teacher.id, Employee.name, Employee.employee_no),
                            (Employee.name, Employee.employee_no)).order_by(Employee.name).limit(5)
        records.extend({"url": url_for("academics.teacher_record", teacher_id=row_id),
                        "name": name, "detail": f"Teacher · {number}"} for row_id, name, number in teachers)
    if role in ("admin", "operations_admin"):
        sources = (
            ("inventory", InventoryItem, InventoryItem.name, InventoryItem.item_code, "Inventory"),
            ("hostel", HostelRoom, HostelRoom.room_no, HostelRoom.block, "Hostel"),
            ("mess", MessMenu, MessMenu.menu, MessMenu.meal_type, "Mess & Dining"),
        )
        for module, model, label, detail, title in sources:
            if module_enabled(module, module != "hostel"):
                rows = matching(db.session.query(model.id, label, detail), (label, detail)).order_by(model.id).limit(5)
                records.extend({"url": url_for("operations.operation_record", module=module, record_id=row_id),
                                "name": (name or "")[:100], "detail": f"{title} · {description or ''}"}
                               for row_id, name, description in rows)
    results["records"] = records
    return jsonify(results)
