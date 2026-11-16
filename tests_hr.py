from app.extensions import db
from app.models import Employee, Payroll, StaffLeave
from tests_login_security import app, add_user, login_data


def test_school_hr_workflow(app):
    with app.app_context():
        employee = Employee(name="School HR Test", employee_no="HR-001", basic_salary=1000)
        db.session.add(employee)
        db.session.commit()
        employee_id = employee.id

    def sign_in(role):
        add_user(app, username=role, role=role)
        client = app.test_client()
        assert client.post("/login", data=login_data(client, role)).status_code == 302
        return client

    def post(client, path, **values):
        with client.session_transaction() as session:
            token = session["csrf_token"]
        return client.post(path, data={**values, "csrf_token": token})

    hr, reviewer, accounts = map(sign_in, ("hr_officer", "principal", "accountant"))
    request = dict(employee_id=employee_id, leave_type="Unpaid", start_date="2026-11-12", end_date="2026-11-13")
    assert post(hr, "/hr/leave", **request).status_code == 303
    assert post(hr, "/hr/leave", **request).status_code == 303
    with app.app_context():
        entry = StaffLeave.query.one()
        leave_id = entry.id
        assert entry.status == "Pending"
    review_url = f"/hr/leave/{leave_id}/review"
    assert post(hr, review_url, decision="Approved").status_code == 403
    assert post(reviewer, review_url, decision="Approved").status_code == 303
    assert b"Unpaid" in accounts.get(f"/hr/payroll?employee_id={employee_id}&month=2026-11").data
    fields = dict(employee_id=employee_id, month="2026-11", bonus="125.25",
                  other_deductions="30.10", status="Paid")
    assert post(accounts, "/hr/payroll", **fields).status_code == 303
    assert post(accounts, "/hr/payroll", **{**fields, "bonus": 0}).status_code == 303
    assert post(accounts, "/hr/payroll", **{**fields, "month": "2026-12", "bonus": "-1"}).status_code == 303
    with app.app_context():
        payroll = Payroll.query.one()
        assert payroll.net_salary == 1095.15
        assert payroll.paid_at is not None
        slip = f"/hr/payroll/{payroll.id}/payslip"
    assert b"1095.15" in accounts.get(slip).data
    assert hr.get(slip).status_code == 403
