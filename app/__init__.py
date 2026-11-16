from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

import click
from flask import Flask, render_template, request, abort, session
from flask_login import current_user
from config import Config
from .extensions import db, login_manager
from flask_migrate import Migrate
import logging
import os
import secrets
from logging.handlers import RotatingFileHandler

def local_secret(instance_path):
    path = Path(instance_path) / "session-secret"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(mode="w", encoding="ascii", dir=path.parent, delete=False) as temporary:
            temporary.write(secrets.token_hex(32))
        try:
            if os.name == "nt":
                os.rename(temporary.name, path)
            else:
                os.link(temporary.name, path)
        except FileExistsError:
            pass
        finally:
            Path(temporary.name).unlink(missing_ok=True)
    return path.read_text(encoding="ascii")


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    database_url = os.environ.get("DATABASE_URL", app.config["SQLALCHEMY_DATABASE_URI"])
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgres://"):]
    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_url,
        SECRET_KEY=os.environ.get("SCHOOL_ERP_SECRET_KEY"),
    )
    if test_config is not None:
        app.config.update(test_config)
    secret = app.config["SECRET_KEY"]
    if secret and (len(secret) < 32 or secret.lower().startswith(("replace", "change_me", "dev-only"))):
        raise RuntimeError("Set SCHOOL_ERP_SECRET_KEY to a random secret of at least 32 characters.")
    if not secret:
        if app.config["SESSION_COOKIE_SECURE"]:
            raise RuntimeError("Set SCHOOL_ERP_SECRET_KEY when using secure cookies.")
        app.config["SECRET_KEY"] = local_secret(app.instance_path)
    db.init_app(app)
    login_manager.init_app(app)
    Migrate(app, db)
    login_manager.login_view = "auth.login"

    from .models import User, SystemSetting
    from .auth import auth_bp, DEMO_ADMIN_VIEWS, PUBLIC_DEMO_USERS, public_demo_enabled
    from .assistant import assistant_bp, available_actions, ollama_model
    from .module_banners import module_banner
    from .main import main_bp
    from .students import students_bp
    from .academics import academics_bp
    from .finance import finance_bp
    from .online_payments import online_payments_bp
    from .library import library_bp
    from .admin import admin_bp
    from .timetable import timetable_bp
    from .reports import reports_bp
    from .notifications import notifications_bp
    from .hr import hr_bp
    from .operations import ops_bp
    from .portal import portal_bp
    from .exports import exports_bp
    from .profile import profile_bp
    from .api import api_bp
    from .production import production_bp
    from .mess import mess_bp
    from .accounts import accounts_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(assistant_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(students_bp, url_prefix="/students")
    app.register_blueprint(academics_bp, url_prefix="/academics")
    app.register_blueprint(finance_bp, url_prefix="/finance")
    app.register_blueprint(online_payments_bp)
    app.register_blueprint(library_bp, url_prefix="/library")
    app.register_blueprint(admin_bp)
    app.register_blueprint(timetable_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(hr_bp)
    app.register_blueprint(ops_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(exports_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(production_bp)
    app.register_blueprint(mess_bp)
    app.register_blueprint(accounts_bp)

    @app.before_request
    def student_portal_guard():
        endpoint = request.endpoint
        if endpoint is None or endpoint == "static" or endpoint == "online_payments.webhook":
            return None
        if (public_demo_enabled() and current_user.is_authenticated
                and current_user.username in PUBLIC_DEMO_USERS.values()):
            public_routes = {"auth.login", "auth.logout", "auth.demo_login", "main.dashboard",
                             "main.index", "portal.index", "api.health"}
            can_view = endpoint in public_routes or (
                current_user.username == "admin_demo" and endpoint in DEMO_ADMIN_VIEWS
            )
            if not can_view or (request.method not in ("GET", "HEAD") and endpoint not in
                                ("auth.logout", "auth.demo_login")):
                abort(403)
            return None
        if current_user.is_authenticated and current_user.family_or_demo_teacher:
            if endpoint not in {
                "auth.login", "auth.logout", "main.index", "main.dashboard",
                "portal.index", "profile.password", "api.health", "assistant.ask", "assistant.overview",
            }:
                abort(403)
            return None
        if not current_user.is_authenticated or current_user.role != "student":
            return None
        allowed = {
            "auth.login", "auth.logout", "main.index", "main.dashboard", "main.robots_txt",
            "main.global_search", "portal.index", "profile.password", "assistant.ask",
            "assistant.overview", "academics.report_card", "exports.report_card_pdf",
            "students.id_card", "exports.student_id_card_pdf", "students.verify_card",
            "exports.verify_voucher", "online_payments.start", "online_payments.status",
            "online_payments.verify_sandbox", "api.health",
        }
        if endpoint not in allowed:
            abort(403)
        return None

    @app.before_request
    def module_guard():
        if not current_user.is_authenticated: return None
        path=request.path
        mapping={'/hostel':'hostel','/mess':'mess','/transport':'transport','/inventory':'inventory','/library':'library'}
        for prefix,module in mapping.items():
            if path == prefix or path.startswith(prefix + '/'):
                row=SystemSetting.query.filter_by(key=f'module.{module}').first()
                enabled = True if row is None else str(row.value).lower() in {'1','true','yes','on'}
                if not enabled: abort(404)
                break
        return None

    @app.before_request
    def csrf_origin_guard():
        if request.endpoint in {"online_payments.webhook", "static"}:
            return None
        if request.endpoint == "auth.login" and request.method == "POST":
            request.max_content_length = 16 * 1024
        # Defense-in-depth CSRF protection for browser form submissions.
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        origin = request.headers.get("Origin")
        referer = request.headers.get("Referer")
        if origin or referer:
            try:
                supplied = urlsplit(origin or referer)
            except ValueError:
                abort(400, description="Invalid request origin.")
            expected = urlsplit(request.host_url)
            if (supplied.scheme, supplied.netloc) != (expected.scheme, expected.netloc):
                abort(400, description="Invalid request origin.")
        submitted = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        if not submitted or not secrets.compare_digest(submitted.encode(), session["csrf_token"].encode()):
            abort(400, description="Invalid CSRF token.")
        return None

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if current_user.is_authenticated or request.endpoint in {"auth.login", "auth.logout"}:
            response.headers.setdefault("Cache-Control", "no-store")
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.context_processor
    def template_helpers():
        from .access import module_enabled
        return {"module_enabled": module_enabled, "assistant_actions": available_actions,
                "public_demo_enabled": public_demo_enabled(), "demo_admin_views": DEMO_ADMIN_VIEWS,
                "assistant_ollama_configured": bool(ollama_model()), "module_banner": module_banner}

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404, message="Page not found."), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("error.html", code=500, message="An unexpected server error occurred."), 500

    log_dir = os.path.join(app.instance_path, "logs")
    os.makedirs(log_dir, exist_ok=True)
    if not any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
        handler = RotatingFileHandler(os.path.join(log_dir, "school_erp.log"), maxBytes=2*1024*1024, backupCount=5)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)

    with app.app_context():
        if app.config.get("AUTO_CREATE_DB", True):
            db.create_all()
        if app.config.get("AUTO_SCHEMA_UPGRADE", True):
            from .schema_upgrade import ensure_columns
            ensure_columns()
        from .models import SequenceCounter
        for code_type in ["student", "invoice", "receipt", "employee", "login_attempt"]:
            if not SequenceCounter.query.filter_by(code_type=code_type).first():
                try:
                    with db.session.begin_nested():
                        db.session.add(SequenceCounter(code_type=code_type, current_value=0))
                        db.session.flush()
                except Exception:
                    db.session.rollback()
        defaults = {"hostel":"0","mess":"1","transport":"1","inventory":"1","library":"1","whatsapp":"0","bank_integration":"0"}
        for key,value in defaults.items():
            if not SystemSetting.query.filter_by(key=f"module.{key}").first():
                db.session.add(SystemSetting(key=f"module.{key}", value=value))
        db.session.commit()

    @app.cli.command("set-admin-password")
    @click.password_option()
    def set_admin_password(password):
        if len(password) < 12:
            raise click.ClickException("Use a password of at least 12 characters.")
        admin = User.query.filter_by(username="admin").first()
        if admin is None:
            admin = User(username="admin", role="admin")
            db.session.add(admin)
        elif admin.role != "admin":
            raise click.ClickException("The username admin belongs to a different role.")
        admin.set_password(password)
        db.session.commit()
        click.echo("Administrator password saved.")

    return app
