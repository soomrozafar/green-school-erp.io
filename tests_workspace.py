from datetime import date

import pytest

from app.extensions import db
from app.models import Attendance, Employee, FeeInvoice, Student
from tests_login_security import add_user, app, login_data


def sign_in(app, role):
    add_user(app, role=role)
    client = app.test_client()
    assert client.post("/login", data=login_data(client)).status_code == 302
    return client


def seed_records(app):
    with app.app_context():
        student = Student(admission_no="QA-STU", first_name="QA Student")
        db.session.add_all([
            student,
            Attendance(student=student, date=date.today(), status="Present"),
            FeeInvoice(invoice_no="QA-INV", student=student, fee_type="Tuition", amount=2500),
            FeeInvoice(invoice_no="OTHER-INV", student=student, fee_type="Tuition", amount=1700),
            Employee(employee_no="QA-EMP", name="QA Employee"),
            Employee(employee_no="OTHER-EMP", name="Other Employee"),
        ])
        db.session.commit()


def ask(client, question):
    token = login_data(client)["csrf_token"]
    return client.post("/assistant", data={"question": question, "csrf_token": token})


def test_dashboard_and_assistant_use_live_data(app, monkeypatch):
    monkeypatch.delenv("SCHOOL_ERP_OLLAMA_MODEL", raising=False)
    seed_records(app)
    client = sign_in(app, "admin")
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert b"School dashboard" in dashboard.data
    assert b"PKR 4,200" in dashboard.data
    assert b'aria-current="page"' in dashboard.data
    assert b'id="erpAssistant"' in dashboard.data
    assert b"<span>AI Assistant</span>" in dashboard.data

    fees = ask(client, "Kitni baqaya fees hain?").get_json()
    assert "PKR 4,200.00" in fees["message"]
    assert fees["actions"][0]["url"] == "/finance/fees"
    assert fees["source"] == "builtin"
    assert b"Built-in mode" in dashboard.data
    attendance = ask(client, "Aaj ki hazri").get_json()
    assert "1 of 1" in attendance["message"]
    assert ask(client, "x" * 281).status_code == 400
    assert client.post("/assistant", data={"question": "fees"}).status_code == 400


def test_search_results_open_filtered_records(app):
    seed_records(app)
    client = sign_in(app, "admin")
    data = client.get("/search?q=QA").get_json()
    assert data["students"][0]["admission_no"] == "QA-STU"
    assert data["employees"][0]["employee_no"] == "QA-EMP"
    assert data["invoices"][0]["invoice_no"] == "QA-INV"
    for route, match, excluded in (
        ("/finance/fees?q=QA-INV", b"QA-INV", b"OTHER-INV"),
        ("/hr/employees?q=QA-EMP", b"QA-EMP", b"OTHER-EMP"),
    ):
        response = client.get(route)
        assert response.status_code == 200
        assert match in response.data
        assert excluded not in response.data


@pytest.mark.parametrize("role", ["teacher", "student"])
def test_assistant_keeps_finance_private(app, role, monkeypatch):
    seed_records(app)
    client = sign_in(app, role)

    def unexpected_model_call(*args):
        pytest.fail("Recognized requests should never call the model.")

    monkeypatch.setattr("app.assistant.classify_locally", unexpected_model_call)
    assistant = ask(client, "Outstanding fees")
    assert assistant.status_code == 200
    assert all(not item["url"].startswith("/finance") for item in assistant.get_json()["actions"])
    assert b"4,200" not in assistant.data

    if role == "teacher":
        assert client.get("/search?q=QA").get_json()["invoices"] == []
        assert b"Fee collections" not in client.get("/dashboard").data


def test_optional_local_model_can_only_select_allowed_action(app, monkeypatch):
    import json

    from app import assistant

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, limit):
            return json.dumps({"message": {"content": json.dumps({"action": self.action})}}).encode()

    response = Response()

    class Opener:
        def open(self, request, timeout):
            assert request.full_url == "http://127.0.0.1:11434/api/chat"
            assert timeout == 20
            keys = json.loads(request.data)["format"]["properties"]["action"]["enum"]
            assert "attendance" in keys
            assert "balance" not in keys
            return response

    monkeypatch.setenv("SCHOOL_ERP_OLLAMA_MODEL", "test-model")
    monkeypatch.setattr(assistant, "build_opener", lambda *handlers: Opener())
    client = sign_in(app, "teacher")
    response.action = "attendance"
    result = ask(client, "Aaj class ka kaam").get_json()
    assert result["actions"][0]["url"] == "/students/attendance"
    assert result["source"] == "ollama"
    assert b"Ollama configured" in client.get("/dashboard").data
    response.action = "balance"
    assert all(not item["url"].startswith("/finance") for item in ask(client, "Unrecognized text").get_json()["actions"])

def test_assistant_workflow_alerts_and_audience(app):
    from datetime import timedelta
    from app.models import Exam, Notification

    seed_records(app)
    with app.app_context():
        invoice = FeeInvoice.query.filter_by(invoice_no="QA-INV").one()
        invoice.paid = 500
        invoice.due_date = date.today() - timedelta(days=1)
        db.session.add_all([
            Exam(name="Finished exam", end_date=date.today() - timedelta(days=1)),
            Exam(name="Future exam", end_date=date.today() + timedelta(days=1)),
            Notification(title="All notice", message="Visible to everyone", audience="All"),
            Notification(title="Teacher notice", message="Teachers only", audience="Teachers"),
            Notification(title="Inactive", message="Hidden", audience="All", is_active=False),
        ])
        db.session.commit()
    client = sign_in(app, "admin")
    overview = client.get("/assistant/overview").get_json()
    summaries = {card["title"]: card for card in overview["cards"]}
    assert "missing a class or guardian" in summaries["Admissions"]["summary"]
    assert "PKR 2,000.00" in summaries["Fees"]["summary"]
    assert "1 finished exams" in summaries["Grades"]["summary"]
    assert [notice["title"] for notice in overview["notices"]] == ["All notice"]
    fees = client.get(summaries["Fees"]["action"]["url"])
    assert fees.status_code == 200 and b"QA-INV" in fees.data and b"OTHER-INV" not in fees.data
    assert client.get(summaries["Admissions"]["action"]["url"]).status_code == 200
    assert ask(client, "Grades pending").get_json()["actions"][0]["url"] == "/academics/results"


def test_teacher_does_not_receive_finance_or_admissions_alerts(app):
    client = sign_in(app, "teacher")
    assert [card["title"] for card in client.get("/assistant/overview").get_json()["cards"]] == ["Grades"]
    assert app.test_client().get("/assistant/overview").status_code == 302

def test_module_banner_renders_for_each_work_area(app):
    from html import unescape
    from pathlib import Path
    import re
    from app.module_banners import BANNERS, module_banner

    assets = set()
    for endpoint, (title, _) in BANNERS.items():
        actual_title, asset, today = module_banner(endpoint, "admin")
        assert actual_title == title
        assert today == date.today()
        assert asset not in assets
        assert (Path(app.static_folder) / asset).is_file()
        assets.add(asset)
    admission_banner = module_banner("main.dashboard", "admission_officer")[1]
    assert admission_banner not in assets and (Path(app.static_folder) / admission_banner).is_file()

    client = sign_in(app, "admin")
    for route, title, asset in [
        ("/dashboard", b"School dashboard", b"erp-library.webp"),
        ("/students/new", b"New Student Admission", b"banners/admissions.webp"),
        ("/finance/fees", b"Fee Management", b"banners/fees.webp"),
        ("/academics/results", b"Results", b"banners/results.webp"),
        ("/transport", b"Transport &amp; Routes", b"banners/transport.webp"),
        ("/library/books", b"Library Catalogue", b"banners/library.webp"),
        ("/hr/payroll", b"Payroll", b"banners/payroll.webp"),
    ]:
        response = client.get(route)
        assert response.status_code == 200, route
        assert response.data.count(b"workspace-module-hero") == 1, route
        markup = response.get_data(as_text=True)
        heading = re.search(r"<h1>(.*?)</h1>", markup).group(1)
        assert unescape(title.decode()) in unescape(heading) and asset in response.data, route
        assert b'class="erp-hero' not in response.data, route

def test_banner_replaces_repeated_module_title(app):
    client = sign_in(app, "admin")
    for route, banner_title, duplicate, content in [
        ("/students/parents", b"Parents &amp; Guardians", b"Parents / Guardians</h2>", b"Add Guardian"),
        ("/academics/exams", b"Exams", b"Exams</h3>", b"Exam name"),
        ("/academics/grades", b"Grade Scale", b"Grade Scale</h3>", b"Min %"),
        ("/profile/password", b"Change Password", b"Change Password</h4>", b"Current Password"),
    ]:
        response = client.get(route)
        assert response.status_code == 200
        assert b"<h1>" + banner_title + b"</h1>" in response.data
        assert duplicate not in response.data
        assert content in response.data

def test_generate_sixty_challans_and_reopen_batch(app):
    import re
    from datetime import timedelta
    from app.models import FeeStructure, VoucherBatch

    client = sign_in(app, "admin")
    with app.app_context():
        students = [Student(first_name=f"Batch Student {i:02}", admission_no=f"BULK-{i:02}",
                            phone="0312-5550199" if i == 0 else None) for i in range(60)]
        fee = FeeStructure(name="Batch tuition", amount=1000)
        db.session.add_all([*students, fee])
        db.session.commit()
        ids = [str(student.id) for student in students]
        fee_id = str(fee.id)
    form = {"student_ids": ids, "fee_structure_ids": fee_id, "fee_months": date.today().strftime("%Y-%m"),
            "csrf_token": login_data(client)["csrf_token"]}
    result = client.post("/finance/bulk-vouchers", data=form)
    assert result.status_code == 303
    page = client.get(result.location)
    assert page.status_code == 200
    assert b"60 challans for 60 students" in page.data
    assert b"59 students need a valid" in page.data
    assert b"https://wa.me/923125550199" in page.data
    assert page.data.count(b"Student PDF") == 60
    combined = client.get(result.location + "/pdf")
    assert combined.status_code == 200
    assert len(re.findall(rb"/Type /Page\b", combined.data)) == 60
    single = client.get(result.location + f"/students/{ids[0]}/pdf")
    assert single.status_code == 200
    assert len(re.findall(rb"/Type /Page\b", single.data)) == 1
    assert client.get(result.location + "/students/9999/pdf").status_code == 404

    retry = client.post("/finance/bulk-vouchers", data=form)
    assert retry.status_code == 303
    with app.app_context():
        assert FeeInvoice.query.count() == 60
        assert VoucherBatch.query.order_by(VoucherBatch.id.desc()).first().created_count == 0


def test_voucher_pdf_continues_large_invoice(app):
    import re
    from app.models import FeeInvoiceItem

    client = sign_in(app, "admin")
    with app.app_context():
        student = Student(admission_no="LARGE-01", first_name="Long Voucher")
        invoice = FeeInvoice(student=student, invoice_no="LONG-01", fee_type="Multi-month", amount=108,
                             items=[FeeInvoiceItem(description=f"Combined billing line {i}", amount=1)
                                    for i in range(108)])
        db.session.add(invoice)
        db.session.commit()
        invoice_id = invoice.id
    response = client.get(f"/exports/voucher/{invoice_id}.pdf")
    assert response.status_code == 200
    assert len(re.findall(rb"/Type /Page\b", response.data)) > 1


def test_admin_can_copy_diagnostics_request(app):
    client = sign_in(app, "admin")
    seed_records(app)
    with app.app_context():
        invoice = FeeInvoice.query.first()
        invoice.paid = invoice.amount + 1
        db.session.commit()
    response = client.get("/admin/system/integrity")
    assert response.status_code == 200
    assert b"Copy request" in response.data
    assert b"Overpaid invoices. Reconcile" in response.data
    reply = ask(client, "system health").get_json()
    assert "1 data integrity checks" in reply["message"]
