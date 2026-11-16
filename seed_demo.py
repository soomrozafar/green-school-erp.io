"""Public School Gadap ERP - Demo/Dummy Data Seeder.

Safe-by-default: does not delete existing records. Run once on a test database.
Usage: python seed_demo.py
"""
from datetime import date, datetime, timedelta
from getpass import getpass
from app import create_app
from app.extensions import db
from app.models import (
    User, AcademicSession, ClassRoom, Subject, Parent, Student, Employee, Teacher,
    Attendance, Exam, Result, FeeStructure, FeeInvoice, FeeInvoiceItem, FeePayment,
    Book, LibraryIssue, Timetable, Notification, LoginEvent, AuditLog,
    StudentPromotionHistory, StudentStatusHistory, Payroll, GradeScale,
    Vehicle, TransportRoute, TransportAssignment, HostelRoom, HostelAllocation,
    InventoryItem, InventoryTransaction, MessMenu, Permission, SystemSetting,
    BankAccount, WhatsAppMessage
)

TODAY = date.today()


def user(username, password, role, student=None):
    u = User.query.filter_by(username=username).first()
    if u:
        return u
    u = User(username=username, role=role, student=student)
    u.set_password(password)
    db.session.add(u)
    db.session.flush()
    return u


def link_demo_accounts(password):
    student = Student.query.filter_by(admission_no="PSG-DEMO-0001").one()
    employee = Employee.query.filter_by(employee_no="EMP-DEMO-001").one()
    if not student.parent_id or not employee.teacher:
        raise RuntimeError("Demo parent or teacher record is missing.")
    for username, role, field, record_id in (
        ("teacher_demo", "teacher", "teacher_id", employee.teacher.id),
        ("student_demo", "student", "student_id", student.id),
        ("parent_demo", "parent", "parent_id", student.parent_id),
    ):
        account = user(username, password, role)
        if account.role != role or getattr(account, field) not in (None, record_id):
            raise RuntimeError(f"Demo username {username} is assigned to another role or record.")
        setattr(account, field, record_id)
        account.set_password(password)
        account.is_active_user = True


def main():
    app = create_app()
    with app.app_context():
        marker = SystemSetting.query.filter_by(key="demo.seed.v1").first()
        password = getpass("Choose a demo account password (at least 12 characters): ")
        if len(password) < 12:
            raise SystemExit("Use a password of at least 12 characters.")

        if marker:
            link_demo_accounts(password)
            db.session.commit()
            print("Demo logins refreshed: teacher_demo, student_demo, parent_demo.")
            return

        # Enable all optional modules for a complete demo environment.
        for key in ["hostel", "mess", "transport", "inventory", "library", "whatsapp", "bank_integration"]:
            row = SystemSetting.query.filter_by(key=f"module.{key}").first()
            if row:
                row.value = "1"
            else:
                db.session.add(SystemSetting(key=f"module.{key}", value="1"))

        # Users / role demo accounts
        admin = user("admin_demo", password, "admin")
        accountant = user("accountant_demo", password, "accountant")
        admission = user("admission_demo", password, "admission_officer")
        staff = user("staff_demo", password, "staff")
        teacher_user = user("teacher_demo", password, "teacher")

        session = AcademicSession.query.filter_by(name="2026-27 Demo Session").first()
        if not session:
            session = AcademicSession(name="2026-27 Demo Session", start_date=date(2026, 4, 1), end_date=date(2027, 3, 31), is_active=True)
            db.session.add(session); db.session.flush()

        # Classes / sections
        classes = {}
        for name, section in [("Class I", "A"), ("Class II", "A"), ("Class III", "A"), ("Class IV", "A"), ("Class V", "A"), ("Class VI", "A"), ("Class VII", "A"), ("Class VIII", "A")]:
            c = ClassRoom.query.filter_by(name=name, section=section, session_id=session.id).first()
            if not c:
                c = ClassRoom(name=name, section=section, capacity=35, session=session)
                db.session.add(c); db.session.flush()
            classes[name] = c

        # Subjects
        subject_defs = [
            ("ENG", "English"), ("URD", "Urdu"), ("MAT", "Mathematics"),
            ("SCI", "General Science"), ("SST", "Social Studies"),
            ("ISL", "Islamiat"), ("COM", "Computer Science"), ("PE", "Physical Education")
        ]
        subjects = {}
        for code, name in subject_defs:
            s = Subject.query.filter_by(code=code).first()
            if not s:
                s = Subject(code=code, name=name, max_marks=100)
                db.session.add(s); db.session.flush()
            subjects[code] = s

        # Employees: teachers + non-teaching staff
        employee_defs = [
            ("Demo Teacher 01", "Teacher", "Academics", "Senior Teacher", "M", "1988-02-10", "Muhammad Iqbal", "42101-1111111-1", "0300-1111111", "teacher01@psgdemo.edu.pk", "M.Ed", 8, 65000),
            ("Demo Teacher 02", "Teacher", "Academics", "Teacher", "F", "1991-06-18", "Shazia Ahmed", "42101-2222222-2", "0301-2222222", "teacher02@psgdemo.edu.pk", "B.Ed", 6, 58000),
            ("Demo Teacher 03", "Teacher", "Academics", "Teacher", "M", "1986-11-25", "Abdul Latif", "42101-3333333-3", "0302-3333333", "teacher03@psgdemo.edu.pk", "M.A", 10, 72000),
            ("Demo Accountant", "Non-Teacher", "Accounts", "Accountant", "M", "1985-03-14", "Ghulam Mustafa", "42101-4444444-4", "0303-4444444", "accounts@psgdemo.edu.pk", "M.Com", 9, 70000),
            ("Demo HR Officer", "Non-Teacher", "HR", "HR Officer", "F", "1990-09-09", "Nusrat Bibi", "42101-5555555-5", "0304-5555555", "hr@psgdemo.edu.pk", "MBA", 7, 62000),
            ("Demo Librarian", "Non-Teacher", "Library", "Librarian", "F", "1987-12-02", "Rashida Khan", "42101-6666666-6", "0305-6666666", "library@psgdemo.edu.pk", "MLIS", 8, 55000),
            ("Demo Driver", "Non-Teacher", "Transport", "Driver", "M", "1979-07-21", "Allah Dino", "42101-7777777-7", "0306-7777777", "driver@psgdemo.edu.pk", "Matric", 12, 45000),
        ]
        employees = []
        for idx, d in enumerate(employee_defs, 1):
            name, etype, dept, desig, gender, dob, father, cnic, phone, email, qual, exp, salary = d
            e = Employee.query.filter_by(email=email).first()
            if not e:
                e = Employee(employee_no=f"EMP-DEMO-{idx:03d}", name=name, employee_type=etype, department=dept,
                             designation=desig, gender=gender, dob=date.fromisoformat(dob), father_name=father,
                             cnic=cnic, phone=phone, email=email, address="Public School Gadap Demo Campus, Karachi",
                             qualification=qual, experience_years=exp, joining_date=date(2023, 4, 1),
                             basic_salary=salary, bank_name="Demo Bank", bank_account=f"00123456{idx:02d}",
                             iban=f"PK00DEMO000000000000{idx:04d}", emergency_contact_name="Demo Emergency Contact",
                             emergency_contact_phone=f"031{idx:07d}", status="Active")
                db.session.add(e); db.session.flush()
            employees.append(e)

        teacher_emps = [e for e in employees if e.employee_type == "Teacher"]
        teacher_objs = []
        for e, codes in zip(teacher_emps, [["ENG", "URD"], ["MAT", "SCI"], ["SST", "ISL", "COM"]]):
            t = Teacher.query.filter_by(employee_id=e.id).first()
            if not t:
                # Existing/legacy SQLite databases may still have teacher.employee_no
                # as NOT NULL even though the current ORM uses Employee as the source
                # of truth. Insert the compatibility column when that legacy column
                # exists, then load the ORM object normally.
                teacher_columns = {c[1] for c in db.session.execute(db.text("PRAGMA table_info(teacher)"))}
                if "employee_no" in teacher_columns:
                    # Populate every legacy NOT NULL teacher column that may still
                    # exist in an older SQLite database. The current ORM intentionally
                    # uses Employee as the single source of truth, but old physical
                    # columns can remain NOT NULL after schema upgrades.
                    legacy_values = {
                        "employee_id": e.id,
                        "employee_no": e.employee_no,
                        "name": e.name,
                        "phone": e.phone or "N/A",
                        "email": e.email or f"{e.employee_no.lower()}@demo.invalid",
                        "designation": e.designation or "Teacher",
                        "subject": ", ".join(codes),
                        "status": "Active",
                    }
                    insert_cols = [c for c in legacy_values if c in teacher_columns]
                    # If an old column is NOT NULL and has no ORM-era value, provide
                    # a safe demo fallback rather than allowing the seeder to fail.
                    not_null_info = db.session.execute(db.text("PRAGMA table_info(teacher)")).fetchall()
                    for row in not_null_info:
                        col = row[1]
                        not_null = bool(row[3])
                        if not_null and col not in legacy_values and col not in ("id",):
                            # Known legacy fields are covered above; unknown columns
                            # should not be guessed because their meaning is unknown.
                            raise RuntimeError(f"Legacy teacher column '{col}' is NOT NULL and is not supported by the demo seeder.")
                    placeholders = ", ".join(f":v_{c}" for c in insert_cols)
                    columns_sql = ", ".join(insert_cols)
                    params = {f"v_{c}": legacy_values[c] for c in insert_cols}
                    db.session.execute(
                        db.text(f"INSERT INTO teacher ({columns_sql}) VALUES ({placeholders})"),
                        params,
                    )
                    db.session.flush()
                    t = Teacher.query.filter_by(employee_id=e.id).first()
                else:
                    t = Teacher(employee=e, status="Active")
                    db.session.add(t); db.session.flush()
            t.subjects = [subjects[c] for c in codes]
            teacher_objs.append(t)
        db.session.flush()
        if not teacher_user.student_id:
            # Keep teacher demo login independent; portal linkage can be added later.
            pass

        # Parents and students (siblings included to demonstrate family matching)
        parent_specs = [
            ("Demo Parent Ahmed", "Father", "0300-9000001", "ahmed.parent@demo.pk", "42101-9000001-1"),
            ("Demo Parent Bilal", "Father", "0300-9000002", "bilal.parent@demo.pk", "42101-9000002-2"),
            ("Demo Parent Sana", "Mother", "0300-9000003", "sana.parent@demo.pk", "42101-9000003-3"),
            ("Demo Parent Imran", "Father", "0300-9000004", "imran.parent@demo.pk", "42101-9000004-4"),
            ("Demo Parent Farooq", "Father", "0300-9000005", "farooq.parent@demo.pk", "42101-9000005-5"),
        ]
        parents = []
        for i, (name, rel, mobile, email, cnic) in enumerate(parent_specs, 1):
            p = Parent.query.filter_by(cnic=cnic).first()
            if not p:
                p = Parent(name=name, relation=rel, mobile=mobile, phone=mobile, email=email, cnic=cnic,
                           address=f"Demo Address Block {i}, Gadap, Karachi", latitude=24.98 + i * .002, longitude=67.16 + i * .002)
                db.session.add(p); db.session.flush()
            parents.append(p)

        students = []
        student_specs = [
            ("Ayaan", "Ahmed", "M", "2014-05-12", "Class V", parents[0], "Blue", "R-101", "0300-9100001"),
            ("Hassan", "Ahmed", "M", "2016-01-20", "Class III", parents[0], "Blue", "R-101", "0300-9100002"),
            ("Fatima", "Bilal", "F", "2015-08-07", "Class IV", parents[1], "Green", "R-102", "0300-9100003"),
            ("Maryam", "Sana", "F", "2013-03-19", "Class VI", parents[2], "Red", "R-201", "0300-9100004"),
            ("Huzaifa", "Imran", "M", "2012-11-02", "Class VII", parents[3], "Yellow", "R-202", "0300-9100005"),
            ("Zainab", "Farooq", "F", "2011-09-15", "Class VIII", parents[4], "Green", "R-203", "0300-9100006"),
            ("Hamza", "Imran", "M", "2014-12-11", "Class V", parents[3], "Yellow", "R-202", "0300-9100007"),
            ("Eman", "Farooq", "F", "2015-02-28", "Class IV", parents[4], "Green", "R-203", "0300-9100008"),
            ("Usman", "Ahmed", "M", "2018-07-04", "Class I", parents[0], "Blue", "R-101", "0300-9100009"),
            ("Noor", "Sana", "F", "2017-10-23", "Class II", parents[2], "Red", "R-201", "0300-9010010"),
        ]
        for idx, (first, last, gender, dob, cls, parent, house, room, phone) in enumerate(student_specs, 1):
            adm = f"PSG-DEMO-{idx:04d}"
            st = Student.query.filter_by(admission_no=adm).first()
            if not st:
                st = Student(admission_no=adm, first_name=first, last_name=last, father_name=parent.name,
                             gender=gender, dob=date.fromisoformat(dob), class_room=classes[cls], parent=parent,
                             house=house, room_no=room, phone=phone, address=parent.address,
                             latitude=parent.latitude, longitude=parent.longitude, admission_date=date(2026, 4, 10), status="Active")
                db.session.add(st); db.session.flush()
            students.append(st)

        # Student portal login
        link_demo_accounts(password)

        # Grade scales
        for grade, mn, mx, remarks in [("A+",90,100,"Excellent"),("A",80,89.99,"Very Good"),("B",70,79.99,"Good"),("C",60,69.99,"Satisfactory"),("D",50,59.99,"Needs Improvement"),("F",0,49.99,"Fail")]:
            if not GradeScale.query.filter_by(grade=grade).first():
                db.session.add(GradeScale(grade=grade, min_percent=mn, max_percent=mx, remarks=remarks))

        # Attendance for 10 days
        for st in students:
            for day_offset in range(1, 11):
                d = TODAY - timedelta(days=day_offset)
                if not Attendance.query.filter_by(student_id=st.id, date=d).first():
                    status = "Absent" if (st.id + day_offset) % 11 == 0 else ("Late" if (st.id + day_offset) % 7 == 0 else "Present")
                    db.session.add(Attendance(student=st, date=d, status=status))

        # Exams and results
        exam = Exam.query.filter_by(name="Demo Mid Term 2026", session_id=session.id, class_id=classes["Class V"].id).first()
        if not exam:
            exam = Exam(name="Demo Mid Term 2026", session=session, class_room=classes["Class V"], term="Mid Term", start_date=TODAY-timedelta(days=20), end_date=TODAY-timedelta(days=10))
            db.session.add(exam); db.session.flush()
        class_v_students = [s for s in students if s.class_room.name == "Class V"]
        for st in class_v_students:
            for code in ["ENG","MAT","SCI","URD"]:
                if not Result.query.filter_by(exam_id=exam.id, student_id=st.id, subject_id=subjects[code].id).first():
                    marks = 55 + ((st.id * subjects[code].id) % 41)
                    db.session.add(Result(exam=exam, student=st, subject=subjects[code], marks=marks, total=100))

        # Fee structures
        fee_defs = [("Tuition Fee", 5000), ("Admission Fee", 3000), ("Transport Fee", 2500), ("Hostel Fee", 7000), ("Mess Fee", 4500), ("Computer/Lab Fee", 1000)]
        fee_structures = []
        for name, amount in fee_defs:
            fs = FeeStructure.query.filter_by(name=name, class_id=classes["Class V"].id, session_id=session.id).first()
            if not fs:
                fs = FeeStructure(name=name, class_room=classes["Class V"], session=session, amount=amount, frequency="Monthly", description=f"Demo {name}")
                db.session.add(fs); db.session.flush()
            fee_structures.append(fs)

        # Invoices / payments
        for idx, st in enumerate(students, 1):
            inv_no = f"INV-DEMO-{idx:04d}"
            inv = FeeInvoice.query.filter_by(invoice_no=inv_no).first()
            if not inv:
                tuition = fee_structures[0].amount
                transport = fee_structures[2].amount if idx % 2 == 0 else 0
                hostel = fee_structures[3].amount if idx in {4,5,6} else 0
                total = tuition + transport + hostel
                inv = FeeInvoice(invoice_no=inv_no, student=st, fee_type="Monthly Fees", amount=total, paid=0, due_date=TODAY+timedelta(days=10), status="Unpaid")
                db.session.add(inv); db.session.flush()
                db.session.add(FeeInvoiceItem(invoice=inv, fee_structure_id=fee_structures[0].id, description="Tuition Fee", amount=tuition, fee_month=TODAY.replace(day=1)))
                if transport:
                    db.session.add(FeeInvoiceItem(invoice=inv, fee_structure_id=fee_structures[2].id, description="Transport Fee", amount=transport, fee_month=TODAY.replace(day=1)))
                if hostel:
                    db.session.add(FeeInvoiceItem(invoice=inv, fee_structure_id=fee_structures[3].id, description="Hostel Fee", amount=hostel, fee_month=TODAY.replace(day=1)))
                paid = round(total * (0.6 if idx % 3 == 0 else (1.0 if idx % 3 == 1 else 0)), 2)
                if paid:
                    db.session.add(FeePayment(receipt_no=f"REC-DEMO-{idx:04d}", invoice=inv, amount=paid, payment_method="Bank" if idx % 2 else "Cash", reference=f"DEMO-{idx:05d}", received_by=accountant.id))
                    inv.paid = paid
                    inv.status = "Paid" if paid >= total else "Partial"

        # Library
        books = []
        for i, (isbn, title, author, category, qty) in enumerate([
            ("978-DEMO-001", "English Grammar Basics", "A. Khan", "English", 5),
            ("978-DEMO-002", "General Science Grade 5", "S. Ali", "Science", 4),
            ("978-DEMO-003", "Mathematics Made Easy", "M. Ahmed", "Mathematics", 6),
            ("978-DEMO-004", "Computer Fundamentals", "R. Hussain", "Computer", 3),
        ], 1):
            b = Book.query.filter_by(isbn=isbn).first()
            if not b:
                b = Book(isbn=isbn, title=title, author=author, category=category, quantity=qty, available=qty)
                db.session.add(b); db.session.flush()
            books.append(b)
        for i, (b, st) in enumerate(zip(books, students[:4])):
            if not LibraryIssue.query.filter_by(book_id=b.id, student_id=st.id, status="Issued").first():
                b.available = max(0, b.available - 1)
                db.session.add(LibraryIssue(book=b, student=st, issue_date=TODAY-timedelta(days=i+2), status="Issued"))

        # Timetable
        slots = [("Monday","08:00","08:45","ENG"),("Tuesday","08:00","08:45","MAT"),("Wednesday","08:00","08:45","SCI"),("Thursday","08:00","08:45","URD"),("Friday","08:00","08:45","ISL")]
        for day, start, end, code in slots:
            if not Timetable.query.filter_by(class_id=classes["Class V"].id, subject_id=subjects[code].id, day=day, start_time=start).first():
                teacher = teacher_objs[0] if code in ["ENG","URD"] else (teacher_objs[1] if code in ["MAT","SCI"] else teacher_objs[2])
                db.session.add(Timetable(class_room=classes["Class V"], subject=subjects[code], teacher=teacher, day=day, start_time=start, end_time=end, room="Room V-A"))

        # Transport
        vehicle = Vehicle.query.filter_by(registration_no="DEMO-PSG-001").first()
        if not vehicle:
            vehicle = Vehicle(registration_no="DEMO-PSG-001", vehicle_type="Coaster", capacity=30, driver_name="Demo Driver", driver_phone="0306-7777777", status="Active")
            db.session.add(vehicle); db.session.flush()
        route = TransportRoute.query.filter_by(name="Demo Gadap Route").first()
        if not route:
            route = TransportRoute(name="Demo Gadap Route", pickup_points="Gadap Chowk; Malir Halt; School Gate", map_points="24.98,67.16;24.99,67.17;25.00,67.18", monthly_fee=2500, vehicle=vehicle)
            db.session.add(route); db.session.flush()
        for st in students[:5]:
            if not TransportAssignment.query.filter_by(student_id=st.id, route_id=route.id).first():
                db.session.add(TransportAssignment(student=st, route=route, pickup_point="Gadap Chowk", status="Active"))

        # Hostel
        rooms = []
        for block, room_no, gender in [("Boys Block","B-101","M"),("Boys Block","B-102","M"),("Girls Block","G-201","F")]:
            r = HostelRoom.query.filter_by(block=block, room_no=room_no).first()
            if not r:
                r = HostelRoom(block=block, room_no=room_no, capacity=4, gender=gender, status="Available")
                db.session.add(r); db.session.flush()
            rooms.append(r)
        for st, room, bed in [(students[4],rooms[0],"1"),(students[6],rooms[1],"1"),(students[3],rooms[2],"1")]:
            if not HostelAllocation.query.filter_by(student_id=st.id, status="Active").first():
                db.session.add(HostelAllocation(student=st, room=room, bed_no=bed, allocated_on=TODAY-timedelta(days=30), status="Active"))

        # Inventory + transactions
        inv_items = []
        for code, name, cat, qty, reorder, loc in [
            ("IT-DEMO-001","Desktop Computer","IT Equipment",25,5,"IT Store"),
            ("STAT-DEMO-002","A4 Paper Ream","Stationery",80,20,"Main Store"),
            ("LAB-DEMO-003","Whiteboard Marker","Stationery",120,30,"Main Store"),
            ("MED-DEMO-004","First Aid Kit","Health",10,3,"Health Room"),
        ]:
            item = InventoryItem.query.filter_by(item_code=code).first()
            if not item:
                item = InventoryItem(item_code=code, name=name, category=cat, unit="pcs", quantity=qty, reorder_level=reorder, location=loc, status="Active")
                db.session.add(item); db.session.flush()
            inv_items.append(item)
        for i, item in enumerate(inv_items):
            if not InventoryTransaction.query.filter_by(item_id=item.id, reference=f"DEMO-OPEN-{i+1}").first():
                db.session.add(InventoryTransaction(item=item, transaction_type="IN", quantity=item.quantity, reference=f"DEMO-OPEN-{i+1}", created_by=admin.id))

        # Mess menu
        for offset, meal, menu, cost in [(0,"Breakfast","Paratha, Egg, Tea",180),(0,"Lunch","Chicken Biryani, Raita, Salad",420),(0,"Dinner","Daal, Rice, Roti, Salad",300),(1,"Breakfast","Bread, Omelette, Milk",160),(1,"Lunch","Chicken Karahi, Roti, Salad",450)]:
            d = TODAY + timedelta(days=offset)
            if not MessMenu.query.filter_by(menu_date=d, meal_type=meal).first():
                db.session.add(MessMenu(menu_date=d, meal_type=meal, menu=menu, estimated_cost=cost, status="Planned", created_by=admin.id))

        # Payroll
        for i, e in enumerate(employees):
            month = TODAY.strftime("%Y-%m")
            if not Payroll.query.filter_by(employee_id=e.id, month=month).first():
                basic = e.basic_salary or 0
                housing = round(basic * .10, 2); transport_a = 3000; medical = 2500
                gross = basic + housing + transport_a + medical
                tax = round(gross * .02, 2)
                net = gross - tax
                db.session.add(Payroll(employee=e, month=month, basic_salary=basic, housing_allowance=housing,
                    transport_allowance=transport_a, medical_allowance=medical, other_allowances=0, overtime=0, bonus=0,
                    absent_deduction=0, loan_deduction=0, advance_deduction=0, tax_deduction=tax, provident_fund=0,
                    other_deductions=0, allowances=housing+transport_a+medical, deductions=tax, gross_salary=gross,
                    net_salary=net, payment_method="Bank", payment_reference=f"PAY-DEMO-{i+1:03d}", status="Processed", paid_at=datetime.now(), remarks="Demo payroll"))

        # Notifications / audit / login history
        if not Notification.query.filter_by(title="Demo Parent Meeting").first():
            db.session.add(Notification(title="Demo Parent Meeting", message="Parent-teacher meeting will be held on Saturday at 10:00 AM.", audience="All", is_active=True))
        if not Notification.query.filter_by(title="Demo Fee Reminder").first():
            db.session.add(Notification(title="Demo Fee Reminder", message="Monthly fee vouchers are available in the student portal.", audience="Students", is_active=True))
        db.session.add(AuditLog(user_id=admin.id, action="DEMO_SEED", module="System", details="Overall demo data seeded"))
        db.session.add(LoginEvent(user_id=admin.id, username=admin.username, event="LOGIN", ip_address="127.0.0.1", user_agent="Demo Seeder"))

        # Promotion + status history examples
        if students:
            st = students[0]
            if not StudentPromotionHistory.query.filter_by(student_id=st.id, remarks="Demo promotion history").first():
                db.session.add(StudentPromotionHistory(student=st, from_class=classes["Class IV"], to_class=classes["Class V"], from_session=session, to_session=session, promoted_on=date(2026,4,5), changed_by=admin.id, remarks="Demo promotion history"))
            if not StudentStatusHistory.query.filter_by(student_id=st.id, remarks="Demo status history").first():
                db.session.add(StudentStatusHistory(student=st, old_status="Active", new_status="Active", changed_by=admin.id, remarks="Demo status history"))

        # Bank accounts
        if not BankAccount.query.filter_by(account_number="DEMO-001-PSG").first():
            db.session.add(BankAccount(bank_name="Demo Bank Pakistan", account_title="Public School Gadap - Demo", account_number="DEMO-001-PSG", iban="PK00DEMO0000000000000001", branch="Gadap Branch", is_active=True))

        # WhatsApp prepared messages
        for st in students[:3]:
            phone = st.parent.mobile or st.phone or "03000000000"
            if not WhatsAppMessage.query.filter_by(student_id=st.id, phone=phone).first():
                db.session.add(WhatsAppMessage(student=st, phone=phone, message=f"Dear Parent, demo fee voucher for {st.first_name} is available in the school portal.", status="Prepared"))

        # Core demo permissions
        for role in ["admin", "accountant", "admission_officer", "staff", "teacher", "student"]:
            for module in ["students", "academics", "accounts", "reports"]:
                action = "view"
                existing = Permission.query.filter_by(role=role, module=module, action=action).first()
                if not existing:
                    db.session.add(Permission(role=role, module=module, action=action, allowed=True))

        db.session.add(SystemSetting(key="demo.seed.v1", value=datetime.utcnow().isoformat()))
        db.session.commit()

        print("Demo data seeded successfully.")
        print("Demo logins:")
        print("  admin_demo")
        print("  accountant_demo")
        print("  admission_demo")
        print("  staff_demo")
        print("  teacher_demo")
        print("  student_demo")
        print("  parent_demo")


if __name__ == "__main__":
    main()
