import re
from io import BytesIO

from app.extensions import db
from app.models import Employee, Notification, Parent, Student, Subject, Teacher, User, WhatsAppMessage
from tests_erp_ready import admin_client
from tests_login_security import PASSWORD, app, login_data


def post(client, path, **data):
    with client.session_transaction() as session:
        csrf = session["csrf_token"]
    return client.post(path, data={**data, "csrf_token": csrf})


def test_allocation_import_and_portal_communication(app):
    admin = admin_client(app)
    with app.app_context():
        parent = Parent(name="Demo Family", mobile="0300-1234567")
        db.session.add_all([
            Employee(name="Demo Import Teacher", employee_no="IMP-001", employee_type="Teacher"),
            Subject(code="SINDHI", name="Sindhi"),
            Student(admission_no="IMP-STUDENT", first_name="Demo Child", parent=parent),
        ])
        account = User(username="portal-family", role="parent", parent=parent)
        account.set_password(PASSWORD)
        db.session.add(account)
        db.session.commit()
        student_id = Student.query.one().id

    path = "/academics/teacher-allocation/import"
    preview = post(admin, path, action="preview", source_file=(BytesIO(b"Teacher,Subject\nIMP-001,SINDHI\n"), "subjects.csv"))
    assert b"Demo Import Teacher" in preview.data
    token = re.search(rb'name="draft" value="([^"]+)"', preview.data)[1].decode()
    with app.app_context():
        assert Teacher.query.count() == 0
    assert post(admin, path, action="save", draft=token).status_code == 303
    assert post(admin, path, action="save", draft=token).status_code == 303
    with app.app_context():
        assert [s.code for s in Teacher.query.one().subjects] == ["SINDHI"]

    assert post(admin, "/admin/communication/contact", whatsapp_number="+923001234567").status_code == 303
    for audience in ("Parents", "Teachers"):
        assert post(admin, "/notifications/", title=f"{audience} Notice", message="For your portal", audience=audience).status_code == 303
    family = app.test_client()
    assert family.post("/login", data=login_data(family, "portal-family")).status_code == 302
    page = family.get("/portal/").data
    assert b"Chat with AI Assistant" in page and b"https://wa.me/923001234567" in page
    assert b"Parents Notice" in page and b"Teachers Notice" not in page
    assert post(family, "/assistant", question="Child fees").json["actions"][0]["url"] == "/portal/"
    assert post(family, "/assistant", question="Contact administrator").json["actions"][0]["url"].startswith("https://wa.me/")
    assert family.get(path).status_code == 403
    assert family.get("/notifications/whatsapp").status_code == 403
    assert post(admin, "/notifications/whatsapp", student_ids=[student_id], message="School meeting").status_code == 303
    with app.app_context():
        assert WhatsAppMessage.query.one().status == "Prepared"
        notice = Notification.query.filter_by(audience="Parents").one()
        notice_id = notice.id
    assert post(admin, f"/notifications/{notice_id}/archive").status_code == 303
    assert b"Parents Notice" not in family.get("/portal/").data
