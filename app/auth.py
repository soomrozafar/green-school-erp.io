from datetime import UTC, datetime, timedelta
import secrets

from flask import make_response, Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .teacher_checkin import check_in
from .models import LoginEvent, SequenceCounter, User

auth_bp = Blueprint("auth", __name__)
DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(32))
LEGACY_DEMO_USERS = {
    "admin_demo", "accountant_demo", "admission_demo", "staff_demo", "teacher_demo", "student_demo",
}


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method != "POST":
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    ip_address = request.remote_addr
    audit_name = username[:80] or "unknown"
    now = datetime.now(UTC).replace(tzinfo=None)
    # Reserve a slot before hashing, so concurrent workers see in-flight attempts.
    SequenceCounter.query.filter_by(code_type="login_attempt").update(
        {SequenceCounter.current_value: SequenceCounter.current_value}, synchronize_session=False
    )
    attempts = LoginEvent.query.filter(
        LoginEvent.event.in_(("failed_login", "login_pending")),
        LoginEvent.created_at >= now - timedelta(minutes=15),
    )
    global_attempts = LoginEvent.query.filter(
        LoginEvent.created_at >= now - timedelta(minutes=1),
        LoginEvent.event.in_(("login", "failed_login", "login_pending")),
    )
    locked = (attempts.filter(db.func.lower(LoginEvent.username) == audit_name.lower()).count() >= 5
              or attempts.filter_by(ip_address=ip_address).count() >= 30)
    if locked or global_attempts.count() >= 120:
        db.session.rollback()
        delay = 900 if locked else 60
        flash("Too many failed attempts. Please wait 15 minutes before trying again." if locked
              else "Too many sign-in requests. Please try again in one minute.", "danger")
        response = make_response(render_template("login.html"), 429)
        response.headers["Retry-After"] = str(delay)
        return response

    attempt = LoginEvent(username=audit_name, event="login_pending", ip_address=ip_address,
                         user_agent=request.user_agent.string[:255])
    db.session.add(attempt)
    db.session.commit()
    user = User.query.filter_by(username=username).first() if 0 < len(username) <= 80 else None
    password_hash = user.password_hash if user else DUMMY_HASH
    valid_password = 0 < len(password) <= 4096 and check_password_hash(password_hash, password)
    legacy_password = (username == "admin" and password == "admin123") or (
        username in LEGACY_DEMO_USERS and password == "Demo@12345"
    )
    accepted = bool(user and user.is_active and valid_password and not legacy_password)

    attempt.user_id = user.id if user else None
    if accepted and user.role == "teacher" and user.username != "teacher_demo":
        error = check_in(user, request.form)
        if error:
            attempt.event = "teacher_location_denied"
            db.session.commit()
            flash(error, "warning")
            return render_template("login.html"), 403
    attempt.event = "login" if accepted else "failed_login"
    db.session.commit()
    if accepted:
        session.clear()
        login_user(user)
        session["csrf_token"] = secrets.token_urlsafe(32)
        destination = "portal.index" if user.role == "student" or user.family_or_demo_teacher else "main.dashboard"
        return redirect(url_for(destination))

    flash("Invalid username or password.", "danger")
    return render_template("login.html")


@auth_bp.post("/logout")
@login_required
def logout():
    end_session()
    return redirect(url_for("auth.login"))


def end_session():
    session.clear()
    logout_user()
