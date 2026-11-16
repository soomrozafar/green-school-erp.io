import hashlib
import hmac
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from app.extensions import db
from app.models import FeeInvoice, FeePayment, OnlineFeePayment, Student, User
from tests_login_security import app, login_data


@pytest.fixture
def configured_gateway(monkeypatch):
    for key, value in {
        "SAFEPAY_ENVIRONMENT": "production",
        "SAFEPAY_PUBLIC_KEY": "sec_00000000-0000-0000-0000-000000000001",
        "SAFEPAY_SECRET_KEY": "mock-secret",
        "SAFEPAY_WEBHOOK_SECRET": "mock-webhook-secret",
        "SCHOOL_ERP_PUBLIC_URL": "https://erp.example.test",
    }.items():
        monkeypatch.setenv(key, value)
    calls = []

    def provider(mode, path, secret, payload=None):
        assert mode in {"production", "sandbox"}
        assert secret == "mock-secret"
        calls.append((path, payload))
        if path == "/order/payments/v3/":
            return {"tracker": {"token": "track_test_fee"}}
        assert path == "/client/passport/v1/token"
        return "test-passport"
    monkeypatch.setattr("app.online_payments._provider_post", provider)
    return calls


@pytest.fixture
def student_checkout(app):
    with app.app_context():
        student = Student(admission_no="ONLINE-QA-1", first_name="Test Student")
        other = Student(admission_no="ONLINE-QA-2", first_name="Other Student")
        invoice = FeeInvoice(student=student, invoice_no="ONLINE-01", fee_type="Tuition", amount=1000.50, paid=200)
        other_invoice = FeeInvoice(student=other, invoice_no="ONLINE-02", fee_type="Tuition", amount=200)
        user = User(username="student-pay", role="student", student=student)
        user.set_password("Local checkout test only")
        db.session.add_all([user, invoice, other_invoice])
        db.session.commit()
        invoice_id, other_id = invoice.id, other_invoice.id
    client = app.test_client()
    assert client.post("/login", data=login_data(client, "student-pay", "Local checkout test only")).status_code == 302
    return client, invoice_id, other_id


def submit_checkout(client, invoice_id):
    return client.post(f"/portal/fees/{invoice_id}/pay", data={
        "csrf_token": login_data(client)["csrf_token"], "amount": "1",
    })


def send_event(client, amount=80050, signature=True):
    body = json.dumps({"type": "payment.succeeded", "data": {
        "tracker": "track_test_fee", "currency": "PKR", "state": "TRACKER_ENDED", "amount": amount,
    }}).encode()
    digest = hmac.new(b"mock-webhook-secret", body, hashlib.sha512).hexdigest()
    return client.post("/payments/safepay/webhook", data=body, content_type="application/json",
                       headers={"X-SFPY-SIGNATURE": digest if signature else "invalid"})


def test_safepay_checkout_and_idempotent_receipt(app, configured_gateway, student_checkout):
    client, invoice_id, other_id = student_checkout
    assert b"Pay online" in client.get("/portal/").data
    assert submit_checkout(client, other_id).status_code == 404
    assert client.post(f"/portal/fees/{invoice_id}/pay").status_code == 400
    checkout = submit_checkout(client, invoice_id)
    assert checkout.status_code == 303
    url = urlsplit(checkout.location)
    assert url.hostname == "getsafepay.com"
    assert configured_gateway[0][1]["amount"] == 80050
    reference = parse_qs(url.query)["redirect_url"][0]
    assert reference.startswith("https://erp.example.test/portal/fees/online/")
    status_url = urlsplit(reference).path
    assert b"Waiting for Safepay confirmation" in client.get(status_url + "?success=true").data
    retry = submit_checkout(client, invoice_id)
    assert retry.status_code == 303
    assert len([path for path, _ in configured_gateway if path == "/order/payments/v3/"]) == 1
    assert send_event(client, signature=False).status_code == 403
    with app.app_context():
        assert FeePayment.query.count() == 0
    assert send_event(client).status_code == 204
    assert send_event(client).status_code == 204
    assert b"Payment confirmed" in client.get(status_url).data
    with app.app_context():
        invoice = db.session.get(FeeInvoice, invoice_id)
        assert invoice.status == "Paid" and invoice.paid == 1000.50
        receipt = FeePayment.query.one()
        assert receipt.amount == 800.50 and receipt.payment_method == "Safepay"


@pytest.mark.parametrize("sandbox", [True, False])
def test_sandbox_and_amount_mismatch_do_not_credit_invoice(app, configured_gateway, student_checkout, monkeypatch, sandbox):
    client, invoice_id, _ = student_checkout
    if sandbox:
        monkeypatch.setenv("SAFEPAY_ENVIRONMENT", "sandbox")
    assert submit_checkout(client, invoice_id).status_code == 303
    assert send_event(client, amount=80050 if sandbox else 100).status_code == 204
    with app.app_context():
        assert db.session.get(FeeInvoice, invoice_id).paid == 200
        assert FeePayment.query.count() == 0
        assert OnlineFeePayment.query.one().state == ("test_paid" if sandbox else "review")


def test_local_sandbox_verifies_without_webhook(app, configured_gateway, student_checkout, monkeypatch):
    client, invoice_id, _ = student_checkout
    monkeypatch.setenv("SAFEPAY_ENVIRONMENT", "sandbox")
    monkeypatch.setenv("SCHOOL_ERP_PUBLIC_URL", "http://127.0.0.1:5004")
    monkeypatch.delenv("SAFEPAY_WEBHOOK_SECRET")
    assert b"Test payment" in client.get("/portal/").data
    checkout = submit_checkout(client, invoice_id)
    return_url = parse_qs(urlsplit(checkout.location).query)["redirect_url"][0]
    assert return_url.startswith("http://127.0.0.1:5004/portal/fees/online/")
    status_path = urlsplit(return_url).path
    assert status_path.encode() in client.get("/portal/").data
    assert b"Verify test payment" in client.get(status_path).data

    def reporter(secret, tracker):
        assert secret == "mock-secret" and tracker == "track_test_fee"
        return {"token": tracker, "environment": "sandbox", "state": "TRACKER_ENDED",
                "purchase_totals": {"quote_amount": {"amount": 80050, "currency": "PKR"}}}

    monkeypatch.setattr("app.online_payments._sandbox_tracker", reporter)
    assert client.post(status_path + "/verify").status_code == 400
    token = login_data(client)["csrf_token"]
    assert client.post(status_path + "/verify", data={"csrf_token": token}).status_code == 303
    assert b"Sandbox payment confirmed" in client.get(status_path).data
    with app.app_context():
        assert FeePayment.query.count() == 0
        assert db.session.get(FeeInvoice, invoice_id).paid == 200
        assert OnlineFeePayment.query.one().active_key is None
    assert send_event(client).status_code == 503


def test_malformed_merchant_key_is_reported_before_checkout(app, configured_gateway, student_checkout, monkeypatch):
    client, invoice_id, _ = student_checkout
    monkeypatch.setenv("SAFEPAY_PUBLIC_KEY", "wrong-key-kind")
    page = client.get(submit_checkout(client, invoice_id).location)
    assert b"requires the Public API Key" in page.data
    assert b"wrong-key-kind" not in page.data
    assert configured_gateway == []
    with app.app_context():
        assert OnlineFeePayment.query.count() == 0


@pytest.mark.parametrize("wrap_tracker", [False, True])
def test_sandbox_reporter_accepts_both_response_shapes(monkeypatch, wrap_tracker):
    import io
    from app import online_payments

    tracker = {"token": "track_test_fee", "environment": "sandbox", "state": "TRACKER_ENDED"}
    data = {"tracker": tracker} if wrap_tracker else tracker

    class Reporter:
        def open(self, request, timeout):
            assert request.full_url.endswith("/reporter/api/v1/payments/track_test_fee")
            return io.BytesIO(json.dumps({"data": data}).encode())

    monkeypatch.setattr(online_payments, "build_opener", lambda *args: Reporter())
    assert online_payments._sandbox_tracker("mock-secret", "track_test_fee") == tracker
