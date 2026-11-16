from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from .access import EXAM_APPROVERS, roles_required, teacher_profile
from .extensions import db
from .models import Teacher, Employee, Exam, Result, Student, Subject, AcademicSession, ClassRoom, GradeScale, Timetable, AuditLog
from datetime import UTC, datetime
from math import isfinite
from sqlalchemy.orm import joinedload, selectinload

academics_bp = Blueprint("academics", __name__)

def ensure_teacher(employee, subjects):
    teacher = Teacher.query.filter_by(employee_id=employee.id).first()
    if teacher:
        return teacher
    from sqlalchemy import inspect, text

    legacy = {
        "employee_no": employee.employee_no, "name": employee.name,
        "subject": ", ".join(subject.name for subject in subjects),
        "phone": employee.phone, "email": employee.email, "designation": employee.designation,
    }
    columns = {column["name"] for column in inspect(db.session.connection()).get_columns("teacher")}
    legacy_values = {key: value for key, value in legacy.items() if key in columns}
    if legacy_values:
        values = dict(employee_id=employee.id, status="Active", **legacy_values)
        fields = ", ".join(values)
        parameters = ", ".join(f":{field}" for field in values)
        db.session.execute(text(f"INSERT INTO teacher ({fields}) VALUES ({parameters})"), values)
        return Teacher.query.filter_by(employee_id=employee.id).one()
    teacher = Teacher(employee=employee, status="Active")
    db.session.add(teacher)
    db.session.flush()
    return teacher


@academics_bp.route("/teachers", methods=["GET", "POST"])
@login_required
@roles_required("admin","staff")
def teachers():
    employees=Employee.query.filter(Employee.employee_type=="Teacher", Employee.status=="Active").order_by(Employee.name).all()
    subjects=Subject.query.order_by(Subject.name).all()
    if request.method == "POST":
        from .timetable import _lock_schedule
        _lock_schedule()
        employee_id=request.form.get("employee_id")
        subject_ids=[int(x) for x in request.form.getlist("subject_ids") if x.isdigit()]
        emp=db.get_or_404(Employee, int(employee_id)) if employee_id and employee_id.isdigit() else None
        if not emp or emp.employee_type != "Teacher":
            flash("Please select a valid Teacher from Employees.", "danger")
        elif not subject_ids:
            flash("Please select at least one subject.", "danger")
        else:
            selected = Subject.query.filter(Subject.id.in_(subject_ids)).all()
            t = ensure_teacher(emp, selected)
            if Timetable.query.filter(Timetable.teacher_id == t.id, Timetable.subject_id.notin_(subject_ids)).first():
                db.session.rollback()
                flash("Use Edit to transfer scheduled subjects before removing them.", "warning")
                return redirect(url_for("academics.teachers"), code=303)
            t.subjects = selected
            db.session.commit(); flash(f"Teacher profile updated for {emp.name}.", "success")
    q = request.args.get("q", "").strip()[:80]
    rows = Teacher.query.join(Employee).options(joinedload(Teacher.employee), selectinload(Teacher.subjects))
    if q:
        rows = rows.filter(db.or_(Employee.name.istartswith(q, autoescape=True),
                                  Employee.employee_no.istartswith(q, autoescape=True)))
    teacher_rows = rows.order_by(Employee.name, Teacher.id).all()
    return render_template("academics/teachers.html", teachers=teacher_rows, employees=employees, subjects=subjects, q=q)

@academics_bp.route("/teachers/<int:teacher_id>", methods=["GET", "POST"])
@login_required
@roles_required("staff")
def teacher_record(teacher_id):
    from .timetable import _lock_schedule, check_conflicts, schedule_fields

    if request.method == "POST":
        _lock_schedule()
    teacher = db.get_or_404(Teacher, teacher_id)
    if request.method == "POST":
        try:
            action = request.form.get("action")
            if action == "transfer":
                subject = db.session.get(Subject, request.form.get("subject_id", type=int))
                replacement = Teacher.query.join(Employee).filter(
                    Teacher.id == request.form.get("replacement_id", type=int),
                    Teacher.status == "Active", Employee.status == "Active",
                ).first()
                if subject not in teacher.subjects or not replacement or replacement.id == teacher.id:
                    raise ValueError("Choose an assigned subject and a different active teacher.")
                slots = Timetable.query.all()
                moving = [slot for slot in slots if slot.teacher_id == teacher.id and slot.subject_id == subject.id]
                moving_ids = {slot.id for slot in moving}
                occupied = [schedule_fields(slot) for slot in slots if slot.id not in moving_ids]
                for slot in moving:
                    row = dict(schedule_fields(slot), teacher_id=replacement.id)
                    issue = check_conflicts(row, occupied)
                    if issue:
                        raise ValueError(issue)
                    occupied.append(row)
                for slot in moving:
                    slot.teacher_id = replacement.id
                teacher.subjects.remove(subject)
                if subject not in replacement.subjects:
                    replacement.subjects.append(subject)
                details = f"Teacher #{teacher.id} transferred subject #{subject.id} to #{replacement.id} ({len(moving)} timetable slots)"
            elif action == "save":
                status = request.form.get("status")
                ids = request.form.getlist("subject_ids", type=int)
                subjects = Subject.query.filter(Subject.id.in_(ids)).all()
                if status not in ("Active", "Inactive") or len(subjects) != len(set(ids)):
                    raise ValueError("Select valid subjects and teacher status.")
                scheduled = Timetable.query.filter_by(teacher_id=teacher.id).all()
                if scheduled and status == "Inactive":
                    raise ValueError("Transfer scheduled subjects before deactivating this teacher.")
                if any(slot.subject_id not in ids for slot in scheduled):
                    raise ValueError("Transfer a scheduled subject before removing it.")
                teacher.subjects = subjects
                teacher.status = status
                details = f"Teacher #{teacher.id}: status {status}, subjects {sorted(ids)}"
            else:
                raise ValueError("Choose a valid teacher action.")
            db.session.add(AuditLog(user_id=current_user.id, action="TEACHER_UPDATE", module="Academics", details=details))
            db.session.commit()
            flash("Teacher directory updated.", "success")
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "warning")
        return redirect(url_for("academics.teacher_record", teacher_id=teacher_id), code=303)
    return render_template("academics/teacher_record.html", teacher=teacher,
                           editing=request.args.get("edit") == "1",
                           subjects=Subject.query.order_by(Subject.name).all(),
                           replacements=Teacher.query.join(Employee).filter(
                               Teacher.id != teacher.id, Teacher.status == "Active", Employee.status == "Active"
                           ).order_by(Employee.name).all(),
                           slots=Timetable.query.filter_by(teacher_id=teacher.id).order_by(Timetable.day, Timetable.start_time).all())


@academics_bp.route("/teacher-allocation/import", methods=["GET", "POST"])
@login_required
@roles_required("staff")
def import_allocations():
    from .allocation_import import handle_import
    return handle_import()


@academics_bp.route("/teacher-subjects")
@login_required
@roles_required("admin","staff")
def teacher_subjects():
    employee_id=request.args.get("employee_id", type=int)
    t=Teacher.query.filter_by(employee_id=employee_id).first() if employee_id else None
    return jsonify({"subject_ids":[x.id for x in t.subjects] if t else []})

@academics_bp.route("/exams", methods=["GET","POST"])
@login_required
@roles_required("staff", *EXAM_APPROVERS)
def exams():
    sessions=AcademicSession.query.order_by(AcademicSession.id.desc()).all(); classes=ClassRoom.query.order_by(ClassRoom.name,ClassRoom.section).all()
    if request.method == "POST":
        if request.form.get("term") not in ("Monthly Test", "Midterm", "Final Term"):
            abort(400)
        e=Exam(name=request.form["name"], session_id=int(request.form["session_id"]) if request.form.get("session_id") else None, class_id=int(request.form["class_id"]) if request.form.get("class_id") else None, term=request.form.get("term"), start_date=datetime.strptime(request.form["start_date"], "%Y-%m-%d").date() if request.form.get("start_date") else None, end_date=datetime.strptime(request.form["end_date"], "%Y-%m-%d").date() if request.form.get("end_date") else None)
        db.session.add(e); db.session.commit(); flash("Exam created.", "success")
    return render_template("academics/exams.html", exams=Exam.query.order_by(Exam.id.desc()).all(), sessions=sessions, classes=classes)

def grade_for(percent):
    scale=GradeScale.query.filter(GradeScale.min_percent <= percent, GradeScale.max_percent >= percent).first()
    return scale.grade if scale else ("A+" if percent>=80 else "A" if percent>=70 else "B" if percent>=60 else "C" if percent>=50 else "D" if percent>=40 else "F")

@academics_bp.route("/results", methods=["GET", "POST"])
@login_required
@roles_required("staff", "teacher", *EXAM_APPROVERS)
def results():
    assignments = None
    student_query = Student.query.filter_by(status="Active")
    exam_query = Exam.query
    subject_query = Subject.query
    rows = Result.query
    if current_user.role == "teacher":
        teacher = teacher_profile(current_user)
        assignments = {(row.class_id, row.subject_id) for row in
                       Timetable.query.filter_by(teacher_id=teacher.id).all()} if teacher else set()
        class_ids = {class_id for class_id, _ in assignments}
        student_query = student_query.filter(Student.class_id.in_(class_ids))
        exam_query = exam_query.filter(db.or_(Exam.class_id.is_(None), Exam.class_id.in_(class_ids)))
        subject_query = subject_query.filter(Subject.id.in_({subject_id for _, subject_id in assignments}))
        rows = rows.join(Student).filter(db.or_(db.false(), *(
            db.and_(Student.class_id == class_id, Result.subject_id == subject_id)
            for class_id, subject_id in assignments
        )))

    if request.method == "POST":
        if current_user.role in EXAM_APPROVERS:
            abort(403)
        exam_id = request.form.get("exam_id", type=int)
        student_id = request.form.get("student_id", type=int)
        subject_id = request.form.get("subject_id", type=int)
        marks = request.form.get("marks", type=float)
        total = request.form.get("total", default=100.0, type=float)
        exam = db.get_or_404(Exam, exam_id)
        student = student_query.filter(Student.id == student_id).first_or_404()
        if assignments is not None and (student.class_id, subject_id) not in assignments:
            abort(403)
        db.get_or_404(Subject, subject_id)
        if ((exam.class_id is not None and student.class_id != exam.class_id)
                or (exam.session_id is not None and (not student.class_room or student.class_room.session_id != exam.session_id))):
            abort(400, description="Student does not belong to this exam's class or session.")
        if marks is None or not isfinite(marks) or not isfinite(total) or total <= 0 or not 0 <= marks <= total:
            abort(400, description="Enter valid marks between zero and the positive total.")
        # The same exam row is locked by the approval action before it updates.
        editable = Exam.query.filter(Exam.id == exam_id, Exam.approved_at.is_(None)).update(
            {Exam.approved_at: None}, synchronize_session=False
        )
        if not editable:
            abort(409, description="Approved marks are locked.")
        result = Result.query.filter_by(exam_id=exam_id, student_id=student_id, subject_id=subject_id).first()
        if result is None:
            result = Result(exam_id=exam_id, student_id=student_id, subject_id=subject_id)
            db.session.add(result)
        result.marks, result.total = marks, total
        db.session.commit()
        flash("Draft marks saved.", "success")
        return redirect(url_for("academics.results", exam_id=exam_id), code=303)

    selected_exam = request.args.get("exam_id", type=int)
    reviewing = exam_query.filter_by(id=selected_exam).first_or_404() if selected_exam else None
    if reviewing:
        rows = rows.filter(Result.exam_id == reviewing.id)
    return render_template("academics/results.html",
                           results=rows.order_by(Result.id.desc()).paginate(per_page=50, error_out=False),
                           students=student_query.order_by(Student.first_name).all(),
                           exams=exam_query.order_by(Exam.id.desc()).all(),
                           subjects=subject_query.order_by(Subject.name).all(),
                           reviewing=reviewing, can_approve=current_user.role in EXAM_APPROVERS)


@academics_bp.post("/exams/<int:exam_id>/approve")
@login_required
def approve_exam(exam_id):
    if current_user.role not in EXAM_APPROVERS:
        abort(403)
    db.get_or_404(Exam, exam_id)
    changed = Exam.query.filter(
        Exam.id == exam_id, Exam.approved_at.is_(None),
    ).update({Exam.approved_at: datetime.now(UTC).replace(tzinfo=None),
              Exam.approved_by_id: current_user.id}, synchronize_session=False)
    if not changed or not Result.query.filter_by(exam_id=exam_id).first():
        db.session.rollback()
        abort(409, description="Only an unapproved exam with marks can be approved.")
    db.session.commit()
    flash("Results approved and published to student portals.", "success")
    return redirect(url_for("academics.results", exam_id=exam_id), code=303)


def report_card_records(student_id, exam_id):
    student = db.get_or_404(Student, student_id)
    exam = db.get_or_404(Exam, exam_id)
    if current_user.role == "student":
        if current_user.student_id != student.id or not exam.approved_at:
            abort(403)
    elif current_user.role not in ("admin", "staff", *EXAM_APPROVERS):
        abort(403)
    rows = Result.query.filter_by(student_id=student.id, exam_id=exam.id).order_by(Result.subject_id).all()
    if not rows:
        abort(404)
    return student, exam, rows


@academics_bp.route("/report-card/<int:student_id>/<int:exam_id>")
@login_required
def report_card(student_id, exam_id):
    student, exam, rows = report_card_records(student_id, exam_id)
    total = sum(r.total or 0 for r in rows)
    obtained = sum(r.marks or 0 for r in rows)
    pct = round(obtained / total * 100, 2) if total else 0
    return render_template("academics/report_card.html", student=student, exam=exam, rows=rows,
                           total=total, obtained=obtained, pct=pct, grade=grade_for(pct))


@academics_bp.route("/grades", methods=["GET","POST"])
@login_required
@roles_required("staff", *EXAM_APPROVERS)
def grades():
    if request.method=="POST":
        db.session.add(GradeScale(grade=request.form["grade"],min_percent=float(request.form["min_percent"]),max_percent=float(request.form["max_percent"]),remarks=request.form.get("remarks"))); db.session.commit(); flash("Grade scale added.","success")
    return render_template("academics/grades.html",grades=GradeScale.query.order_by(GradeScale.min_percent.desc()).all())
