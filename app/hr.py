from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from .extensions import db
from .models import Employee, Payroll, Teacher, TeacherAttendance, StaffLeave
from .codes import next_code
from .access import roles_required
from datetime import UTC, datetime, date
from decimal import Decimal, InvalidOperation
from calendar import monthrange
from werkzeug.utils import secure_filename
import os
from uuid import uuid4

hr_bp=Blueprint("hr",__name__,url_prefix="/hr")

@hr_bp.route("/employees",methods=["GET","POST"])
@login_required
@roles_required("hr_officer")
def employees():
    if request.method=="POST":
        try:
            name=(request.form.get("name") or "").strip()
            if not name: raise ValueError("Employee name is required.")
            dob=datetime.strptime(request.form["dob"],"%Y-%m-%d").date() if request.form.get("dob") else None
            joining=datetime.strptime(request.form["joining_date"],"%Y-%m-%d").date() if request.form.get("joining_date") else None
            e=Employee(employee_no=request.form.get("employee_no") or next_code("employee","EMP"),name=name,
                employee_type=request.form.get("employee_type") or "Non-Teacher", department=request.form.get("department"),
                designation=request.form.get("designation"),gender=request.form.get("gender"),dob=dob,
                father_name=request.form.get("father_name"),cnic=request.form.get("cnic"),phone=request.form.get("phone"),
                email=request.form.get("email"),address=request.form.get("address"),qualification=request.form.get("qualification"),
                experience_years=float(request.form.get("experience_years") or 0),joining_date=joining,
                basic_salary=float(request.form.get("basic_salary") or 0),bank_name=request.form.get("bank_name"),
                bank_account=request.form.get("bank_account"),iban=request.form.get("iban"),
                emergency_contact_name=request.form.get("emergency_contact_name"),emergency_contact_phone=request.form.get("emergency_contact_phone"),
                status=request.form.get("status") or "Active")
            photo=request.files.get("photo")
            if photo and photo.filename:
                ext=os.path.splitext(secure_filename(photo.filename))[1].lower()
                if ext not in {".jpg",".jpeg",".png",".webp"}: raise ValueError("Invalid photo type. Use JPG, PNG or WEBP.")
                d=os.path.join(os.path.dirname(__file__),"static","uploads","employees"); os.makedirs(d,exist_ok=True)
                fn=f"employee-{uuid4().hex}{ext}"; photo.save(os.path.join(d,fn)); e.photo_path=f"uploads/employees/{fn}"
            db.session.add(e); db.session.commit(); flash(f"Employee {e.employee_no} added. This same employee record will be used by Teacher and Payroll.","success")
        except Exception as ex:
            db.session.rollback(); flash(f"Employee was not saved: {ex}","danger")
    record_number = request.args.get("q", "").strip()[:80]
    records = Employee.query
    if record_number:
        records = records.filter_by(employee_no=record_number)
    return render_template("hr/employees.html",
                           employees=records.order_by(Employee.id.desc()).all(),
                           record_number=record_number)

LEAVE_TYPES = ("Annual", "Casual", "Sick", "Emergency", "Maternity", "Paternity", "Unpaid")
EARNINGS = ("housing_allowance", "transport_allowance", "medical_allowance", "other_allowances", "overtime", "bonus")
DEDUCTIONS = ("absent_deduction", "loan_deduction", "advance_deduction", "tax_deduction", "provident_fund", "other_deductions")


def lock_employee(employee_id):
    return Employee.query.filter_by(id=employee_id).update(
        {Employee.status: Employee.status}, synchronize_session=False
    )


@hr_bp.route("/leave", methods=["GET", "POST"])
@login_required
@roles_required("hr_officer", "principal", "vice_principal")
def leave():
    if request.method == "POST":
        employee_id = request.form.get("employee_id", type=int)
        kind = request.form.get("leave_type")
        try:
            start = date.fromisoformat(request.form.get("start_date", ""))
            end = date.fromisoformat(request.form.get("end_date", ""))
            if end < start or kind not in LEAVE_TYPES or not employee_id or not lock_employee(employee_id):
                raise ValueError("Select a valid employee, leave type and date range.")
            if db.session.get(Employee, employee_id).status != "Active":
                raise ValueError("Select an active employee.")
            overlap = StaffLeave.query.filter(
                StaffLeave.employee_id == employee_id, StaffLeave.status.in_(("Pending", "Approved")),
                StaffLeave.start_date <= end, StaffLeave.end_date >= start,
            ).first()
            if overlap:
                raise ValueError("This employee already has pending or approved leave for these dates.")
            db.session.add(StaffLeave(employee_id=employee_id, leave_type=kind, start_date=start,
                                      end_date=end, reason=request.form.get("reason", "").strip()[:500],
                                      created_by=current_user.id))
            db.session.commit()
            flash("Leave submitted for approval.", "success")
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "warning")
        return redirect(url_for("hr.leave"), code=303)
    status = request.args.get("status")
    records = StaffLeave.query
    if status in ("Pending", "Approved", "Rejected"):
        records = records.filter_by(status=status)
    return render_template("hr/leave.html", leave_types=LEAVE_TYPES, status=status,
                           records=records.order_by(StaffLeave.id.desc()).paginate(per_page=25, error_out=False),
                           employees=Employee.query.filter_by(status="Active").order_by(Employee.name).all())


@hr_bp.post("/leave/<int:leave_id>/review")
@login_required
@roles_required("principal", "vice_principal")
def review_leave(leave_id):
    decision = request.form.get("decision")
    if decision not in ("Approved", "Rejected"):
        return "Invalid decision", 400
    changed = StaffLeave.query.filter_by(id=leave_id, status="Pending").update({
        StaffLeave.status: decision, StaffLeave.reviewed_by: current_user.id,
        StaffLeave.reviewed_at: datetime.now(UTC).replace(tzinfo=None),
        StaffLeave.review_note: request.form.get("review_note", "").strip()[:500],
    }, synchronize_session=False)
    db.session.commit()
    flash(f"Leave {decision.lower()}." if changed else "Leave has already been reviewed.",
          "success" if changed else "warning")
    return redirect(url_for("hr.leave"), code=303)


def money(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or not 0 <= amount <= Decimal("999999999.99"):
        raise ValueError("Enter valid non-negative payroll amounts.")
    return amount.quantize(Decimal("0.01"))


@hr_bp.route("/payroll", methods=["GET", "POST"])
@login_required
@roles_required("accountant")
def payroll():
    employees = Employee.query.filter_by(status="Active").order_by(Employee.name).all()
    if request.method == "POST":
        try:
            employee_id = request.form.get("employee_id", type=int)
            month = request.form.get("month", "")
            date.fromisoformat(month + "-01")
            status = request.form.get("status") or "Processed"
            if len(month) != 7 or status not in ("Processed", "Paid", "On Hold") or not employee_id or not lock_employee(employee_id):
                raise ValueError("Select a valid employee, month and payroll status.")
            emp = db.session.get(Employee, employee_id)
            if emp.status != "Active":
                raise ValueError("Select an active employee.")
            record = Payroll.query.filter_by(employee_id=employee_id, month=month).first()
            if record and (record.paid_at or record.status == "Paid"):
                raise ValueError("Paid payroll is locked.")
            basic = money(request.form.get("basic_salary") or emp.basic_salary or 0)
            values = {key: money(request.form.get(key) or 0) for key in EARNINGS + DEDUCTIONS}
            allowances = sum(values[key] for key in EARNINGS)
            deductions = sum(values[key] for key in DEDUCTIONS)
            gross = basic + allowances
            if deductions > gross:
                raise ValueError("Total deductions cannot exceed gross salary.")
            if record is None:
                record = Payroll(employee_id=employee_id, month=month)
                db.session.add(record)
            for key, value in values.items():
                setattr(record, key, float(value))
            record.basic_salary, record.allowances, record.deductions = map(float, (basic, allowances, deductions))
            record.gross_salary, record.net_salary = float(gross), float(gross - deductions)
            record.payment_method = (request.form.get("payment_method") or "Bank")[:30]
            record.payment_reference = request.form.get("payment_reference", "")[:120]
            record.remarks = request.form.get("remarks", "")[:2000]
            record.status = status
            if status == "Paid":
                record.paid_at = datetime.now(UTC).replace(tzinfo=None)
            db.session.commit()
            flash("Payroll saved successfully.", "success")
        except (ValueError, InvalidOperation) as error:
            db.session.rollback()
            flash(str(error) if isinstance(error, ValueError) else "Enter valid payroll amounts.", "danger")
        return redirect(url_for("hr.payroll", month=month, employee_id=employee_id), code=303)
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    employee_id = request.args.get("employee_id", type=int)
    approved = []
    try:
        first = date.fromisoformat(month + "-01")
        last = first.replace(day=monthrange(first.year, first.month)[1])
        if employee_id:
            approved = StaffLeave.query.filter(
                StaffLeave.employee_id == employee_id, StaffLeave.status == "Approved",
                StaffLeave.start_date <= last, StaffLeave.end_date >= first,
            ).order_by(StaffLeave.start_date).all()
    except ValueError:
        pass
    record = Payroll.query.filter_by(employee_id=employee_id, month=month).first() if employee_id else None
    return render_template("hr/payroll.html", employees=employees, approved=approved, record=record,
                           selected_month=month, selected_employee=employee_id,
                           payroll=Payroll.query.order_by(Payroll.id.desc()).limit(100).all())


@hr_bp.get("/payroll/<int:record_id>/payslip")
@login_required
@roles_required("accountant")
def payslip(record_id):
    record = db.get_or_404(Payroll, record_id)
    return render_template("hr/payslip.html", record=record, earnings=EARNINGS, deductions=DEDUCTIONS)


@hr_bp.route("/teacher-attendance", methods=["GET", "POST"])
@login_required
@roles_required("staff", "hr_officer")
def teacher_attendance():
    try:
        selected_date = date.fromisoformat(request.values.get("date") or date.today().isoformat())
    except ValueError:
        selected_date = date.today()
        flash("Invalid attendance date. Showing today's roster.", "warning")
    roster = Teacher.query.join(Employee).filter(
        Teacher.status == "Active", Employee.status == "Active"
    ).order_by(Employee.name).all()
    existing = {entry.teacher_id: entry for entry in TeacherAttendance.query.filter_by(date=selected_date).all()}
    statuses = ("Present", "Absent", "Late", "Leave")
    if request.method == "POST":
        submitted = {teacher.id: request.form.get(f"teacher_{teacher.id}", "") for teacher in roster}
        if any(status and status not in statuses for status in submitted.values()):
            flash("Invalid attendance status. Review the roster and try again.", "danger")
        else:
            try:
                for teacher_id, status in submitted.items():
                    if not status:
                        continue
                    if teacher_id in existing:
                        entry = existing[teacher_id]
                        entry.status, entry.recorded_by = status, current_user.id
                    else:
                        db.session.add(TeacherAttendance(teacher_id=teacher_id, date=selected_date,
                                                         status=status, recorded_by=current_user.id))
                db.session.commit()
                flash("Teacher attendance saved.", "success")
                return redirect(url_for("hr.teacher_attendance", date=selected_date.isoformat()), code=303)
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Teacher attendance save failed")
                flash("Teacher attendance could not be saved. Reload the roster and try again.", "danger")
    return render_template("hr/teacher_attendance.html", roster=roster, selected_date=selected_date,
                           existing=existing, statuses=statuses)
