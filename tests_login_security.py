import re

import pytest

from app import create_app
from app.extensions import db
from app.models import FeeInvoice, LoginEvent, Student, User


PASSWORD = "Test password for ERP"


@pytest.fixture()
def app():
    return create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "fixture-secret-used-only-in-isolated-tests",
    })


def add_user(app, username="operator", role="admin", password=PASSWORD, active=True):
    with app.app_context():
        user = User(username=username, role=role, is_active_user=active)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()


def login_data(client, username="operator", password=PASSWORD):
    page = client.get("/login")
    token = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1)
    return {"username": username, "password": password, "csrf_token": token.decode()}


def test_login_rotates_csrf_and_requires_post_logout(app):
    add_user(app)
    client = app.test_client()
    data = login_data(client)
    response = client.post("/login", data=data)
    assert response.location == "/dashboard"
    assert "HttpOnly" in response.headers["Set-Cookie"]
    assert "SameSite=Lax" in response.headers["Set-Cookie"]
    assert client.get("/dashboard").status_code == 200
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 400
    assert client.post("/logout", data={"csrf_token": data["csrf_token"]}).status_code == 400
    token = login_data(client)["csrf_token"]
    assert client.post("/logout", data={"csrf_token": token}).location == "/login"
    assert client.get("/dashboard").status_code == 302


def test_login_checks_csrf_and_origin(app):
    add_user(app)
    client = app.test_client()
    data = login_data(client)
    assert client.post("/login", data={**data, "csrf_token": ""}).status_code == 400
    assert client.post("/login", data=data, headers={"Origin": "https://other.example"}).status_code == 400
    assert client.post("/login", data=data, headers={"Origin": "http://localhost"}).location == "/dashboard"


@pytest.mark.parametrize("change", ["disable", "password"])
def test_existing_session_revoked(app, change):
    add_user(app)
    client = app.test_client()
    assert client.post("/login", data=login_data(client)).status_code == 302
    with app.app_context():
        user = User.query.filter_by(username="operator").one()
        if change == "disable":
            user.is_active_user = False
        else:
            user.set_password("Another secret password")
        db.session.commit()
    assert client.get("/dashboard").status_code == 302


def test_inactive_and_legacy_admin_credentials_rejected(app):
    add_user(app, active=False)
    add_user(app, "admin", password="admin123")
    add_user(app, "admin_demo", password="Demo@12345")
    client = app.test_client()
    for username, password in [("operator", PASSWORD), ("admin", "admin123"), ("admin_demo", "Demo@12345"), ("missing", PASSWORD)]:
        response = client.post("/login", data=login_data(client, username, password))
        assert b"Invalid username or password." in response.data
    assert client.get("/dashboard").status_code == 302


def test_account_throttle_and_audit(app):
    add_user(app)
    client = app.test_client()
    data = login_data(client, password="incorrect")
    for _ in range(5):
        assert client.post("/login", data=data).status_code == 200
    assert client.post("/login", data={**data, "password": PASSWORD}).status_code == 429
    with app.app_context():
        assert LoginEvent.query.filter_by(username="operator", event="failed_login").count() == 5


def test_source_throttle(app):
    with app.app_context():
        db.session.add_all(
            LoginEvent(username=f"attempt-{i}", event="failed_login", ip_address="127.0.0.1")
            for i in range(30)
        )
        db.session.commit()
    client = app.test_client()
    assert client.post("/login", data=login_data(client, "another-account")).status_code == 429


def test_admin_password_command(app):
    with app.app_context():
        assert User.query.filter_by(username="admin").first() is None
    runner = app.test_cli_runner()
    assert runner.invoke(args=["set-admin-password"], input=f"{PASSWORD}\n{PASSWORD}\n").exit_code == 0
    client = app.test_client()
    assert client.post("/login", data=login_data(client, "admin")).location == "/dashboard"


def test_student_portal_and_admin_authorization(app):
    add_user(app, role="student")
    client = app.test_client()
    assert client.post("/login", data=login_data(client)).location == "/portal/"
    assert client.get("/admin/permissions").status_code == 403
    assert client.get("/portal/").location == "/login"
    assert client.get("/dashboard").status_code == 302


def test_single_and_bulk_voucher_pdf(app):
    add_user(app)
    with app.app_context():
        student = Student(admission_no="QA-01", first_name="Test Student")
        invoice = FeeInvoice(invoice_no="QA-01", student=student, fee_type="Tuition", amount=500)
        db.session.add(invoice)
        db.session.commit()
        invoice_id = invoice.id
    client = app.test_client()
    assert client.post("/login", data=login_data(client)).location == "/dashboard"
    for path in (f"/exports/voucher/{invoice_id}.pdf", f"/exports/bulk-vouchers.pdf?invoice_ids={invoice_id}"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.data.startswith(b"%PDF")

def test_teacher_campus_login_records_once(app, monkeypatch):
    from app.models import Employee, Teacher, TeacherAttendance

    for key, value in {"LAT": "24.9", "LON": "67.1", "RADIUS_M": "100"}.items():
        monkeypatch.setenv("SCHOOL_ERP_CAMPUS_" + key, value)
    add_user(app, username="campus-teacher", role="teacher")
    with app.app_context():
        teacher = Teacher(employee=Employee(name="Campus Teacher", employee_no="campus-teacher"))
        db.session.add(teacher)
        db.session.commit()
    for location, status in (
        ({}, 403),
        (dict(latitude="25.0", longitude="67.1", accuracy="10"), 403),
        (dict(latitude="24.9", longitude="67.1", accuracy="150"), 403),
        (dict(latitude="24.9", longitude="67.1", accuracy="10"), 302),
        (dict(latitude="24.9", longitude="67.1", accuracy="10"), 302),
    ):
        client = app.test_client()
        assert client.post("/login", data={**login_data(client, "campus-teacher"), **location}).status_code == status
    with app.app_context():
        assert TeacherAttendance.query.one().status == "Present"
