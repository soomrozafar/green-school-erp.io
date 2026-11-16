from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from sqlalchemy import String, inspect as sa_inspect
from datetime import date, datetime
from .extensions import db
from .access import ROLE_LABELS
from .validators import whatsapp_number
from werkzeug.utils import secure_filename
import os, re, uuid
from .models import User, AcademicSession, ClassRoom, Subject, Parent, Permission, SystemSetting, BankAccount, Student, Teacher, Attendance, Exam, Result, FeeInvoice, Book, LibraryIssue, Timetable, FeePayment, Notification, FeeStructure, FeeInvoiceItem, Employee, GradeScale, Vehicle, TransportRoute, TransportAssignment, HostelRoom, HostelAllocation, InventoryItem, InventoryTransaction, MessMenu

admin_bp=Blueprint("admin",__name__,url_prefix="/admin")

def admin_only():
    return current_user.is_authenticated and current_user.role=="admin"

@admin_bp.before_request
def protect():
    if admin_only():
        return None
    return redirect(url_for("main.dashboard"))

@admin_bp.route("/users", methods=["GET","POST"])
def users():
    if request.method=="POST":
        if User.query.filter_by(username=request.form["username"]).first():
            flash("Username already exists.","danger")
        else:
            password=request.form.get("password", "")
            if len(password) < 8:
                flash("Password must be at least 8 characters.", "danger")
                return redirect(url_for("admin.users"), code=303)
            role=request.form.get("role","staff")
            if role not in ROLE_LABELS:
                flash("Select a supported ERP role.", "danger")
                return redirect(url_for("admin.users"), code=303)
            student_id=request.form.get("student_id")
            if role == "student":
                if not student_id or not student_id.isdigit():
                    flash("Select a student for the student portal account.", "danger")
                    return redirect(url_for("admin.users"), code=303)
                st=Student.query.get(int(student_id))
                if not st:
                    flash("Selected student was not found.", "danger")
                    return redirect(url_for("admin.users"), code=303)
                if User.query.filter(User.student_id==st.id).first():
                    flash("This student already has a portal account.", "danger")
                    return redirect(url_for("admin.users"), code=303)
            else:
                student_id=None
            teacher_id = request.form.get("teacher_id", type=int) if role == "teacher" else None
            if role == "teacher" and (not teacher_id or not Teacher.query.filter_by(id=teacher_id, status="Active").first()):
                flash("Select an active teacher profile.", "danger")
                return redirect(url_for("admin.users"), code=303)
            parent_id = request.form.get("parent_id", type=int) if role == "parent" else None
            if role == "parent" and (not parent_id or not db.session.get(Parent, parent_id)):
                flash("Select a guardian record for the parent portal account.", "danger")
                return redirect(url_for("admin.users"), code=303)
            u=User(username=request.form["username"].strip(),role=role,student_id=int(student_id) if student_id else None,
                   teacher_id=teacher_id, parent_id=parent_id)
            u.set_password(password); db.session.add(u); db.session.commit()
            flash("User created successfully.","success")
    return render_template("admin/users.html", users=User.query.order_by(User.id.desc()).all(),
                           students=Student.query.filter_by(status="Active").order_by(Student.first_name, Student.last_name).all(),
                           teachers=Teacher.query.filter_by(status="Active").all(), role_labels=ROLE_LABELS,
                           parents=Parent.query.order_by(Parent.name).all())

@admin_bp.route("/sessions", methods=["GET","POST"])
def sessions():
    if request.method=="POST":
        s=AcademicSession(name=request.form["name"],start_date=None,end_date=None,is_active=True)
        db.session.add(s); db.session.commit(); flash("Academic session created.","success")
    return render_template("admin/sessions.html", sessions=AcademicSession.query.order_by(AcademicSession.id.desc()).all())

@admin_bp.route("/classes", methods=["GET","POST"])
def classes():
    sessions=AcademicSession.query.all()
    if request.method=="POST":
        c=ClassRoom(name=request.form["name"],section=request.form["section"],capacity=int(request.form.get("capacity") or 40),session_id=int(request.form["session_id"]))
        db.session.add(c); db.session.commit(); flash("Class/section created.","success")
    return render_template("admin/classes.html", classes=ClassRoom.query.order_by(ClassRoom.id.desc()).all(),sessions=sessions)

@admin_bp.route("/subjects", methods=["GET","POST"])
def subjects():
    if request.method=="POST":
        s=Subject(code=request.form.get("code"),name=request.form["name"],max_marks=float(request.form.get("max_marks") or 100))
        db.session.add(s); db.session.commit(); flash("Subject created.","success")
    return render_template("admin/subjects.html", subjects=Subject.query.order_by(Subject.id.desc()).all())


@admin_bp.route("/permissions", methods=["GET", "POST"])
def permissions():
    roles = ["staff", "teacher", "accountant", "librarian", "admission_officer", "operations_admin", "student"]
    modules = ["students", "attendance", "academics", "finance", "hr", "library", "transport", "hostel", "inventory", "reports", "notifications"]
    actions = ["view", "create", "edit", "delete", "export"]
    if request.method == "POST":
        role = request.form.get("role")
        module = request.form.get("module")
        action = request.form.get("action")
        allowed = request.form.get("allowed") == "1"
        if role in roles and module in modules and action in actions:
            p = Permission.query.filter_by(role=role, module=module, action=action).first()
            if not p:
                p = Permission(role=role, module=module, action=action)
                db.session.add(p)
            p.allowed = allowed
            db.session.commit()
            flash("Permission updated.", "success")
    return render_template("admin/permissions.html", roles=roles, modules=modules, actions=actions, permissions=Permission.query.all())


@admin_bp.route('/modules', methods=['GET','POST'])
def modules():
    defaults = {
        'hostel': False, 'mess': True, 'transport': True, 'inventory': True, 'library': True,
        'whatsapp': False, 'bank_integration': False
    }
    if request.method == 'POST':
        for key, default in defaults.items():
            value = '1' if request.form.get(key) == '1' else '0'
            row = SystemSetting.query.filter_by(key=f'module.{key}').first()
            if not row:
                row = SystemSetting(key=f'module.{key}', value=value); db.session.add(row)
            else: row.value = value
        db.session.commit(); flash('Module settings updated.','success'); return redirect(url_for('admin.modules'))
    settings={k: (SystemSetting.query.filter_by(key=f'module.{k}').first().value if SystemSetting.query.filter_by(key=f'module.{k}').first() else ('1' if v else '0')) for k,v in defaults.items()}
    contact = SystemSetting.query.filter_by(key="communication.whatsapp_support").first()
    return render_template('admin/modules.html', settings=settings, whatsapp_contact=contact.value if contact else "")


@admin_bp.post("/communication/contact")
def communication_contact():
    supplied = request.form.get("whatsapp_number", "").strip()
    number = whatsapp_number(supplied) if supplied else ""
    if supplied and not number:
        flash("Enter a WhatsApp number with country code, such as +92 …", "warning")
    else:
        contact = SystemSetting.query.filter_by(key="communication.whatsapp_support").first()
        if contact is None:
            contact = SystemSetting(key="communication.whatsapp_support")
            db.session.add(contact)
        contact.value = f"+{number}" if number else ""
        db.session.commit()
        flash("School WhatsApp contact updated.", "success")
    return redirect(url_for("admin.modules"), code=303)

@admin_bp.route('/banks', methods=['GET','POST'])
def banks():
    if request.method == 'POST':
        b=BankAccount(bank_name=request.form['bank_name'].strip(),account_title=request.form['account_title'].strip(),account_number=request.form.get('account_number'),iban=request.form.get('iban'),branch=request.form.get('branch'),is_active=True)
        db.session.add(b); db.session.commit(); flash('Bank account saved.','success'); return redirect(url_for('admin.banks'))
    return render_template('admin/banks.html', banks=BankAccount.query.order_by(BankAccount.id.desc()).all())


# ---------------------------------------------------------------------------
# Admin Data Edit Center
# ---------------------------------------------------------------------------
EDITABLE_MODELS = {
    "users": User, "sessions": AcademicSession, "classes": ClassRoom,
    "subjects": Subject, "parents": Parent, "students": Student,
    "teachers": Teacher, "attendance": Attendance, "invoices": FeeInvoice, "books": Book,
    "library_issues": LibraryIssue, "timetable": Timetable,
    "payments": FeePayment, "notifications": Notification,
    "fee_structures": FeeStructure, "invoice_items": FeeInvoiceItem,
    "employees": Employee, "grades": GradeScale,
    "vehicles": Vehicle, "transport_routes": TransportRoute,
    "transport_assignments": TransportAssignment, "hostel_rooms": HostelRoom,
    "hostel_allocations": HostelAllocation, "inventory_items": InventoryItem,
    "inventory_transactions": InventoryTransaction, "mess_menu": MessMenu,
    "banks": BankAccount,
}

EDITABLE_LABELS = {
    "users":"Users", "sessions":"Academic Sessions", "classes":"Classes / Sections",
    "subjects":"Subjects", "parents":"Parents / Guardians", "students":"Students",
    "teachers":"Teachers", "attendance":"Attendance", "exams":"Exams",
    "results":"Results / Marks", "invoices":"Fee Invoices", "books":"Library Books",
    "library_issues":"Library Issues", "timetable":"Timetable", "payments":"Fee Payments",
    "notifications":"Notifications", "fee_structures":"Fee Structures",
    "invoice_items":"Invoice Items", "employees":"Employees",
    "grades":"Grade Scales", "vehicles":"Vehicles", "transport_routes":"Transport Routes",
    "transport_assignments":"Transport Assignments", "hostel_rooms":"Hostel Rooms",
    "hostel_allocations":"Hostel Allocations", "inventory_items":"Inventory Items",
    "inventory_transactions":"Inventory Transactions", "mess_menu":"Mess Menu",
    "banks":"Bank Accounts",
}

# Transaction/history tables are editable only because the administrator explicitly
# enters the Data Edit Center. Audit/login history is intentionally excluded.

def _display_value(obj):
    if obj is None:
        return "-"
    for attrs in (("name",), ("first_name","last_name"), ("employee_no","name"),
                  ("admission_no","first_name"), ("username",), ("title",), ("invoice_no",),
                  ("receipt_no",), ("registration_no",), ("code",), ("block","room_no"),
                  ("id",)):
        vals=[]
        for a in attrs:
            if hasattr(obj,a):
                v=getattr(obj,a)
                if v not in (None, ""):
                    vals.append(str(v))
        if vals:
            return " — ".join(vals)
    return str(getattr(obj,"id",obj))


def _field_meta(model, obj):
    mapper = sa_inspect(model)
    fields=[]
    for col in mapper.columns:
        if col.primary_key:
            continue
        if col.name in {"password_hash"}:
            continue
        value=getattr(obj,col.name,None)
        fk_target=None
        if col.foreign_keys:
            fk=next(iter(col.foreign_keys))
            fk_target=fk.column.table.name
        field_type=col.type.__class__.__name__.lower()
        input_type="text"
        if "date" in field_type and "time" not in field_type: input_type="date"
        elif "datetime" in field_type: input_type="datetime-local"
        elif "bool" in field_type: input_type="checkbox"
        elif any(x in field_type for x in ("integer","float","numeric","decimal")): input_type="number"
        elif "text" in field_type: input_type="textarea"
        fields.append({"name":col.name,"label":col.name.replace("_"," ").title(),"value":value,
                       "type":input_type,"required":bool(not col.nullable and col.default is None and col.server_default is None),
                       "fk":fk_target})
    return fields


def _coerce_value(col, raw):
    if raw is None: return None
    typ=col.type.__class__.__name__.lower()
    if raw == "" and col.nullable: return None
    if "bool" in typ: return raw in ("1","true","on","yes")
    if "integer" in typ: return int(raw) if raw != "" else None
    if any(x in typ for x in ("float","numeric","decimal")): return float(raw) if raw != "" else None
    if "date" in typ and "time" not in typ: return date.fromisoformat(raw) if raw else None
    if "datetime" in typ:
        return datetime.fromisoformat(raw) if raw else None
    return raw


@admin_bp.route("/data-edit")
def data_edit():
    modules=[]
    for key, model in EDITABLE_MODELS.items():
        modules.append({"key":key,"label":EDITABLE_LABELS[key],"count":model.query.count()})
    return render_template("admin/data_edit.html", modules=modules)


@admin_bp.route("/data-edit/<model_key>")
def data_edit_list(model_key):
    model=EDITABLE_MODELS.get(model_key)
    if not model:
        flash("Unknown data module.","danger")
        return redirect(url_for("admin.data_edit"))
    term = request.args.get("q", "").strip()[:80]
    columns = [c for c in sa_inspect(model).columns if not c.primary_key and c.name != "password_hash"]
    query = model.query
    if term:
        conditions = [c.istartswith(term, autoescape=True) for c in columns if isinstance(c.type, String)]
        if term.isascii() and term.isdecimal() and len(term) < 10:
            conditions.append(model.id == int(term))
        query = query.filter(db.or_(db.false(), *conditions))
    page = query.order_by(model.id.desc()).paginate(per_page=50, error_out=False)
    return render_template("admin/data_edit_list.html", model_key=model_key, model_label=EDITABLE_LABELS[model_key],
                           page=page, columns=columns, term=term)


@admin_bp.route("/data-edit/<model_key>/<int:record_id>", methods=["GET","POST"])
def data_edit_record(model_key, record_id):
    model=EDITABLE_MODELS.get(model_key)
    if not model:
        flash("Unknown data module.","danger")
        return redirect(url_for("admin.data_edit"))
    obj=db.session.get(model, record_id)
    if not obj:
        flash("Record not found.","danger")
        return redirect(url_for("admin.data_edit_list", model_key=model_key))
    fields=_field_meta(model,obj)
    if request.method == "GET" and request.args.get("view") == "1":
        return render_template("admin/data_record_view.html", record=obj, fields=fields,
                               model_key=model_key, title=EDITABLE_LABELS[model_key])
    choices={}
    for f in fields:
        if f["fk"]:
            target_table=f["fk"]
            target_model=next((m for m in EDITABLE_MODELS.values() if getattr(m,"__tablename__",None)==target_table),None)
            if target_model:
                choices[f["name"]]=target_model.query.order_by(target_model.id.desc()).limit(500).all()
    if request.method=="POST":
        try:
            mapper=sa_inspect(model)
            for f in fields:
                col=mapper.columns[f["name"]]
                raw=request.form.get(f["name"])
                if f["type"]=="checkbox":
                    raw=request.form.get(f["name"])
                setattr(obj,f["name"],_coerce_value(col,raw))
            # Password is deliberately handled separately and never shown as plaintext.
            if model is User and request.form.get("new_password"):
                password=request.form.get("new_password")
                if len(password)<8: raise ValueError("Password must be at least 8 characters.")
                obj.set_password(password)
            db.session.commit()
            flash(f"{EDITABLE_LABELS[model_key]} record updated successfully.","success")
            return redirect(url_for("admin.data_edit_list", model_key=model_key))
        except Exception as ex:
            db.session.rollback()
            flash(f"Record was not updated: {ex}","danger")
    return render_template("admin/data_edit_form.html", model_key=model_key, model_label=EDITABLE_LABELS[model_key], obj=obj, fields=fields, choices=choices, is_user=(model is User))
