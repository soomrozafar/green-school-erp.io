from datetime import date
from io import BytesIO
import re
from zipfile import ZipFile

from app.extensions import db
from app.models import Attendance, ClassRoom, Employee, Student, Subject, Teacher, TeacherAttendance, Timetable
from tests_login_security import app, login_data
from tests_workspace import ask, sign_in


def seed(app):
    with app.app_context():
        teacher = Teacher(employee=Employee(name="Test Maths Teacher", employee_no="ERP-001", employee_type="Teacher"))
        student = Student(first_name="Test Student", admission_no="ERP-STU", class_room=ClassRoom(name="Class II", section="A"))
        subject = Subject(name="Math", code="MATH")
        db.session.add_all([teacher, student, subject])
        db.session.commit()
        return teacher.id, student.id


def test_import_reviews_and_saves_allocations(app):
    teacher_id, _ = seed(app)
    client = sign_in(app, "admin")
    assert ask(client, "Import timetable").get_json()["actions"][0]["url"] == "/timetable/import"
    csrf = login_data(client)["csrf_token"]
    data = "Day,Class,Subject,Teacher,Start,End,Room\nMonday,Class II - A,MATH,ERP-001,8:30 AM,09:15,Room 2"
    preview = client.post("/timetable/import", data={"csrf_token": csrf, "timetable_text": data})
    assert b"Draft preview" in preview.data
    with app.app_context():
        assert Timetable.query.count() == 0
    token = re.search(rb'name="draft" value="([^"]+)"', preview.data)[1].decode()
    assert client.post("/timetable/import", data={"csrf_token": csrf, "action": "save",
                                                   "draft": token, "allocate": "1"}).status_code == 303
    assert b"Test Maths Teacher" in client.get("/timetable/").data
    with app.app_context():
        assert Timetable.query.one().start_time == "08:30"
        assert db.session.get(Teacher, teacher_id).subjects[0].name == "Math"
    clash = client.post("/timetable/import", data={"csrf_token": csrf, "timetable_text": data.replace("09:15", "09:30")})
    assert b"Overlapping class assignment" in clash.data
    assert b"Save reviewed timetable" not in clash.data


def test_word_upload_and_role_scope(app):
    seed(app)
    client = sign_in(app, "admin")
    document = BytesIO()
    with ZipFile(document, "w") as zipped:
        zipped.writestr("word/document.xml", """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Tuesday,Class II - A,Math,ERP-001,08:30,09:15,Room 2</w:t></w:r></w:p></w:body></w:document>""")
    document.seek(0)
    response = client.post("/timetable/import", data={"csrf_token": login_data(client)["csrf_token"],
                                                       "source_file": (document, "schedule.docx")})
    assert b"Draft preview" in response.data
    with app.app_context():
        assert Timetable.query.count() == 0

    teacher = app.test_client()
    from tests_login_security import add_user
    add_user(app, username="teacher-schedule", role="teacher")
    assert teacher.post("/login", data=login_data(teacher, "teacher-schedule")).status_code == 302
    assert teacher.get("/timetable/import").status_code == 403
    assert teacher.get("/hr/teacher-attendance").status_code == 403


def test_teacher_and_student_attendance_keep_unmarked_separate(app):
    teacher_id, student_id = seed(app)
    client = sign_in(app, "admin")
    assert ask(client, "Teacher attendance today").get_json()["actions"][0]["url"] == "/hr/teacher-attendance"
    day = date.today().isoformat()
    csrf = login_data(client)["csrf_token"]
    assert client.post("/hr/teacher-attendance", data={"csrf_token": csrf, "date": day,
                                                       f"teacher_{teacher_id}": "Late"}).status_code == 303
    assert client.post("/hr/teacher-attendance", data={"csrf_token": csrf, "date": day,
                                                       f"teacher_{teacher_id}": "Present"}).status_code == 303
    assert client.post("/students/attendance", data={"csrf_token": csrf, "action": "save",
                                                     "date": day, f"student_{student_id}": ""}).status_code == 200
    with app.app_context():
        assert TeacherAttendance.query.one().status == "Present"
        assert Attendance.query.count() == 0

def test_teacher_marks_and_approval_release(app):
    from app.models import Exam, Result, User
    from tests_login_security import PASSWORD

    teacher_id, student_id = seed(app)
    with app.app_context():
        student = db.session.get(Student, student_id)
        subject = Subject.query.filter_by(code="MATH").one()
        exam = Exam(name="Final Mathematics", term="Final Term", class_id=student.class_id)
        outsider = Student(first_name="Unassigned Student", admission_no="ERP-OUT",
                           class_room=ClassRoom(name="Class III", section="A"))
        db.session.add_all([exam, outsider, Timetable(day="Monday", start_time="08:00", end_time="09:00",
                           teacher_id=teacher_id, class_id=student.class_id, subject_id=subject.id)])
        for username, role, link in [
            ("linked-teacher", "teacher", {"teacher_id": teacher_id}),
            ("linked-student", "student", {"student_id": student_id}),
            ("exam-reviewer", "vice_principal", {}),
        ]:
            account = User(username=username, role=role, **link)
            account.set_password(PASSWORD)
            db.session.add(account)
        db.session.commit()
        exam_id, subject_id, class_id, outsider_id, outside_class = exam.id, subject.id, student.class_id, outsider.id, outsider.class_id

    def login(username):
        client = app.test_client()
        assert client.post("/login", data=login_data(client, username)).status_code == 302
        return client

    def post(client, path, **fields):
        with client.session_transaction() as session:
            token = session["csrf_token"]
        return client.post(path, data={"csrf_token": token, **fields})

    teacher, student, reviewer = map(login, ("linked-teacher", "linked-student", "exam-reviewer"))
    assert teacher.get(f"/students/attendance?class_id={outside_class}").status_code == 403
    assert post(teacher, "/students/attendance", action="save", class_id=class_id,
                date=date.today().isoformat(), **{f"student_{student_id}": "Present"}).status_code == 200
    marks = dict(exam_id=exam_id, student_id=student_id, subject_id=subject_id, marks=84, total=100)
    assert post(teacher, "/academics/results", **{**marks, "student_id": outsider_id}).status_code == 404
    assert post(teacher, "/academics/results", **{**marks, "subject_id": 9999}).status_code == 403
    assert post(teacher, "/academics/results", **marks).status_code == 303
    approval = f"/academics/exams/{exam_id}/approve"
    card = f"/academics/report-card/{student_id}/{exam_id}"
    pdf = f"/exports/report-card/{student_id}/{exam_id}.pdf"
    assert b"Final Mathematics" not in student.get("/portal/").data
    assert student.get(card).status_code == student.get(pdf).status_code == 403
    assert post(teacher, approval).status_code == 403
    assert b"Approve &amp; Publish" in reviewer.get(f"/academics/results?exam_id={exam_id}").data
    assert post(reviewer, approval).status_code == 303
    assert b"Final Result" in student.get("/portal/").data
    assert student.get(card).status_code == 200
    assert student.get(pdf).data.startswith(b"%PDF")
    assert post(teacher, "/academics/results", **{**marks, "marks": 99}).status_code == 409
    with app.app_context():
        assert Attendance.query.one().status == "Present"
        assert Result.query.one().marks == 84
        assert db.session.get(Exam, exam_id).approved_by.username == "exam-reviewer"
