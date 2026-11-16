from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func
from .models import (Student, Teacher, FeeInvoice, FeePayment, Attendance, Result,
                     Timetable, Employee, Payroll, Exam, LibraryIssue,
                     TransportAssignment, HostelAllocation, AcademicSession, OnlineFeePayment)
from .academics import grade_for
from .auth import end_session
from .online_payments import gateway_config
from .notifications import announcements, support_url

portal_bp=Blueprint('portal', __name__, url_prefix='/portal')

@portal_bp.route('/')
@login_required
def index():
    if current_user.role == 'student':
        return student_portal()
    data={}
    if current_user.role=='parent':
        if current_user.parent_id is not None:
            children = Student.query.filter_by(parent_id=current_user.parent_id, status="Active")
            data["students"] = children.order_by(Student.first_name).all()
            data["invoices"] = (FeeInvoice.query.join(Student)
                                .filter(Student.parent_id == current_user.parent_id, Student.status == "Active")
                                .order_by(FeeInvoice.id.desc()).limit(20).all())
    elif current_user.role=='teacher':
        teacher = current_user.teacher
        if teacher is None and not current_user.family_or_demo_teacher:
            employee = Employee.query.filter_by(employee_no=current_user.username).first()
            teacher = employee.teacher if employee else None
        data["teacher"] = teacher
        if teacher:
            data["timetable"] = Timetable.query.filter_by(teacher_id=teacher.id).order_by(Timetable.day, Timetable.start_time).all()
    elif current_user.role=='accountant':
        data['invoices']=FeeInvoice.query.order_by(FeeInvoice.id.desc()).limit(10).all()
        data['payments']=FeePayment.query.order_by(FeePayment.id.desc()).limit(10).all()
    elif current_user.role=='staff':
        data['students']=Student.query.filter_by(status='Active').order_by(Student.first_name).limit(20).all()
    elif current_user.role=='librarian':
        from .models import Book, LibraryIssue
        data['books']=Book.query.order_by(Book.title).limit(20).all()
        data['issues']=LibraryIssue.query.filter_by(status='Issued').order_by(LibraryIssue.id.desc()).limit(20).all()
    else:
        data['students']=Student.query.filter_by(status='Active').limit(10).all()
    return render_template('portal/index.html', data=data, notices=announcements(current_user.role), school_whatsapp=support_url())


def student_portal():
    student = current_user.student
    if not student or student.status != 'Active':
        end_session()
        flash('Your student portal account is not linked to an active student record. Please contact the school office.', 'danger')
        return redirect(url_for('auth.login'))

    attendance = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.date.desc()).limit(180).all()
    total_att = len(attendance)
    present = sum(1 for a in attendance if str(a.status).lower() in ('present','late'))
    absent = sum(1 for a in attendance if str(a.status).lower() == 'absent')
    attendance_pct = round((present / total_att) * 100, 1) if total_att else 0

    results = Result.query.filter_by(student_id=student.id).join(Exam, Result.exam_id==Exam.id).filter(Exam.approved_at.is_not(None)).order_by(Exam.id.desc(), Result.id.desc()).all()
    exams = []
    seen=set()
    for r in results:
        if r.exam_id in seen: continue
        rows=[x for x in results if x.exam_id==r.exam_id]
        total=sum(float(x.total or 0) for x in rows)
        obtained=sum(float(x.marks or 0) for x in rows)
        pct=round(obtained/total*100,2) if total else 0
        exams.append({'exam':r.exam,'rows':rows,'total':total,'obtained':obtained,'pct':pct,'grade':grade_for(pct)})
        seen.add(r.exam_id)

    invoices=FeeInvoice.query.filter_by(student_id=student.id).order_by(FeeInvoice.id.desc()).all()
    payments=(FeePayment.query.join(FeeInvoice, FeePayment.invoice_id==FeeInvoice.id)
              .filter(FeeInvoice.student_id==student.id).order_by(FeePayment.paid_at.desc()).limit(20).all())
    total_billed=round(sum(float(i.amount or 0) for i in invoices),2)
    total_paid=round(sum(float(i.paid or 0) for i in invoices),2)
    total_due=round(max(total_billed-total_paid,0),2)

    class_id=student.class_id
    timetable=(Timetable.query.filter_by(class_id=class_id).order_by(Timetable.day, Timetable.start_time).all()
               if class_id else [])
    notices = announcements('student')
    library=LibraryIssue.query.filter_by(student_id=student.id).order_by(LibraryIssue.id.desc()).limit(10).all()

    transport=None
    if _module_enabled('transport'):
        transport=TransportAssignment.query.filter_by(student_id=student.id,status='Active').order_by(TransportAssignment.id.desc()).first()
    hostel=None
    if _module_enabled('hostel'):
        hostel=HostelAllocation.query.filter_by(student_id=student.id,status='Active').order_by(HostelAllocation.id.desc()).first()

    payment_gateway = gateway_config()
    pending_online_payments = {}
    if payment_gateway:
        pending_online_payments = {
            payment.invoice_id: payment.id for payment in OnlineFeePayment.query.join(FeeInvoice).filter(
                FeeInvoice.student_id == student.id,
                OnlineFeePayment.environment == payment_gateway[0],
                OnlineFeePayment.state.in_(("pending", "review")),
                OnlineFeePayment.active_key.is_not(None),
            ).all()
        }
    return render_template('portal/student.html', student=student, attendance=attendance, school_whatsapp=support_url(),
        online_payment_mode=payment_gateway[0] if payment_gateway else None,
        pending_online_payments=pending_online_payments,
        attendance_pct=attendance_pct, present=present, absent=absent, total_att=total_att,
        exams=exams, invoices=invoices, payments=payments, total_billed=total_billed,
        total_paid=total_paid, total_due=total_due, timetable=timetable, notices=notices,
        library=library, transport=transport, hostel=hostel)


def _module_enabled(module):
    from .models import SystemSetting
    row=SystemSetting.query.filter_by(key=f'module.{module}').first()
    return True if row is None else str(row.value).lower() in {'1','true','yes','on'}
