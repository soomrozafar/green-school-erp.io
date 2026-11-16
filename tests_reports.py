from datetime import date
from io import BytesIO

from openpyxl import load_workbook

from app.extensions import db
from app.models import FeeInvoice, Student
from app.report_catalogue import REPORTS
from tests_erp_ready import admin_client
from tests_login_security import add_user, app, login_data


def test_report_catalogue_and_exports(app):
    client = admin_client(app)
    assert b"Reports Center" in client.get("/reports/").data
    for key in REPORTS:
        path = f"/reports/{key}"
        assert client.get(path).status_code == 200, key
        assert client.get(path + "?format=csv").data.startswith(b"\xef\xbb\xbf"), key
        assert client.get(path + "?format=xlsx").data.startswith(b"PK"), key


def test_filtered_invoice_reporting_and_role_access(app):
    admin = admin_client(app)
    with app.app_context():
        student = Student(first_name="=1+1", admission_no="TEST-42")
        db.session.add_all([
            FeeInvoice(student=student, invoice_no="INV-TEST-A", fee_type="Monthly", amount=250, paid=50,
                       due_date=date(2026, 11, 1), status="Partial"),
            FeeInvoice(student=student, invoice_no="INV-TEST-B", fee_type="Monthly", amount=500, paid=0,
                       due_date=date(2026, 12, 1), status="Unpaid"),
        ])
        db.session.commit()
    path = "/reports/invoices?start=2026-11-01&end=2026-11-30"
    view = admin.get(path).data
    assert b"INV-TEST-A" in view and b"INV-TEST-B" not in view
    assert b"Outstanding" in view and b"200.00" in view
    export = admin.get(path + "&format=csv").data
    assert b"INV-TEST-A" in export and b"INV-TEST-B" not in export and b"'=1+1" in export
    workbook = load_workbook(BytesIO(admin.get(path + "&format=xlsx").data), read_only=True)
    assert ("Outstanding", 200) in list(workbook["Analysis"].values)
    assert list(workbook["Report"].values)[1][2] == "'=1+1"
    workbook.close()
    add_user(app, username="reports-teacher", role="teacher")
    teacher = app.test_client()
    teacher.post("/login", data=login_data(teacher, "reports-teacher"))
    assert teacher.get(path + "&format=csv").status_code == 403
    assert teacher.get("/reports/payroll?format=xlsx").status_code == 403
