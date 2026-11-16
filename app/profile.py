from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from .extensions import db

profile_bp=Blueprint('profile', __name__, url_prefix='/profile')

@profile_bp.route('/password', methods=['GET','POST'])
@login_required
def password():
    if request.method=='POST':
        if not current_user.check_password(request.form.get('current_password','')):
            flash('Current password is incorrect.','danger')
        elif len(request.form.get('new_password','')) < 8:
            flash('New password must be at least 8 characters.','danger')
        elif request.form.get('new_password') != request.form.get('confirm_password'):
            flash('New passwords do not match.','danger')
        else:
            current_user.set_password(request.form['new_password']); db.session.commit(); flash('Password changed successfully.','success'); return redirect(url_for('main.dashboard'))
    return render_template('profile/password.html')
