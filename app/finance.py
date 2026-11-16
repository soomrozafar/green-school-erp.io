from datetime import datetime, date
import calendar
import re
from urllib.parse import urlencode

from sqlalchemy.exc import SQLAlchemyError
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from .extensions import db
from .models import FeeInvoice, FeePayment, FeeInvoiceItem, Student, AuditLog, FeeStructure, ClassRoom, AcademicSession, SequenceCounter, VoucherBatch
from .codes import next_code
from .access import roles_required
from sqlalchemy.orm import selectinload, joinedload

from .validators import whatsapp_number

finance_bp=Blueprint("finance",__name__)

def audit(action, details):
    db.session.add(AuditLog(user_id=current_user.id, action=action, module="Finance", details=details))

@finance_bp.route("/fees", methods=["GET","POST"])
@login_required
@roles_required("admin", "accountant")
def fees():
    students=Student.query.order_by(Student.first_name).all()
    if request.method=="POST":
        try:
            amount=float(request.form["amount"]); paid=float(request.form.get("paid") or 0)
            if amount<=0 or paid<0 or paid>amount: raise ValueError
            inv=FeeInvoice(invoice_no=(request.form.get("invoice_no") or "").strip() or next_code("invoice", "INV"),student_id=int(request.form["student_id"]),fee_type=request.form["fee_type"].strip(),amount=amount,paid=paid,status="Paid" if paid>=amount else ("Partial" if paid else "Unpaid"),due_date=datetime.strptime(request.form["due_date"], "%Y-%m-%d").date() if request.form.get("due_date") else None)
            db.session.add(inv); db.session.flush()
            if paid: db.session.add(FeePayment(receipt_no=next_code("receipt", "RCPT"), invoice_id=inv.id, amount=paid, payment_method=request.form.get("payment_method","Cash"), received_by=current_user.id))
            audit("Create Invoice", f"Invoice {inv.invoice_no} created for student ID {inv.student_id}"); db.session.commit(); flash("Fee invoice saved.","success")
        except (ValueError, TypeError): db.session.rollback(); flash("Please enter valid fee values.","danger")
    record_number = request.args.get("q", "").strip()[:80]
    overdue = request.args.get("overdue") == "1"
    if overdue:
        from .assistant import overdue_invoices
        records = overdue_invoices()
    else:
        records = FeeInvoice.query
    if record_number:
        records = records.filter_by(invoice_no=record_number)
    return render_template("finance/fees.html",
                           invoices=records.order_by(FeeInvoice.id.desc()).all(),
                           record_number=record_number, overdue=overdue, students=students)

@finance_bp.route("/structures", methods=["GET","POST"])
@login_required
@roles_required("admin", "accountant")
def structures():
    classes=ClassRoom.query.order_by(ClassRoom.name, ClassRoom.section).all(); sessions=AcademicSession.query.order_by(AcademicSession.id.desc()).all()
    if request.method=="POST":
        fs=FeeStructure(name=request.form["name"].strip(), class_id=int(request.form["class_id"]) if request.form.get("class_id") else None, session_id=int(request.form["session_id"]) if request.form.get("session_id") else None, amount=float(request.form["amount"]), frequency=request.form.get("frequency","Monthly"), description=request.form.get("description"))
        db.session.add(fs); db.session.commit(); flash("Fee structure saved.","success")
    return render_template("finance/structures.html", structures=FeeStructure.query.order_by(FeeStructure.id.desc()).all(), classes=classes, sessions=sessions)

@finance_bp.route("/payment", methods=["GET","POST"])
@login_required
@roles_required("admin", "accountant")
def payment():
    invoices=FeeInvoice.query.filter(FeeInvoice.paid < FeeInvoice.amount).order_by(FeeInvoice.id.desc()).all()
    if request.method=="POST":
        try:
            from .online_payments import _invoice_lock
            inv = db.get_or_404(FeeInvoice, int(request.form["invoice_id"]))
            _invoice_lock(inv.id)
            db.session.refresh(inv)
            amount=float(request.form["amount"]); remaining=round(inv.amount-inv.paid,2)
            if amount<=0 or amount>remaining: raise ValueError
            inv.paid=round(inv.paid+amount,2); inv.status="Paid" if inv.paid>=inv.amount else "Partial"
            receipt=FeePayment(receipt_no=next_code("receipt", "RCPT"),invoice_id=inv.id,amount=amount,payment_method=request.form.get("payment_method","Cash"),reference=request.form.get("reference"),received_by=current_user.id)
            db.session.add(receipt); audit("Record Payment",f"{receipt.receipt_no}: {amount:.2f} against {inv.invoice_no}"); db.session.commit(); flash(f"Payment recorded. Receipt: {receipt.receipt_no}","success"); return redirect(url_for("finance.payment"))
        except (ValueError,TypeError): db.session.rollback(); flash("Invalid payment amount or invoice.","danger")
    return render_template("finance/payment.html", invoices=invoices)


def _recommended_fee_month(today=None):
    """School billing recommendation; can be overridden by the user on the calendar."""
    today = today or date.today()
    # Default: same month, with the school's configured advance summer billing pattern.
    target_month = today.month
    target_year = today.year
    if today.month == 4:
        target_month = 6
    elif today.month == 5:
        target_month = 7
    return date(target_year, target_month, 1)

def _month_choices(year=None):
    year = year or date.today().year
    return [date(year, m, 1) for m in range(1, 13)]

def _parse_months(form):
    values=[]
    for raw in form.getlist('fee_months'):
        try:
            d=datetime.strptime(raw, '%Y-%m').date().replace(day=1)
            values.append(d)
        except ValueError:
            continue
    return sorted(set(values))

def _existing_month_invoices(student_id, fee_ids, months):
    if not months: return []
    invoices=[]
    for inv in FeeInvoice.query.filter_by(student_id=student_id).order_by(FeeInvoice.id).all():
        if inv.paid >= inv.amount: continue
        for item in (inv.items or []):
            if item.fee_structure_id in fee_ids and item.fee_month in months:
                invoices.append(inv); break
    return list({i.id:i for i in invoices}.values())

@finance_bp.route("/generate-voucher/<int:student_id>", methods=["GET", "POST"])
@login_required
@roles_required("admin", "admission_officer")
def generate_voucher(student_id):
    student = db.get_or_404(Student, student_id)
    structures = FeeStructure.query.filter_by(is_active=True).order_by(FeeStructure.name).all()
    today=date.today(); recommended=_recommended_fee_month(today)
    months=_month_choices(today.year)
    existing_due=[]
    if request.method == "POST":
        try:
            selected_ids = list(dict.fromkeys(int(x) for x in request.form.getlist("fee_structure_ids") if x.isdigit()))
            fee_months=_parse_months(request.form)
            if not selected_ids or not fee_months: raise ValueError("selection")
            structures_selected = FeeStructure.query.filter(FeeStructure.id.in_(selected_ids), FeeStructure.is_active.is_(True)).order_by(FeeStructure.name).all()
            if len(structures_selected) != len(selected_ids): raise ValueError("fees")
            existing_due=_existing_month_invoices(student.id, set(selected_ids), fee_months)
            existing_ids={i.id for i in existing_due}
            inv = FeeInvoice(invoice_no=next_code("invoice", "INV"), student_id=student.id, fee_type="Monthly / Multiple Fees", amount=0, paid=0, status="Unpaid", due_date=datetime.combine(fee_months[0], datetime.min.time()).date())
            db.session.add(inv); db.session.flush()
            total=0; new_items=0
            for month in fee_months:
                for fs in structures_selected:
                    duplicate=False
                    for old in existing_due:
                        duplicate = any(x.fee_structure_id==fs.id and x.fee_month==month for x in (old.items or []))
                        if duplicate: break
                    if duplicate: continue
                    amt=float(fs.amount or 0); total += amt; new_items += 1
                    db.session.add(FeeInvoiceItem(invoice_id=inv.id, fee_structure_id=fs.id, description=f"{fs.name} - {month.strftime('%B %Y')}", amount=amt, fee_month=month))
            if new_items == 0:
                db.session.delete(inv); db.session.commit()
                if existing_due:
                    from .exports import build_bulk_voucher_pdf
                    return build_bulk_voucher_pdf(existing_due)
                raise ValueError("nothing")
            inv.amount=round(total,2); inv.fee_type="Monthly / Multiple Fees"
            audit("Generate Voucher", f"Voucher {inv.invoice_no} for {student.admission_no}; months={','.join(m.strftime('%Y-%m') for m in fee_months)}; items={new_items}")
            db.session.commit()
            all_invoices=existing_due+[inv]
            from .exports import build_bulk_voucher_pdf
            return build_bulk_voucher_pdf(all_invoices) if len(all_invoices)>1 else redirect(url_for("finance.voucher", invoice_id=inv.id))
        except (ValueError, TypeError):
            db.session.rollback(); flash("Please select at least one fee item and one billing month.", "danger")
    return render_template("finance/generate_voucher.html", student=student, structures=structures, months=months, recommended=recommended, existing_due=existing_due)

@finance_bp.route("/bulk-vouchers", methods=["GET", "POST"])
@login_required
@roles_required("admin", "accountant", "admission_officer")
def bulk_vouchers():
    today = date.today()
    if request.method == "POST":
        selected = set(request.form.getlist("student_ids", type=int))
        fee_ids = set(request.form.getlist("fee_structure_ids", type=int))
        fee_months = _parse_months(request.form)
        try:
            batch = create_voucher_batch(selected, fee_ids, fee_months, today)
            db.session.commit()
            return redirect(url_for("finance.voucher_batch", batch_id=batch.id), code=303)
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Bulk voucher batch failed")
            flash("The batch could not be saved. No vouchers were created. Try again or ask an administrator to check the log.", "danger")

    classes = ClassRoom.query.order_by(ClassRoom.name, ClassRoom.section).all()
    structures = FeeStructure.query.filter_by(is_active=True).order_by(FeeStructure.name).all()
    class_id = request.args.get("class_id", "").strip()
    status = request.args.get("status", "Active").strip()
    query = Student.query.options(joinedload(Student.class_room))
    if class_id.isdigit():
        query = query.filter_by(class_id=int(class_id))
    if status:
        query = query.filter_by(status=status)
    recent_batches = VoucherBatch.query.filter_by(created_by=current_user.id).order_by(
        VoucherBatch.id.desc()
    ).limit(8).all()
    return render_template(
        "finance/bulk_vouchers.html", students=query.order_by(Student.first_name, Student.last_name).all(),
        classes=classes, structures=structures, class_id=class_id, status=status,
        months=_month_choices(today.year), recommended=_recommended_fee_month(today),
        recent_batches=recent_batches,
    )


def create_voucher_batch(selected, fee_ids, fee_months, today):
    if not selected or not fee_ids or not fee_months:
        raise ValueError("Select students, fee items and at least one billing month.")

    # Lock the sequence before reading existing charges so a retry cannot create a second batch of charges.
    sequence = SequenceCounter.query.filter_by(code_type="invoice")
    if not sequence.update({SequenceCounter.current_value: SequenceCounter.current_value}, synchronize_session=False):
        db.session.add(SequenceCounter(code_type="invoice", current_value=0))
        db.session.flush()
    counter = sequence.one()
    structures = FeeStructure.query.filter(
        FeeStructure.id.in_(fee_ids), FeeStructure.is_active.is_(True)
    ).order_by(FeeStructure.name).all()
    if len(structures) != len(fee_ids):
        raise ValueError("Refresh the page and reselect the active fee items.")

    students = Student.query.filter(Student.id.in_(selected)).order_by(
        Student.first_name, Student.last_name, Student.id
    ).all()
    if len(students) != len(selected):
        raise ValueError("Some selected students are no longer available. Refresh and try again.")

    previous_items = db.session.query(
        FeeInvoice.student_id, FeeInvoiceItem.fee_structure_id, FeeInvoiceItem.fee_month, FeeInvoice
    ).join(FeeInvoiceItem, FeeInvoiceItem.invoice_id == FeeInvoice.id).filter(
        FeeInvoice.student_id.in_(selected),
        FeeInvoiceItem.fee_structure_id.in_(fee_ids),
        FeeInvoiceItem.fee_month.in_(fee_months),
    ).order_by(FeeInvoice.id).all()
    billed = {(student_id, fee_id, month) for student_id, fee_id, month, _ in previous_items}
    invoices = {invoice.id: invoice for _, _, _, invoice in previous_items
                if (invoice.paid or 0) < invoice.amount}
    created = []
    for student in students:
        items = [
            FeeInvoiceItem(fee_structure_id=fee.id, description=f"{fee.name} - {month:%B %Y}",
                           amount=fee.amount or 0, fee_month=month)
            for month in fee_months for fee in structures
            if (student.id, fee.id, month) not in billed
        ]
        if not items:
            continue
        counter.current_value += 1
        invoice = FeeInvoice(
            invoice_no=f"INV-{today.year}-{counter.current_value:05d}", student=student,
            fee_type="Monthly / Multiple Fees", amount=round(sum(item.amount for item in items), 2),
            paid=0, status="Unpaid", due_date=items[0].fee_month, items=items,
        )
        db.session.add(invoice)
        created.append(invoice)

    if not invoices and not created:
        raise ValueError("The selected fees are already paid. No outstanding challans were found for these months.")
    db.session.flush()
    batch = VoucherBatch(created_by=current_user.id, invoice_ids=[*invoices, *(inv.id for inv in created)],
                         student_count=len(students), created_count=len(created))
    db.session.add(batch)
    audit("Bulk Generate Voucher", f"{len(students)} students, {len(created)} new and {len(invoices)} existing invoices")
    return batch


def _batch_invoices(batch_id, student_id=None):
    batch = db.get_or_404(VoucherBatch, batch_id)
    if batch.created_by != current_user.id and current_user.role != "admin":
        abort(404)
    query = FeeInvoice.query.options(
        joinedload(FeeInvoice.student).joinedload(Student.class_room),
        joinedload(FeeInvoice.student).joinedload(Student.parent), selectinload(FeeInvoice.items),
    ).filter(FeeInvoice.id.in_(batch.invoice_ids))
    if student_id is not None:
        query = query.filter_by(student_id=student_id)
    invoices = query.order_by(FeeInvoice.id).all()
    if student_id is not None and not invoices:
        abort(404)
    return batch, invoices


@finance_bp.get("/bulk-vouchers/batch/<int:batch_id>")
@login_required
@roles_required("admin", "accountant", "admission_officer")
def voucher_batch(batch_id):
    batch, invoices = _batch_invoices(batch_id)
    grouped = {}
    for invoice in invoices:
        grouped.setdefault(invoice.student_id, []).append(invoice)
    rows = []
    for student_id, items in grouped.items():
        student = items[0].student
        phone = whatsapp_number(student.phone)
        recipient = "Student"
        if not phone and student.parent:
            phone = whatsapp_number(student.parent.mobile) or whatsapp_number(student.parent.phone)
            recipient = "Guardian"
        message = "Assalam-o-Alaikum. Please see the attached fee challan from Green School."
        rows.append({
            "student": student, "invoices": items, "recipient": recipient, "phone": phone,
            "whatsapp": f"https://wa.me/{phone}?{urlencode({'text': message})}" if phone else None,
        })
    return render_template("finance/voucher_batch.html", batch=batch, rows=rows, invoice_count=len(invoices),
                           missing_contacts=sum(not row["phone"] for row in rows))


@finance_bp.get("/bulk-vouchers/batch/<int:batch_id>/pdf")
@finance_bp.get("/bulk-vouchers/batch/<int:batch_id>/students/<int:student_id>/pdf")
@login_required
@roles_required("admin", "accountant", "admission_officer")
def voucher_batch_pdf(batch_id, student_id=None):
    from .exports import build_bulk_voucher_pdf

    batch, invoices = _batch_invoices(batch_id, student_id)
    if not invoices:
        abort(404)
    name = f"fee-challans-batch-{batch.id}"
    if student_id is not None:
        name += f"-student-{student_id}"
    return build_bulk_voucher_pdf(invoices, filename=f"{name}.pdf")


@finance_bp.route("/voucher/<int:invoice_id>")
@login_required
@roles_required("admin", "accountant", "admission_officer")
def voucher(invoice_id):
    inv = db.get_or_404(FeeInvoice, invoice_id)
    return render_template("finance/voucher.html", invoice=inv, copies=["STUDENT COPY", "BANK COPY", "SCHOOL COPY"])
