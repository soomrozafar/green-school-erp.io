from tests_login_security import app, add_user, login_data
from app.extensions import db
from app.models import Book, InventoryItem, InventoryTransaction, LibraryIssue, Student, SystemSetting


def admin_client(app):
    add_user(app)
    client = app.test_client()
    assert client.post("/login", data=login_data(client)).status_code == 302
    return client


def test_admin_module_pages_and_website_retired(app):
    with app.app_context():
        for module in ("hostel", "mess", "inventory", "transport", "library"):
            key = f"module.{module}"
            setting = SystemSetting.query.filter_by(key=key).first()
            if setting:
                setting.value = "1"
            else:
                db.session.add(SystemSetting(key=key, value="1"))
        db.session.commit()
    client = admin_client(app)
    paths = (
        "/dashboard", "/students/", "/students/new", "/students/parents",
        "/students/admission-report", "/students/promotion", "/students/attendance",
        "/students/attendance/report", "/academics/teachers", "/academics/teacher-subjects",
        "/academics/exams", "/academics/results", "/academics/grades",
        "/finance/fees", "/finance/structures", "/finance/payment", "/finance/bulk-vouchers",
        "/finance/online-payments", "/accounts/", "/accounts/vouchers", "/accounts/collection",
        "/hr/employees", "/hr/payroll", "/hr/teacher-attendance", "/timetable/",
        "/timetable/import", "/reports/", "/notifications/", "/notifications/whatsapp",
        "/library/books", "/library/issue", "/operations/dashboard", "/transport",
        "/transport/assign", "/hostel", "/mess/", "/inventory", "/profile/password",
        "/assistant/overview", "/admin/users", "/admin/classes", "/admin/sessions",
        "/admin/subjects", "/admin/permissions", "/admin/modules", "/admin/banks",
        "/admin/data-edit", "/admin/system/health", "/admin/system/audit",
        "/admin/system/login-history", "/admin/system/integrity", "/admin/system/backups",
    )
    failures = [(path, response.status_code) for path in paths
                if (response := client.get(path, follow_redirects=True)).status_code != 200]
    assert not failures
    assert b"Green School" in client.get("/dashboard").data
    assert client.get("/static/assets/green-school-logo.png").status_code == 200
    for path in ("/admin/website", "/news/sample", "/academics/elementary", "/sitemap.xml"):
        assert client.get(path).status_code == 404, path
    assert app.test_client().get("/").location == "/login"


def test_operations_role_has_dashboard(app):
    add_user(app, role="operations_admin")
    client = app.test_client()
    client.post("/login", data=login_data(client))
    assert client.get("/dashboard", follow_redirects=True).status_code == 200


def test_oversized_login_rejected(app):
    client = app.test_client()
    data = login_data(client)
    assert client.post("/login", data={**data, "password": "x" * 17000}).status_code == 413


def test_retired_website_editor_cannot_login(app):
    add_user(app, role="website_editor")
    client = app.test_client()
    client.post("/login", data=login_data(client))
    assert client.get("/dashboard").status_code == 302


def test_library_and_stock_updates(app):
    from datetime import date, timedelta
    client = admin_client(app)
    with app.app_context():
        db.session.add_all([
            Student(admission_no="TEST-1", first_name="Test", status="Active"),
            Book(title="Test book", quantity=1, available=1),
            InventoryItem(item_code="TEST", name="Test stock", quantity=2),
        ])
        db.session.commit()
    def post(path, **data):
        with client.session_transaction() as session:
            token = session["csrf_token"]
        assert client.post(path, data={**data, "csrf_token": token}).status_code == 302

    post("/library/books", title="Second title", isbn="TEST-ISBN", quantity=2)
    post("/library/books", title="Duplicate title", isbn="TEST-ISBN", quantity=2)
    page = client.get("/library/books?q=TEST-ISBN&stock=available")
    assert b"Second title" in page.data and b"Duplicate title" not in page.data
    assert b"Test book" not in page.data
    for _ in range(2):
        post("/library/issue", book_id=1, student_id=1)
    with app.app_context():
        assert db.session.get(Book, 1).available == 0
        loan = LibraryIssue.query.one()
        assert loan.due_date == date.today() + timedelta(days=14)
        loan.due_date = date.today() - timedelta(days=1)
        db.session.commit()
    assert b"Test book" in client.get("/library/issue?status=overdue").data
    for _ in range(2):
        post("/library/return/1")
    post("/inventory/transaction", item_id=1, quantity=1, transaction_type="INVALID")
    post("/inventory/transaction", item_id=1, quantity=3, transaction_type="OUT")
    post("/inventory/transaction", item_id=1, quantity=2, transaction_type="OUT")
    with app.app_context():
        assert db.session.get(Book, 1).available == 1
        assert LibraryIssue.query.one().status == "Returned"
        assert InventoryItem.query.one().quantity == 0
        assert InventoryTransaction.query.count() == 1
