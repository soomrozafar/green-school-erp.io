from urllib.parse import urlencode

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from .access import roles_required
from .extensions import db
from .models import AuditLog, Notification, Student, SystemSetting, WhatsAppMessage
from .validators import whatsapp_number

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")
AUDIENCES = ("All", "Students", "Parents", "Teachers", "Staff")


def announcements(role, limit=8):
    audience = {"student": "Students", "parent": "Parents", "teacher": "Teachers"}.get(role, "Staff")
    return Notification.query.filter(
        Notification.is_active.is_(True), Notification.audience.in_(("All", audience))
    ).order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit).all()


def support_url():
    contact = SystemSetting.query.filter_by(key="communication.whatsapp_support").first()
    number = whatsapp_number(contact.value) if contact else None
    return f"https://wa.me/{number}?{urlencode({'text': 'Hello, I need help with Green School ERP.'})}" if number else None


@notifications_bp.route("/", methods=["GET", "POST"])
@login_required
@roles_required("staff", "principal", "vice_principal")
def index():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        message = request.form.get("message", "").strip()
        audience = request.form.get("audience", "All")
        if not 1 <= len(title) <= 180 or not 1 <= len(message) <= 4000 or audience not in AUDIENCES:
            flash("Enter a title, message and valid audience.", "warning")
        else:
            db.session.add(Notification(title=title, message=message, audience=audience))
            db.session.add(AuditLog(user_id=current_user.id, action="Create Notification",
                                    module="Communication", details=title))
            db.session.commit()
            flash("Announcement published.", "success")
        return redirect(url_for("notifications.index"), code=303)
    audience = request.args.get("audience")
    query = Notification.query
    if audience in AUDIENCES:
        query = query.filter_by(audience=audience)
    page = query.order_by(Notification.id.desc()).paginate(per_page=25, error_out=False)
    return render_template("notifications.html", notifications=page.items, page=page,
                           audience=audience, audiences=AUDIENCES)


@notifications_bp.post("/<int:notice_id>/archive")
@login_required
@roles_required("staff", "principal", "vice_principal")
def archive(notice_id):
    notice = db.get_or_404(Notification, notice_id)
    if notice.is_active:
        notice.is_active = False
        db.session.add(AuditLog(user_id=current_user.id, action="Archive Notification",
                                module="Communication", details=notice.title))
        db.session.commit()
    flash("Announcement archived.", "success")
    return redirect(url_for("notifications.index"), code=303)


@notifications_bp.route("/whatsapp", methods=["GET", "POST"])
@login_required
@roles_required("staff", "admission_officer", "accountant")
def whatsapp():
    if request.method == "POST":
        ids = set(request.form.getlist("student_ids", type=int))
        message = request.form.get("message", "").strip()
        if not 1 <= len(ids) <= 250 or not 1 <= len(message) <= 2000:
            flash("Select up to 250 students and enter a message of up to 2,000 characters.", "warning")
        else:
            students = Student.query.options(joinedload(Student.parent)).filter(
                Student.id.in_(ids), Student.status == "Active").all()
            by_number = set()
            missing = len(ids) - len(students)
            for student in students:
                candidates = [student.phone]
                if student.parent:
                    candidates += [student.parent.mobile, student.parent.phone]
                number = next((valid_number for raw in candidates if (valid_number := whatsapp_number(raw))), None)
                if not number:
                    missing += 1
                elif number not in by_number:
                    by_number.add(number)
                    db.session.add(WhatsAppMessage(student_id=student.id, phone="+" + number,
                                                   message=message, status="Prepared"))
            db.session.commit()
            flash(f"{len(by_number)} unique WhatsApp drafts prepared. {missing} student records skipped for missing or invalid contact.", "info")
        return redirect(url_for("notifications.whatsapp"), code=303)

    messages = WhatsAppMessage.query.order_by(WhatsAppMessage.id.desc()).limit(50).all()
    links = {}
    for item in messages:
        number = whatsapp_number(item.phone)
        if number:
            links[item.id] = f"https://wa.me/{number}?{urlencode({'text': item.message})}"
    return render_template("whatsapp.html", students=Student.query.options(joinedload(Student.parent))
                           .filter_by(status="Active").order_by(Student.first_name).all(),
                           messages=messages, links=links)
