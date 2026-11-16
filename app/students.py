from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from .extensions import db
from .models import Student, Attendance, Parent, ClassRoom, StudentStatusHistory, StudentPromotionHistory, FeeStructure, AcademicSession, SystemSetting
from .codes import next_code
from .access import roles_required, teacher_profile
from .models import Timetable
from .validators import clean_phone, clean_cnic
from werkzeug.utils import secure_filename
import os, hmac, hashlib, base64

students_bp = Blueprint("students", __name__)


def _parent_match(mobile=None, email=None, cnic=None):
    """Find an existing guardian using any supplied normalized identifier.

    Matching is intentionally done on contact identifiers, not guardian name,
    so two different people with the same name are not accidentally merged.
    """
    mobile = clean_phone(mobile) if mobile else ""
    email = (email or "").strip().lower()
    cnic = clean_cnic(cnic) if cnic else ""
    from sqlalchemy import or_
    conditions = []
    if mobile:
        conditions.extend([Parent.mobile == mobile, Parent.phone == mobile])
    if email:
        conditions.append(db.func.lower(Parent.email) == email)
    if cnic:
        conditions.append(Parent.cnic == cnic)
    if not conditions:
        return None
    return Parent.query.filter(or_(*conditions)).order_by(Parent.id.asc()).first()

@students_bp.route("/")
@login_required
@roles_required("admin", "admission_officer", "teacher", "staff")
def list_students():
    from sqlalchemy.orm import joinedload

    q = request.args.get("q", "").strip()[:80]
    status = request.args.get("status", "")
    incomplete = request.args.get("incomplete") == "1"
    if incomplete:
        from .assistant import admission_gaps
        query = admission_gaps()
    else:
        query = Student.query
    if status:
        query = query.filter_by(status=status)
    if q:
        name = db.func.trim(Student.first_name + " " + db.func.coalesce(Student.last_name, ""))
        fields = (Student.first_name, Student.last_name, Student.admission_no, Student.father_name, name)
        starts = db.or_(*(field.istartswith(q, autoescape=True) for field in fields))
        contains = db.or_(*(field.icontains(q, autoescape=True) for field in fields))
        query = query.filter(starts if len(q) == 1 else contains).order_by(
            db.case((Student.admission_no == q, 0), (starts, 1), else_=2), Student.first_name)
    if request.args.get("suggest") == "1":
        rows = query.with_entities(Student.first_name, Student.last_name, Student.admission_no).limit(8).all() if q else []
        return jsonify(students=[{"name": f"{first} {last or ''}".strip(), "admission_no": number}
                                 for first, last, number in rows], employees=[], invoices=[])
    page = query.options(joinedload(Student.class_room)).order_by(Student.id.desc()).paginate(per_page=50, error_out=False)
    return render_template("students/list.html", students=page.items, page=page, q=q, status=status, incomplete=incomplete)

@students_bp.route("/parent-lookup")
@login_required
@roles_required("admin", "admission_officer", "staff")
def parent_lookup():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"found": False})
    # Search by normalized mobile/CNIC or case-insensitive email.
    p = _parent_match(q, q, q)
    if not p: return jsonify({"found": False})
    children = [{"id": c.id, "code": c.admission_no, "name": f"{c.first_name} {c.last_name or ''}".strip(), "class": f"{c.class_room.name} - {c.class_room.section}" if c.class_room else "-"} for c in p.children]
    return jsonify({"found": True, "id": p.id, "name": p.name, "relation": p.relation or "Father/Guardian", "mobile": p.mobile or p.phone or "", "phone": p.phone or "", "email": p.email or "", "cnic": p.cnic or "", "address": p.address or "", "latitude": p.latitude, "longitude": p.longitude, "children": children})

@students_bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "admission_officer", "staff")
def new_student():
    classes = ClassRoom.query.order_by(ClassRoom.name, ClassRoom.section).all()
    parents = Parent.query.order_by(Parent.name).all()
    structures = FeeStructure.query.filter_by(is_active=True).order_by(FeeStructure.name).all()
    hostel_enabled = str((SystemSetting.query.filter_by(key="module.hostel").first().value if SystemSetting.query.filter_by(key="module.hostel").first() else "0")).lower() in {"1","true","yes","on"}
    transport_enabled = str((SystemSetting.query.filter_by(key="module.transport").first().value if SystemSetting.query.filter_by(key="module.transport").first() else "1")).lower() in {"1","true","yes","on"}
    if request.method == "POST":
        try:
            required = {"first_name":"Student first name","father_name":"Father/guardian name","gender":"Gender","dob":"Date of birth","class_id":"Class / Section","admission_date":"Admission date","parent_name":"Guardian name"}
            missing=[label for key,label in required.items() if not (request.form.get(key) or "").strip()]
            mobile = clean_phone(request.form.get("parent_mobile") or request.form.get("parent_phone"))
            email = (request.form.get("parent_email") or "").strip()
            cnic = clean_cnic(request.form.get("parent_cnic"))
            if not mobile and not email and not cnic: missing.append("Guardian contact (mobile, email or CNIC)")
            if missing: raise ValueError("Required field(s) missing: " + ", ".join(missing))
            parent_id = int(request.form["parent_id"]) if request.form.get("parent_id") else None

            parent_name = (request.form.get("parent_name", "").strip() or request.form.get("father_name", "").strip())
            if not parent_id and not (mobile or email or cnic):
                raise ValueError("Guardian contact is required for a new admission (mobile, email or CNIC).")
            if not parent_id and (mobile or email or cnic):
                existing = _parent_match(mobile, email, cnic)
                if existing:
                    parent_id = existing.id
                else:
                    p = Parent(name=parent_name or "Parent/Guardian", relation=request.form.get("parent_relation") or "Father", phone=clean_phone(request.form.get("parent_phone") or mobile), mobile=mobile, email=email, cnic=cnic, address=request.form.get("parent_address"), latitude=float(request.form["parent_latitude"]) if request.form.get("parent_latitude") else None, longitude=float(request.form["parent_longitude"]) if request.form.get("parent_longitude") else None)
                    db.session.add(p); db.session.flush(); parent_id = p.id
            class_id = int(request.form["class_id"]) if request.form.get("class_id") else None
            s = Student(
                admission_no=next_code("student", "STD"), first_name=request.form["first_name"].strip(),
                last_name=request.form.get("last_name", "").strip(), father_name=request.form.get("father_name"),
                gender=request.form.get("gender"), dob=datetime.strptime(request.form["dob"], "%Y-%m-%d").date() if request.form.get("dob") else None,
                class_id=class_id, parent_id=parent_id, house=(request.form.get("house") if hostel_enabled else None), room_no=(request.form.get("room_no") if hostel_enabled else None),
                phone=request.form.get("student_phone"), address=request.form.get("address"),
                latitude=float(request.form["latitude"]) if request.form.get("latitude") else None,
                longitude=float(request.form["longitude"]) if request.form.get("longitude") else None,
                admission_date=datetime.strptime(request.form["admission_date"], "%Y-%m-%d").date() if request.form.get("admission_date") else datetime.utcnow().date(),
                status="Active"
            )
            photo=request.files.get("photo")
            if photo and photo.filename:
                ext=os.path.splitext(secure_filename(photo.filename))[1].lower()
                if ext not in {".jpg",".jpeg",".png",".webp"}: raise ValueError("Invalid photo type")
                upload_dir=os.path.join(os.path.dirname(__file__), "static", "uploads", "students"); os.makedirs(upload_dir, exist_ok=True)
                filename=f"student-{s.admission_no}{ext}"; photo.save(os.path.join(upload_dir, filename)); s.photo_path=f"uploads/students/{filename}"
            db.session.add(s); db.session.flush()
            db.session.add(StudentStatusHistory(student_id=s.id, new_status=s.status, remarks="Admission created", changed_by=current_user.id))
            from .models import AuditLog
            db.session.add(AuditLog(user_id=current_user.id, action="Create Admission", module="Admissions", details=f"Student {s.admission_no} created"))
            invoice_id = None
            if request.form.get("fee_structure_id"):
                fs = db.session.get(FeeStructure, int(request.form["fee_structure_id"]))
                if fs:
                    from .models import FeeInvoice
                    inv = FeeInvoice(invoice_no=next_code("invoice", "INV"), student_id=s.id, fee_type=fs.name, amount=fs.amount, paid=0, status="Unpaid")
                    db.session.add(inv); db.session.flush(); invoice_id = inv.id
            db.session.commit()
            flash(f"Admission created successfully. Student Code: {s.admission_no}", "success")
            if invoice_id:
                return redirect(url_for("finance.voucher", invoice_id=invoice_id))
            return redirect(url_for("students.profile", id=s.id))
        except Exception as ex:
            db.session.rollback(); flash(f"Admission not saved: {ex}", "danger")
    return render_template("students/form.html", student=None, classes=classes, parents=parents, structures=structures, auto_code=next_code_preview("student", "STD"), hostel_enabled=hostel_enabled, transport_enabled=transport_enabled)

@students_bp.route("/admission-report")
@login_required
@roles_required("admin", "admission_officer")
def admission_report():
    from .models import AcademicSession
    status = request.args.get("status", "").strip()
    class_id = request.args.get("class_id", "").strip()
    q = Student.query
    if status:
        q = q.filter_by(status=status)
    if class_id.isdigit():
        q = q.filter_by(class_id=int(class_id))
    rows = q.order_by(Student.id.desc()).limit(500).all()
    return render_template("students/admission_report.html", rows=rows, selected_status=status, selected_class=class_id, classes=ClassRoom.query.order_by(ClassRoom.name, ClassRoom.section).all(), statuses=["Active","Dropped Out","Inactive","Transferred","Withdrawn","Graduated"])

def next_code_preview(code_type, prefix):
    from .models import SequenceCounter
    c = SequenceCounter.query.filter_by(code_type=code_type).first()
    n = (c.current_value + 1) if c else 1
    return f"{prefix}-{datetime.utcnow().year}-{n:05d}"

@students_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "admission_officer", "staff")
def edit_student(id):
    s = db.get_or_404(Student, id); classes = ClassRoom.query.order_by(ClassRoom.name, ClassRoom.section).all(); parents = Parent.query.order_by(Parent.name).all(); structures = FeeStructure.query.filter_by(is_active=True).all()
    if request.method == "POST":
        old_status=s.status
        s.first_name=request.form["first_name"].strip(); s.last_name=request.form.get("last_name"); s.father_name=request.form.get("father_name"); s.gender=request.form.get("gender")
        s.dob=datetime.strptime(request.form["dob"], "%Y-%m-%d").date() if request.form.get("dob") else None; s.class_id=int(request.form["class_id"]) if request.form.get("class_id") else None; s.parent_id=int(request.form["parent_id"]) if request.form.get("parent_id") else None
        s.house=request.form.get("house"); s.room_no=request.form.get("room_no"); s.phone=clean_phone(request.form.get("student_phone")); s.address=request.form.get("address"); s.latitude=float(request.form["latitude"]) if request.form.get("latitude") else None; s.longitude=float(request.form["longitude"]) if request.form.get("longitude") else None
        s.admission_date=datetime.strptime(request.form["admission_date"], "%Y-%m-%d").date() if request.form.get("admission_date") else s.admission_date; s.status=request.form.get("status", "Active")
        photo=request.files.get("photo");
        if photo and photo.filename:
            ext=os.path.splitext(secure_filename(photo.filename))[1].lower()
            if ext not in {".jpg",".jpeg",".png",".webp"}: abort(400, description="Only JPG, PNG or WEBP photos are allowed.")
            upload_dir=os.path.join(os.path.dirname(__file__), "static", "uploads", "students"); os.makedirs(upload_dir, exist_ok=True)
            filename=f"student-{s.admission_no}{ext}"; photo.save(os.path.join(upload_dir, filename)); s.photo_path=f"uploads/students/{filename}"
        if old_status != s.status: db.session.add(StudentStatusHistory(student_id=s.id, old_status=old_status, new_status=s.status, remarks=request.form.get("status_remarks"), changed_by=current_user.id))
        db.session.commit(); flash("Student updated successfully.", "success"); return redirect(url_for("students.profile", id=s.id))
    return render_template("students/form.html", student=s, classes=classes, parents=parents, structures=structures, auto_code=s.admission_no)

@students_bp.route("/<int:id>")
@login_required
@roles_required("admin", "admission_officer", "staff")
def profile(id):
    from .models import FeeInvoice, Result
    s=db.get_or_404(Student,id); invoices=FeeInvoice.query.filter_by(student_id=id).order_by(FeeInvoice.id.desc()).all(); results=Result.query.filter_by(student_id=id).order_by(Result.id.desc()).limit(20).all(); attendance=Attendance.query.filter_by(student_id=id).order_by(Attendance.date.desc()).limit(30).all(); history=StudentStatusHistory.query.filter_by(student_id=id).order_by(StudentStatusHistory.changed_at.desc()).all()
    total=len(attendance); present=sum(1 for a in attendance if a.status.lower() in ("present","late")); attendance_pct=round((present/total)*100,1) if total else 0
    family_children = s.parent.children if s.parent else [s]
    return render_template("students/profile.html", student=s, invoices=invoices, results=results, attendance=attendance, history=history, attendance_pct=attendance_pct, family_children=family_children)

@students_bp.route("/parents", methods=["GET","POST"])
@login_required
@roles_required("admin", "admission_officer", "staff")
def parents():
    if request.method=="POST":
        try:
            mobile=clean_phone(request.form.get("mobile") or request.form.get("phone")); email=request.form.get("email","").strip(); cnic=clean_cnic(request.form.get("cnic",""))
            existing=_parent_match(mobile, email, cnic)
            if existing:
                flash(f"Guardian already exists: {existing.name}. Existing family record loaded.","warning")
            else:
                p=Parent(name=request.form["name"].strip(),relation=request.form.get("relation"),phone=clean_phone(request.form.get("phone")),mobile=mobile,email=email,cnic=cnic,address=request.form.get("address"),latitude=float(request.form["latitude"]) if request.form.get("latitude") else None,longitude=float(request.form["longitude"]) if request.form.get("longitude") else None); db.session.add(p); db.session.commit(); flash("Parent/guardian added.","success")
        except (ValueError, TypeError):
            db.session.rollback(); flash("Please check mobile/CNIC and location values.","danger")
    return render_template("students/parents.html", parents=Parent.query.order_by(Parent.id.desc()).all())

def _card_token(student):
    from flask import current_app
    msg=f"{student.id}:{student.admission_no}".encode()
    return base64.urlsafe_b64encode(hmac.new(current_app.config["SECRET_KEY"].encode(), msg, hashlib.sha256).digest()[:18]).decode().rstrip("=")

@students_bp.route("/<int:id>/id-card")
@login_required
@roles_required("admin", "admission_officer", "staff", "teacher", "student")
def id_card(id):
    student=db.get_or_404(Student,id)
    if current_user.role == "student" and current_user.student_id != student.id:
        abort(403)
    return render_template("students/id_card.html", student=student, verify_token=_card_token(student))

@students_bp.route("/verify-card/<admission_no>")
def verify_card(admission_no):
    token=request.args.get("token","")
    student=Student.query.filter_by(admission_no=admission_no).first()
    if not student or not hmac.compare_digest(token, _card_token(student)):
        abort(404)
    return render_template("students/card_verify.html", student=student)

@students_bp.route("/<int:id>/delete", methods=["POST"])
@login_required
@roles_required("admin", "admission_officer")
def delete_student(id):
    s=db.get_or_404(Student,id); old_status=s.status; s.status="Withdrawn"; db.session.add(StudentStatusHistory(student_id=s.id,old_status=old_status,new_status="Withdrawn",remarks="Student withdrawn",changed_by=current_user.id)); db.session.commit(); flash("Student marked as withdrawn. Record retained for audit.","success"); return redirect(url_for("students.list_students"))

@students_bp.route("/family/<int:parent_id>")
@login_required
@roles_required("admin", "admission_officer", "staff", "teacher")
def family(parent_id):
    parent=db.get_or_404(Parent,parent_id)
    return render_template("students/family.html", parent=parent, children=parent.children)

@students_bp.route("/promotion", methods=["GET", "POST"])
@login_required
@roles_required("admin", "admission_officer")
def promotion():
    classes=ClassRoom.query.order_by(ClassRoom.name, ClassRoom.section).all()
    sessions=AcademicSession.query.order_by(AcademicSession.start_date.desc(), AcademicSession.id.desc()).all()
    status=request.args.get("status", "Active")
    class_id=request.args.get("class_id", "")
    query=Student.query
    if status: query=query.filter_by(status=status)
    if class_id.isdigit(): query=query.filter_by(class_id=int(class_id))
    students=query.order_by(Student.first_name, Student.last_name).all()
    if request.method=="POST":
        student_ids=request.form.getlist("student_ids")
        target_class_id=request.form.get("target_class_id")
        target_session_id=request.form.get("target_session_id") or None
        remarks=(request.form.get("remarks") or "").strip()
        if not student_ids or not target_class_id:
            flash("Select at least one student and a target class.", "danger")
            return redirect(url_for("students.promotion", status=status, class_id=class_id))
        target_class=db.get_or_404(ClassRoom, int(target_class_id))
        target_session=db.session.get(AcademicSession, int(target_session_id)) if target_session_id and target_session_id.isdigit() else target_class.session
        count=0
        for sid in student_ids:
            student=db.session.get(Student, int(sid))
            if not student or student.status != "Active": continue
            if student.class_id == target_class.id: continue
            old_class_id=student.class_id
            old_session_id=student.class_room.session_id if student.class_room else None
            student.class_id=target_class.id
            student.status="Active"
            db.session.add(StudentPromotionHistory(student_id=student.id, from_class_id=old_class_id, to_class_id=target_class.id, from_session_id=old_session_id, to_session_id=target_session.id if target_session else None, remarks=remarks or f"Promoted to {target_class.name} - {target_class.section}", changed_by=current_user.id))
            db.session.add(StudentStatusHistory(student_id=student.id, old_status="Active", new_status="Active", remarks=f"Class promotion: {target_class.name} - {target_class.section}" + (f"; {remarks}" if remarks else ""), changed_by=current_user.id))
            count+=1
        db.session.commit()
        flash(f"{count} student(s) promoted successfully.", "success")
        return redirect(url_for("students.promotion"))
    return render_template("students/promotion.html", students=students, classes=classes, sessions=sessions, status=status, class_id=class_id)

@students_bp.route("/<int:id>/dropout", methods=["POST"])
@login_required
@roles_required("admin", "admission_officer")
def dropout_student(id):
    s=db.get_or_404(Student,id)
    if s.status == "Dropped Out":
        flash("Student is already marked as Dropped Out.", "warning")
        return redirect(url_for("students.profile", id=id))
    old=s.status
    remarks=(request.form.get("remarks") or "Student marked as dropped out.").strip()
    s.status="Dropped Out"
    db.session.add(StudentStatusHistory(student_id=s.id, old_status=old, new_status="Dropped Out", remarks=remarks, changed_by=current_user.id))
    db.session.commit()
    flash("Student marked as Dropped Out. Historical records have been retained.", "success")
    return redirect(url_for("students.profile", id=id))

@students_bp.route("/attendance", methods=["GET", "POST"])
@login_required
@roles_required("admin", "teacher", "staff")
def attendance():
    """Daily attendance entry with separate Load and Save actions.

    Load must never write attendance. Save creates a new row when one does not
    exist and updates the existing row when it does.
    """
    selected_date = (
        request.form.get("date")
        or request.args.get("date")
        or datetime.utcnow().date().isoformat()
    )
    try:
        d = datetime.strptime(selected_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        d = datetime.utcnow().date()
        selected_date = d.isoformat()
        flash("Invalid attendance date. Today's date has been selected.", "warning")

    class_id = request.form.get("class_id") or request.args.get("class_id")
    query = Student.query.filter(Student.status == "Active")
    classes_query = ClassRoom.query
    if current_user.role == "teacher":
        teacher = teacher_profile(current_user)
        class_ids = {row.class_id for row in Timetable.query.filter_by(teacher_id=teacher.id).all()} if teacher else set()
        if class_id and (not class_id.isdecimal() or int(class_id) not in class_ids):
            abort(403)
        if not class_id and request.method == "POST" and request.form.get("action") == "save":
            abort(400)
        classes_query = classes_query.filter(ClassRoom.id.in_(class_ids))
        query = query.filter(Student.class_id.in_(class_ids)) if class_id else query.filter(db.false())
    classes = classes_query.order_by(ClassRoom.name, ClassRoom.section).all()

    if class_id:
        try:
            query = query.filter_by(class_id=int(class_id))
        except (TypeError, ValueError):
            class_id = None
            flash("Invalid class selection. Showing all active students.", "warning")

    students = query.order_by(Student.first_name, Student.last_name).all()

    # The Load button is a read-only operation. It intentionally does not
    # enter the save block below.
    action = request.form.get("action") if request.method == "POST" else None
    if request.method == "POST" and action == "save":
        allowed_statuses = {"Present", "Absent", "Late", "Leave"}
        try:
            attendance_rows = {
                row.student_id: row for row in Attendance.query.filter(
                    Attendance.date == d, Attendance.student_id.in_([s.id for s in students])
                ).order_by(Attendance.id).all()
            }
            for s in students:
                status = request.form.get(f"student_{s.id}", "").strip()
                if not status:
                    continue
                if status not in allowed_statuses:
                    raise ValueError("Invalid attendance status.")
                if s.id in attendance_rows:
                    attendance_rows[s.id].status = status
                else:
                    db.session.add(Attendance(student_id=s.id, date=d, status=status))

            db.session.commit()
            flash("Attendance saved successfully.", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Attendance save failed")
            flash("Attendance could not be saved. Please try again.", "danger")

    existing = {
        a.student_id: a.status
        for a in Attendance.query.filter_by(date=d).filter(Attendance.student_id.in_([s.id for s in students])).all()
    }
    return render_template(
        "students/attendance.html",
        students=students,
        classes=classes,
        selected_date=selected_date,
        class_id=class_id,
        existing=existing,
    )

@students_bp.route("/attendance/report")
@login_required
@roles_required("admin","teacher","staff","admission_officer")
def attendance_report():
    from sqlalchemy import func
    query = db.session.query(Student, func.count(Attendance.id),
                             func.sum(db.case((Attendance.status == "Present", 1), else_=0))).outerjoin(Attendance)
    if current_user.role == "teacher":
        teacher = teacher_profile(current_user)
        assigned = Timetable.query.with_entities(Timetable.class_id).filter_by(teacher_id=teacher.id) if teacher else None
        query = query.filter(Student.class_id.in_(assigned.selectable)) if assigned is not None else query.filter(db.false())
    rows = query.group_by(Student.id).order_by(Student.first_name).all()
    return render_template("students/attendance_report.html", rows=rows)
