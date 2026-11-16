from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required
from .access import roles_required
from .models import FeeInvoice, FeePayment, BankAccount

accounts_bp=Blueprint("accounts",__name__,url_prefix="/accounts")

@accounts_bp.route('/')
@login_required
@roles_required("admin","accountant")
def dashboard():
    invoices=FeeInvoice.query.all(); payments=FeePayment.query.all()
    total_billed=sum(float(x.amount or 0) for x in invoices); total_collected=sum(float(x.amount or 0) for x in payments)
    outstanding=round(total_billed-total_collected,2)
    return render_template('accounts/dashboard.html', total_billed=total_billed,total_collected=total_collected,outstanding=outstanding,invoices=invoices[-10:],banks=BankAccount.query.filter_by(is_active=True).all())

@accounts_bp.route('/vouchers')
@login_required
@roles_required("admin","accountant")
def vouchers(): return redirect(url_for('finance.bulk_vouchers'))

@accounts_bp.route('/collection')
@login_required
@roles_required("admin","accountant")
def collection(): return redirect(url_for('finance.payment'))
