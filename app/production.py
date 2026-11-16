import os
import sqlite3
from datetime import datetime
from pathlib import Path
from flask import Blueprint, current_app, jsonify, redirect, url_for, flash, send_file, request, render_template
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from .extensions import db
from .models import AuditLog, LoginEvent, Student, FeeInvoice, FeePayment, Attendance, InventoryItem, HostelRoom, HostelAllocation, TransportAssignment

production_bp = Blueprint('production', __name__, url_prefix='/admin/system')


def _admin():
    return current_user.is_authenticated and current_user.role == 'admin'


@production_bp.before_request
def protect():
    if not _admin():
        return redirect(url_for('main.dashboard'))


@production_bp.route('/backup')
@login_required
def backup():
    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not uri.startswith('sqlite:///'):
        flash('Database backup download is currently implemented for SQLite deployments. Use your database provider backup tools for other databases.', 'warning')
        return redirect(url_for('main.dashboard'))
    db_path = uri.replace('sqlite:///', '', 1)
    if not os.path.isabs(db_path):
        db_path = os.path.join(current_app.instance_path, db_path)
    if not os.path.exists(db_path):
        flash('Database file was not found.', 'danger')
        return redirect(url_for('main.dashboard'))
    stamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path(current_app.instance_path) / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    out = backup_dir / f'school_erp_backup_{stamp}.db'
    src = sqlite3.connect(db_path)
    dest = sqlite3.connect(out)
    with dest:
        src.backup(dest)
    dest.close(); src.close()
    return send_file(out, as_attachment=True, download_name=out.name)


@production_bp.route('/health')
@login_required
def system_health():
    db.session.execute(db.text('SELECT 1'))
    return jsonify({'status': 'ok', 'database': 'connected', 'time_utc': datetime.utcnow().isoformat()})


@production_bp.route('/audit')
@login_required
def audit():
    page = max(request.args.get('page', 1, type=int), 1)
    per_page = min(max(request.args.get('per_page', 30, type=int), 10), 100)
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('admin/audit.html', logs=logs)


@production_bp.route('/login-history')
@login_required
def login_history():
    page = max(request.args.get('page', 1, type=int), 1)
    per_page = min(max(request.args.get('per_page', 30, type=int), 10), 100)
    events = LoginEvent.query.order_by(LoginEvent.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('admin/login_history.html', events=events)


@production_bp.route('/integrity')
@login_required
def integrity():
    checks = integrity_checks()
    failures = [(name, guidance) for name, ok, guidance in checks if not ok]
    request_lines = [
        "Review the School Management ERP in C:/SchoolManagementERP.",
        "Investigate the checks below using read-only queries. Reproduce any issue in a test database.",
        "Propose and test the smallest appropriate code fix. Ask for review before changing school records.",
    ]
    if failures:
        request_lines.extend(f"- {name}. {guidance}" for name, guidance in failures)
    else:
        request_lines.append("- Data integrity checks: no problems reported.")
        request_lines.append("- Profile slow workflows using a test dataset and report measured bottlenecks.")
    return render_template('admin/integrity.html', checks=checks, codex_request="\n".join(request_lines))


def integrity_checks():
    db.session.execute(db.text("SELECT 1"))
    return [
        ("Database connection", True, "Database query completed."),
        ("Students without admission number",
         not Student.query.filter((Student.admission_no.is_(None)) | (Student.admission_no == "")).first(),
         "Check admissions and assign a valid unique admission number."),
        ("Negative fee invoices", not FeeInvoice.query.filter(FeeInvoice.amount < 0).first(),
         "Review invoice amounts and supporting records."),
        ("Overpaid invoices", not FeeInvoice.query.filter(FeeInvoice.paid > FeeInvoice.amount).first(),
         "Reconcile payments against the original invoice before changing balances."),
        ("Negative inventory quantities", not InventoryItem.query.filter(InventoryItem.quantity < 0).first(),
         "Reconcile the stock count against inventory movements."),
        ("Hostel over-allocation", not _hostel_overallocated(),
         "Compare active allocations with room capacity."),
        ("Duplicate active transport assignments", not _duplicate_transport_assignments(),
         "Review the student's current route and close superseded assignments."),
    ]


def _hostel_overallocated():
    return (
        db.session.query(HostelRoom.id)
        .join(HostelAllocation, HostelAllocation.room_id == HostelRoom.id)
        .filter(HostelAllocation.status == "Active")
        .group_by(HostelRoom.id, HostelRoom.capacity)
        .having(db.func.count(HostelAllocation.id) > db.func.coalesce(HostelRoom.capacity, 0))
        .first() is not None
    )


def _duplicate_transport_assignments():
    rows = db.session.query(TransportAssignment.student_id).filter_by(status='Active').group_by(TransportAssignment.student_id).having(db.func.count(TransportAssignment.id) > 1).all()
    return len(rows)


@production_bp.route('/backups')
@login_required
def backups():
    backup_dir = Path(current_app.instance_path) / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(backup_dir.glob('*.db'), key=lambda x: x.stat().st_mtime, reverse=True)
    return render_template('admin/backups.html', backups=files)


@production_bp.route('/backup/<path:name>')
@login_required
def download_backup(name):
    safe = secure_filename(name)
    backup_dir = Path(current_app.instance_path) / 'backups'
    target = backup_dir / safe
    if not target.exists() or target.parent.resolve() != backup_dir.resolve():
        flash('Backup not found.', 'danger')
        return redirect(url_for('production.backups'))
    return send_file(target, as_attachment=True, download_name=target.name)
