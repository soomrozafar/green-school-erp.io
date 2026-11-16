from functools import wraps
from flask import redirect, url_for, flash, abort
from flask_login import current_user
from .models import SystemSetting
from .extensions import db

ROLE_LABELS = {
    "admin": "Super Administrator",
    "admission_officer": "Admission Officer",
    "operations_admin": "Admin Department",
    "accountant": "Accountant",
    "hr_officer": "HR Officer",
    "teacher": "Teacher",
    "examination_officer": "Examination Officer",
    "principal": "Principal",
    "vice_principal": "Vice Principal",
    "staff": "Staff",
    "librarian": "Librarian",
    "student": "Student",
    "parent": "Parent / Guardian",
}

EXAM_APPROVERS = ("examination_officer", "principal", "vice_principal")


def teacher_profile(user):
    from .models import Teacher, Employee

    teachers = Teacher.query.join(Employee).filter(Teacher.status == "Active", Employee.status == "Active")
    if user.teacher_id is not None:
        return teachers.filter(Teacher.id == user.teacher_id).first()
    return teachers.filter(Employee.employee_no == user.username).first()


def roles_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role not in roles and current_user.role != "admin":
                return abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return deco


def module_enabled(module, default=True):
    try:
        setting = SystemSetting.query.filter_by(key=f"module.{module}").first()
        return default if setting is None else str(setting.value).lower() in {"1","true","yes","on"}
    except Exception:
        return default
