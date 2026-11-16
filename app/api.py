from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from .extensions import db
from .models import Student, Teacher, Employee, FeeInvoice, FeePayment, Attendance, InventoryItem, Notification

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

@api_bp.get('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'school-management-erp', 'version': '8.0'})

@api_bp.get('/summary')
@login_required
def summary():
    return jsonify({
        'user': current_user.username,
        'role': current_user.role,
        'students': Student.query.count(),
        'teachers': Teacher.query.count(),
        'employees': Employee.query.count(),
        'fee_invoices': FeeInvoice.query.count(),
    })


@api_bp.get('/metrics')
@login_required
def metrics():
    billed = db.session.query(db.func.coalesce(db.func.sum(FeeInvoice.amount), 0)).scalar() or 0
    collected = db.session.query(db.func.coalesce(db.func.sum(FeePayment.amount), 0)).scalar() or 0
    attendance_total = Attendance.query.count()
    attendance_present = Attendance.query.filter(Attendance.status.in_(['Present', 'Late'])).count()
    return jsonify({
        'students': Student.query.count(),
        'teachers': Teacher.query.count(),
        'employees': Employee.query.count(),
        'inventory_items': InventoryItem.query.count(),
        'active_notifications': Notification.query.filter_by(is_active=True).count(),
        'fee_billed': float(billed),
        'fee_collected': float(collected),
        'fee_outstanding': max(float(billed)-float(collected), 0),
        'attendance_percentage': round(attendance_present / attendance_total * 100, 1) if attendance_total else 0,
    })
