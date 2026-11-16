from datetime import date

from app.extensions import db
from app.models import Employee, HostelRoom, InventoryItem, MessMenu, Student, Subject, Teacher, Timetable
from tests_academic_workflows import seed
from tests_erp_ready import admin_client
from tests_login_security import app


def post(client, path, **values):
    with client.session_transaction() as session:
        token = session["csrf_token"]
    return client.post(path, data={**values, "csrf_token": token}, follow_redirects=True)


def test_record_edits_transfer_and_search(app):
    teacher_id, student_id = seed(app)
    client = admin_client(app)
    with app.app_context():
        from app.models import User, SystemSetting
        for key in ("hostel", "mess"):
            SystemSetting.query.filter_by(key=f"module.{key}").one().value = "1"
        student = db.session.get(Student, student_id)
        student.first_name = "Ayesha"
        original = db.session.get(Teacher, teacher_id)
        subject = Subject.query.one()
        original.subjects.append(subject)
        replacement = Teacher(employee=Employee(employee_no="ERP-002", name="Replacement Teacher", employee_type="Teacher"))
        staff_id = User.query.one().id
        room = HostelRoom(block="A", room_no="1", capacity=4)
        item = InventoryItem(item_code="STK-001", name="Chairs", quantity=10, reorder_level=2, unit="pcs")
        meal = MessMenu(menu_date=date.today(), meal_type="Lunch", menu="Rice", estimated_cost=100, created_by=staff_id)
        db.session.add_all([replacement, room, item, meal,
                            Timetable(class_id=student.class_id, teacher_id=teacher_id, subject_id=subject.id,
                                      day="Monday", start_time="08:00", end_time="09:00")])
        db.session.commit()
        replacement_id, subject_id = replacement.id, subject.id
        room_id, item_id, meal_id = room.id, item.id, meal.id

    assert client.get("/search?q=A").json["students"][0]["name"] == "Ayesha"
    assert b'data-live-search="directory"' in client.get("/students/").data
    assert client.get("/students/?q=A&suggest=1").json["students"][0]["name"] == "Ayesha"
    assert client.get("/students/?q=Ay&status=Active&suggest=1").json["students"][0]["name"] == "Ayesha"
    assert client.get("/students/?q=Ay&status=Inactive&suggest=1").json["students"] == []
    assert client.get("/students/?q=%25&suggest=1").json["students"] == []
    assert client.get("/search?q=Ay").json["students"][0]["name"] == "Ayesha"
    assert not client.get("/search?q=%25").json["students"]
    records = client.get("/search?q=Ch&scope=workspace").json["records"]
    assert any(row["url"] == f"/inventory/records/{item_id}" for row in records)
    teacher_url = f"/academics/teachers/{teacher_id}"
    assert b"Transfer Subject" in client.get(teacher_url + "?edit=1").data
    assert b"Transfer scheduled subjects" in post(client, teacher_url, action="save", status="Inactive").data
    assert b"updated" in post(client, teacher_url, action="transfer", subject_id=subject_id,
                              replacement_id=replacement_id).data
    assert b"Inactive" in post(client, teacher_url, action="save", status="Inactive").data
    for module, record_id, fields, expected in (
        ("hostel", room_id, dict(block="A", room_no="101", capacity=5, gender=""), b"101"),
        ("inventory", item_id, dict(item_code="STK-001", name="Classroom Chairs", category="Furniture",
                                    unit="pcs", location="Stockroom", reorder_level=3, quantity=999), b"Classroom Chairs"),
        ("mess", meal_id, dict(menu_date=date.today(), meal_type="Lunch", menu="Rice and salad",
                               estimated_cost=125), b"Rice and salad"),
    ):
        path = f"/{module}/records/{record_id}"
        assert b"Save Changes" in client.get(path + "?edit=1").data
        assert expected in post(client, path, **fields).data
    with app.app_context():
        original = db.session.get(Teacher, teacher_id)
        assert original.status == "Inactive" and not original.subjects
        assert Timetable.query.one().teacher_id == replacement_id
        assert db.session.get(InventoryItem, item_id).quantity == 10
