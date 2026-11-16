from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from .extensions import db
from .models import MessMenu
from .access import roles_required

mess_bp=Blueprint('mess',__name__,url_prefix='/mess')

@mess_bp.route('/',methods=['GET','POST'])
@login_required
@roles_required('admin','operations_admin')
def index():
    if request.method=='POST':
        try:
            m=MessMenu(menu_date=datetime.strptime(request.form['menu_date'],'%Y-%m-%d').date(),meal_type=request.form['meal_type'],menu=request.form['menu'].strip(),estimated_cost=float(request.form.get('estimated_cost') or 0),created_by=current_user.id)
            db.session.add(m); db.session.commit(); flash('Mess menu saved.','success')
        except (ValueError,TypeError): db.session.rollback(); flash('Please enter valid mess data.','danger')
    return render_template('operations/mess.html',menus=MessMenu.query.order_by(MessMenu.menu_date.desc(),MessMenu.id.desc()).limit(100).all())
