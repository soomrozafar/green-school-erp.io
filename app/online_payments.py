from datetime import datetime, timedelta, UTC
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import hmac
import json
import os
import re
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from .access import roles_required
from .codes import next_code
from .extensions import db
from .models import AuditLog, FeeInvoice, FeePayment, OnlineFeePayment

online_payments_bp = Blueprint("online_payments", __name__)
API_HOSTS = {"sandbox": "https://sandbox.api.getsafepay.com", "production": "https://api.getsafepay.com"}
CHECKOUT_HOSTS = {"sandbox": API_HOSTS["sandbox"], "production": "https://getsafepay.com"}
# The gateway redirects the slashless POST with 301. Use the canonical URL to keep the body and merchant header.
TRACKER_SETUP_PATH = "/order/payments/v3/"
USER_AGENT = "SchoolManagementERP/1.0"
MERCHANT_ID = re.compile(r"sec_[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
MERCHANT_KEY_HINT = "Safepay requires the Public API Key from Developer > API Keys (sec_ followed by a UUID). Ask Accounts to check it."


def gateway_config():
    mode = os.environ.get("SAFEPAY_ENVIRONMENT", "sandbox")
    public, secret, webhook, base = (
        os.environ.get(key, "").strip() for key in (
            "SAFEPAY_PUBLIC_KEY", "SAFEPAY_SECRET_KEY", "SAFEPAY_WEBHOOK_SECRET", "SCHOOL_ERP_PUBLIC_URL",
        )
    )
    try:
        host = urlsplit(base)
    except ValueError:
        return None
    if (mode not in API_HOSTS or not all((public, secret, host.hostname))
            or host.username or host.password or host.query or host.fragment):
        return None
    loopback_sandbox = mode == "sandbox" and host.hostname in {"127.0.0.1", "localhost", "::1"}
    if not ((host.scheme == "https" and webhook) or
            (loopback_sandbox and host.scheme in {"http", "https"})):
        return None
    return mode, public, secret, webhook, base.rstrip("/")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _provider_post(mode, path, secret, payload=None):
    call = Request(API_HOSTS[mode] + path, method="POST",
                   headers={"X-SFPY-MERCHANT-SECRET": secret, "Content-Type": "application/json",
                            "User-Agent": USER_AGENT},
                   data=json.dumps(payload or {}).encode())
    with build_opener(NoRedirect()).open(call, timeout=12) as response:
        return json.loads(response.read(65536))["data"]



def _sandbox_tracker(secret, tracker):
    call = Request(API_HOSTS["sandbox"] + "/reporter/api/v1/payments/" + quote(tracker, safe=""),
                   headers={"X-SFPY-MERCHANT-SECRET": secret, "Accept": "application/json",
                            "User-Agent": USER_AGENT})
    with build_opener(NoRedirect()).open(call, timeout=12) as response:
        data = json.loads(response.read(65536))["data"]
        if not isinstance(data, dict):
            raise ValueError("Unexpected Safepay reporter response")
        tracker = data.get("tracker", data)
        if not isinstance(tracker, dict):
            raise ValueError("Unexpected Safepay tracker response")
        return tracker


def _checkout_error_message(error):
    generic = "Could not open Safepay checkout. Please try again."
    if not isinstance(error, HTTPError):
        return generic
    try:
        body = error.read(4096)
    except OSError:
        body = b""
    if error.code == 403 and body.strip() == b"error code: 1010":
        return "Safepay blocked the connection before checking credentials. Ask Accounts to review gateway access."
    try:
        fields = json.loads(body)["status"]["errors"]
        errors = " ".join(item.lower() for item in fields if isinstance(item, str))
    except (ValueError, KeyError, TypeError, AttributeError):
        errors = ""
    if error.code == 400 and errors.startswith("merchant_api_key:"):
        return MERCHANT_KEY_HINT
    if error.code == 404 and "merchant with api key" in errors and "not found" in errors:
        return "Safepay did not find this merchant in the selected environment. Ask Accounts to check the sandbox or live key pair."
    if error.code in {401, 403}:
        return "Safepay could not authenticate the checkout. Ask Accounts to check the Private API Secret Key."
    if error.code == 400:
        return "Safepay rejected the invoice details. Ask Accounts to review the amount, currency and enabled payment methods."
    return generic

def _minor(value):
    return int((Decimal(str(value or 0)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _own_invoice(invoice_id):
    if current_user.role != "student" or not current_user.student or current_user.student.status != "Active":
        abort(403)
    return FeeInvoice.query.filter_by(id=invoice_id, student_id=current_user.student_id).first_or_404()


def _invoice_lock(invoice_id):
    # UPDATE obtains a writer lock on SQLite and a row lock on PostgreSQL.
    FeeInvoice.query.filter_by(id=invoice_id).update({FeeInvoice.paid: FeeInvoice.paid})


@online_payments_bp.post("/portal/fees/<int:invoice_id>/pay")
@login_required
def start(invoice_id):
    invoice = _own_invoice(invoice_id)
    config = gateway_config()
    if not config:
        abort(503, description="Online payments are awaiting Safepay configuration.")
    mode, public, secret, _, base = config
    if not MERCHANT_ID.fullmatch(public):
        flash(MERCHANT_KEY_HINT, "danger")
        return redirect(url_for("portal.index"), code=303)

    _invoice_lock(invoice.id)
    db.session.refresh(invoice)
    amount = _minor(invoice.amount) - _minor(invoice.paid)
    if amount <= 0 or invoice.status in {"Cancelled", "Voided"}:
        db.session.rollback()
        flash("This invoice has no payable balance.", "info")
        return redirect(url_for("portal.index"), code=303)

    reservation = f"{mode}:{invoice.id}"
    payment = OnlineFeePayment.query.filter_by(active_key=reservation).first()
    if payment and payment.state == "review":
        db.session.rollback()
        flash("The school accounts office needs to review this payment before you try again.", "warning")
        return redirect(url_for("portal.index"), code=303)
    if payment and not payment.tracker:
        # A stale setup never produced a checkout URL. Retire it so a retry can start.
        if payment.created_at > datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1):
            db.session.rollback()
            flash("Checkout is being prepared. Try again in a moment.", "info")
            return redirect(url_for("portal.index"), code=303)
        payment.state, payment.active_key = "failed", None
        db.session.flush()
        payment = None
    if payment and payment.amount_minor != amount:
        db.session.rollback()
        flash("The invoice balance changed. Contact the accounts office to review the existing checkout.", "warning")
        return redirect(url_for("portal.index"), code=303)
    if payment is None:
        payment = OnlineFeePayment(id=uuid4().hex, invoice_id=invoice_id, initiated_by=current_user.id,
                                   active_key=reservation, environment=mode, amount_minor=amount, state="creating")
        db.session.add(payment)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Checkout is already being prepared for this invoice.", "info")
        return redirect(url_for("portal.index"), code=303)

    stage = "create tracker" if not payment.tracker else "create checkout token"
    try:
        if not payment.tracker:
            data = _provider_post(mode, TRACKER_SETUP_PATH, secret, {
                "merchant_api_key": public, "intent": "CYBERSOURCE", "mode": "payment",
                "entry_mode": "raw", "currency": "PKR", "amount": amount, "include_fees": False,
                "metadata": {"order_id": payment.id, "source": "school-erp"},
            })
            tracker = data["tracker"]["token"]
            if not isinstance(tracker, str) or not tracker.startswith("track_") or len(tracker) > 90:
                raise ValueError("Unexpected tracker")
            payment.tracker, payment.state = tracker, "pending"
            db.session.commit()
        stage = "create checkout token"
        passport = _provider_post(mode, "/client/passport/v1/token", secret)
        if not isinstance(passport, str) or not passport:
            raise ValueError("Unexpected checkout token")
    except (OSError, ValueError, KeyError, TypeError) as error:
        code = error.code if isinstance(error, HTTPError) else None
        current_app.logger.warning("Safepay %s failed for ERP reference %s (%s, HTTP %s)",
                                   stage, payment.id, type(error).__name__, code or "none")
        if not payment.tracker:
            payment.state, payment.active_key = "failed", None
            db.session.commit()
        flash(_checkout_error_message(error), "danger")
        return redirect(url_for("portal.index"), code=303)

    return_path = base + url_for("online_payments.status", payment_id=payment.id)
    fields = urlencode({"environment": mode, "tracker": payment.tracker, "tbt": passport,
                        "source": "hosted", "redirect_url": return_path, "cancel_url": return_path})
    response = redirect(f"{CHECKOUT_HOSTS[mode]}/embedded?{fields}", code=303)
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@online_payments_bp.get("/portal/fees/online/<payment_id>")
@login_required
def status(payment_id):
    payment = db.get_or_404(OnlineFeePayment, payment_id)
    _own_invoice(payment.invoice_id)
    return render_template("portal/online_payment.html", payment=payment)


@online_payments_bp.post("/portal/fees/online/<payment_id>/verify")
@login_required
def verify_sandbox(payment_id):
    payment = db.get_or_404(OnlineFeePayment, payment_id)
    _own_invoice(payment.invoice_id)
    config = gateway_config()
    if payment.environment != "sandbox" or not config or config[0] != "sandbox":
        abort(403)
    return_url = url_for("online_payments.status", payment_id=payment.id)
    if payment.state != "pending" or not payment.tracker:
        return redirect(return_url, code=303)
    try:
        tracker = _sandbox_tracker(config[2], payment.tracker)
        if tracker["token"] != payment.tracker or tracker["environment"] != "sandbox":
            raise ValueError("Unexpected sandbox tracker")
        if tracker["state"] != "TRACKER_ENDED":
            flash("Safepay has not confirmed the test payment yet.", "info")
            return redirect(return_url, code=303)
        total = tracker["purchase_totals"]["quote_amount"]
        matched = (total["currency"] == "PKR" and type(total["amount"]) is int
                   and total["amount"] == payment.amount_minor)
    except (OSError, KeyError, ValueError, TypeError):
        current_app.logger.warning("Safepay sandbox verification failed for ERP reference %s", payment.id)
        flash("Could not check with Safepay. Please try again.", "warning")
        return redirect(return_url, code=303)

    _invoice_lock(payment.invoice_id)
    db.session.refresh(payment)
    if payment.state == "pending":
        if matched:
            payment.state, payment.active_key = "test_paid", None
        else:
            payment.state = "review"
    db.session.commit()
    return redirect(return_url, code=303)


@online_payments_bp.get("/finance/online-payments")
@login_required
@roles_required("admin", "accountant")
def history():
    payments = OnlineFeePayment.query.order_by(OnlineFeePayment.created_at.desc()).paginate(per_page=30, error_out=False)
    return render_template("finance/online_payments.html", payments=payments, configured=bool(gateway_config()))


@online_payments_bp.post("/payments/safepay/webhook")
def webhook():
    config = gateway_config()
    if not config or not config[3]:
        abort(503)
    mode, _, _, secret, _ = config
    request.max_content_length = 64 * 1024
    payload = request.get_data()
    expected = hmac.new(secret.encode(), payload, hashlib.sha512).hexdigest()
    signature = request.headers.get("X-SFPY-SIGNATURE", "")
    if not hmac.compare_digest(expected.encode(), signature.encode()):
        abort(403)

    event = request.get_json(silent=True)
    if not isinstance(event, dict) or not isinstance(event.get("data"), dict):
        abort(400)
    kind = event.get("type")
    if kind not in {"payment.succeeded", "payment.refunded", "void.succeeded"}:
        return "", 204
    data = event["data"]
    tracker = data.get("tracker")
    if not isinstance(tracker, str):
        abort(400)
    payment = OnlineFeePayment.query.filter_by(tracker=tracker, environment=mode).first()
    if not payment:
        return "", 204
    _invoice_lock(payment.invoice_id)
    db.session.refresh(payment)
    db.session.refresh(payment.invoice)
    if kind != "payment.succeeded":
        if payment.state in {"paid", "test_paid", "pending"}:
            payment.state = "review"
        db.session.commit()
        return "", 204
    if payment.state != "pending":
        db.session.rollback()
        return "", 204

    invoice = payment.invoice
    if (data.get("state") != "TRACKER_ENDED" or data.get("currency") != "PKR"
            or type(data.get("amount")) is not int or data["amount"] != payment.amount_minor
            or _minor(invoice.amount) - _minor(invoice.paid) != payment.amount_minor
            or invoice.status in {"Cancelled", "Voided"}):
        payment.state = "review"
    elif mode == "sandbox":
        payment.state, payment.active_key = "test_paid", None
    else:
        amount = payment.amount_minor / 100
        receipt = FeePayment(invoice_id=invoice.id, receipt_no=next_code("receipt", "RCPT"),
                             amount=amount, payment_method="Safepay", reference=payment.tracker,
                             received_by=None)
        db.session.add(receipt)
        db.session.flush()
        invoice.paid, invoice.status = invoice.amount, "Paid"
        payment.state, payment.active_key, payment.receipt_id = "paid", None, receipt.id
        db.session.add(AuditLog(user_id=payment.initiated_by, action="Confirm Online Fee Payment",
                               module="Finance", details=f"{receipt.receipt_no} against {invoice.invoice_no}"))
    db.session.commit()
    return "", 204
