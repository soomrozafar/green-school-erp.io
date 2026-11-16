from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user
from .models import Permission

def permission_required(module, action='view'):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.role == 'admin':
                return fn(*args, **kwargs)
            p = Permission.query.filter_by(role=current_user.role, module=module, action=action, allowed=True).first()
            if not p:
                flash('You do not have permission to perform this action.', 'danger')
                return redirect(url_for('main.dashboard'))
            return fn(*args, **kwargs)
        return wrapper
    return decorator
