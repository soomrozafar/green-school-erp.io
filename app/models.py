from datetime import datetime
from hmac import compare_digest, digest
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from .extensions import db, login_manager

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="admin", nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=True, index=True)
    student = db.relationship("Student", foreign_keys=[student_id], backref=db.backref("portal_user", uselist=False))
    parent_id = db.Column(db.Integer, db.ForeignKey("parent.id"), index=True)
    parent = db.relationship("Parent")
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), index=True)
    teacher = db.relationship("Teacher")

    @property
    def family_or_demo_teacher(self):
        return self.role == "parent" or (self.role == "teacher" and self.username == "teacher_demo")

    is_active_user = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)
    @property
    def is_active(self):
        return bool(self.is_active_user) and self.role != "website_editor"

    def get_id(self):
        key = current_app.secret_key.encode()
        signature = digest(key, self.password_hash.encode(), "sha256").hex()
        return f"{self.id}:{signature}"


@login_manager.user_loader
def load_user(user_id):
    identifier, separator, signature = user_id.partition(":")
    if (not separator or not identifier.isascii() or not identifier.isdecimal()
            or len(identifier) > 18 or len(signature) != 64 or not signature.isascii()):
        return None
    user = db.session.get(User, int(identifier))
    if user is not None and user.is_active and compare_digest(user.get_id(), user_id):
        return user
    return None

class AcademicSession(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(50), unique=True, nullable=False)
    start_date=db.Column(db.Date)
    end_date=db.Column(db.Date)
    is_active=db.Column(db.Boolean, default=True)

class ClassRoom(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(80), nullable=False)
    section=db.Column(db.String(30), nullable=False)
    capacity=db.Column(db.Integer, default=40)
    session_id=db.Column(db.Integer, db.ForeignKey("academic_session.id"))
    session=db.relationship("AcademicSession")

class Subject(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    code=db.Column(db.String(30), unique=True)
    name=db.Column(db.String(120), nullable=False)
    max_marks=db.Column(db.Float, default=100)
    teachers=db.relationship("Teacher", secondary="teacher_subject", back_populates="subjects", lazy="select")

class Parent(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(150), nullable=False)
    relation=db.Column(db.String(50))
    phone=db.Column(db.String(40), index=True)
    mobile=db.Column(db.String(40), index=True)
    email=db.Column(db.String(120), index=True)
    cnic=db.Column(db.String(30), index=True)
    address=db.Column(db.Text)
    latitude=db.Column(db.Float)
    longitude=db.Column(db.Float)
    children=db.relationship("Student", back_populates="parent", lazy=True)

class Student(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    admission_no=db.Column(db.String(50), unique=True, nullable=False)
    first_name=db.Column(db.String(100), nullable=False)
    last_name=db.Column(db.String(100))
    father_name=db.Column(db.String(150))
    gender=db.Column(db.String(20))
    dob=db.Column(db.Date)
    class_id=db.Column(db.Integer, db.ForeignKey("class_room.id"))
    parent_id=db.Column(db.Integer, db.ForeignKey("parent.id"))
    house=db.Column(db.String(80)); room_no=db.Column(db.String(30))
    phone=db.Column(db.String(40)); address=db.Column(db.Text)
    latitude=db.Column(db.Float); longitude=db.Column(db.Float)
    admission_date=db.Column(db.Date)
    photo_path=db.Column(db.String(255))
    status=db.Column(db.String(30), default="Active")
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    class_room=db.relationship("ClassRoom")
    parent=db.relationship("Parent", back_populates="children")

class Teacher(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    employee_id=db.Column(db.Integer, db.ForeignKey("employee.id"), unique=True, nullable=False)
    status=db.Column(db.String(30), default="Active")
    employee=db.relationship("Employee", back_populates="teacher")
    subjects=db.relationship("Subject", secondary="teacher_subject", back_populates="teachers", lazy="joined")

teacher_subject=db.Table("teacher_subject",
    db.Column("teacher_id", db.Integer, db.ForeignKey("teacher.id"), primary_key=True),
    db.Column("subject_id", db.Integer, db.ForeignKey("subject.id"), primary_key=True),
)

class Attendance(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    student_id=db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    date=db.Column(db.Date, nullable=False); status=db.Column(db.String(20), nullable=False)
    student=db.relationship("Student")


class TeacherAttendance(db.Model):
    __table_args__ = (db.UniqueConstraint("teacher_id", "date", name="uq_teacher_attendance_day"),)
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

class Exam(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(120), nullable=False)
    session_id=db.Column(db.Integer, db.ForeignKey("academic_session.id"))
    class_id=db.Column(db.Integer, db.ForeignKey("class_room.id"))
    approved_at = db.Column(db.DateTime)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])
    term=db.Column(db.String(50)); start_date=db.Column(db.Date); end_date=db.Column(db.Date)
    session=db.relationship("AcademicSession"); class_room=db.relationship("ClassRoom")

class Result(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    exam_id=db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    student_id=db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    subject_id=db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    marks=db.Column(db.Float, default=0); total=db.Column(db.Float, default=100)
    exam=db.relationship("Exam"); student=db.relationship("Student"); subject=db.relationship("Subject")

class FeeInvoice(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    invoice_no=db.Column(db.String(50), unique=True, nullable=False)
    student_id=db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    fee_type=db.Column(db.String(80), nullable=False); amount=db.Column(db.Float, default=0)
    paid=db.Column(db.Float, default=0); due_date=db.Column(db.Date); status=db.Column(db.String(30), default="Unpaid")
    student=db.relationship("Student")
    items=db.relationship("FeeInvoiceItem", back_populates="invoice", cascade="all, delete-orphan", lazy=True)


class VoucherBatch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    invoice_ids = db.Column(db.JSON, nullable=False)
    student_count = db.Column(db.Integer, nullable=False)
    created_count = db.Column(db.Integer, nullable=False)

class Book(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    isbn=db.Column(db.String(50), unique=True); title=db.Column(db.String(200), nullable=False)
    author=db.Column(db.String(150)); category=db.Column(db.String(100))
    quantity=db.Column(db.Integer, default=1); available=db.Column(db.Integer, default=1)

class LibraryIssue(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    book_id=db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)
    student_id=db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    issue_date=db.Column(db.Date, default=datetime.utcnow); return_date=db.Column(db.Date)
    status=db.Column(db.String(30), default="Issued")
    due_date = db.Column(db.Date)
    book=db.relationship("Book"); student=db.relationship("Student")

class Timetable(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    class_id=db.Column(db.Integer, db.ForeignKey("class_room.id"), nullable=False)
    subject_id=db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    teacher_id=db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False)
    day=db.Column(db.String(20), nullable=False)
    start_time=db.Column(db.String(10), nullable=False)
    end_time=db.Column(db.String(10), nullable=False)
    room=db.Column(db.String(50))
    class_room=db.relationship("ClassRoom"); subject=db.relationship("Subject"); teacher=db.relationship("Teacher")


class FeePayment(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    receipt_no=db.Column(db.String(50), unique=True, nullable=False)
    invoice_id=db.Column(db.Integer, db.ForeignKey("fee_invoice.id"), nullable=False)
    amount=db.Column(db.Float, nullable=False)
    payment_method=db.Column(db.String(40), default="Cash")
    reference=db.Column(db.String(120))
    paid_at=db.Column(db.DateTime, default=datetime.utcnow)
    received_by=db.Column(db.Integer, db.ForeignKey("user.id"))
    invoice=db.relationship("FeeInvoice", backref=db.backref("payments", lazy=True))
    receiver=db.relationship("User")


class OnlineFeePayment(db.Model):
    id = db.Column(db.String(32), primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("fee_invoice.id"), nullable=False, index=True)
    invoice = db.relationship("FeeInvoice")
    initiated_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    active_key = db.Column(db.String(64), unique=True)
    environment = db.Column(db.String(12), nullable=False)
    amount_minor = db.Column(db.Integer, nullable=False)
    tracker = db.Column(db.String(90), unique=True)
    state = db.Column(db.String(20), nullable=False, default="creating")
    receipt_id = db.Column(db.Integer, db.ForeignKey("fee_payment.id"), unique=True)
    receipt = db.relationship("FeePayment")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Notification(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    title=db.Column(db.String(180), nullable=False)
    message=db.Column(db.Text, nullable=False)
    audience=db.Column(db.String(40), default="All")
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    is_active=db.Column(db.Boolean, default=True)

class LoginEvent(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.Integer, db.ForeignKey("user.id"))
    username=db.Column(db.String(80), nullable=False)
    event=db.Column(db.String(30), nullable=False)
    ip_address=db.Column(db.String(64))
    user_agent=db.Column(db.String(255))
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    user=db.relationship("User")

class AuditLog(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.Integer, db.ForeignKey("user.id"))
    action=db.Column(db.String(100), nullable=False)
    module=db.Column(db.String(80))
    details=db.Column(db.Text)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    user=db.relationship("User")

class FeeStructure(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(120), nullable=False)
    class_id=db.Column(db.Integer, db.ForeignKey("class_room.id"))
    session_id=db.Column(db.Integer, db.ForeignKey("academic_session.id"))
    amount=db.Column(db.Float, nullable=False, default=0)
    frequency=db.Column(db.String(30), default="Monthly")
    description=db.Column(db.Text)
    is_active=db.Column(db.Boolean, default=True)
    class_room=db.relationship("ClassRoom")
    session=db.relationship("AcademicSession")

class FeeInvoiceItem(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    invoice_id=db.Column(db.Integer, db.ForeignKey("fee_invoice.id"), nullable=False)
    fee_structure_id=db.Column(db.Integer, db.ForeignKey("fee_structure.id"))
    description=db.Column(db.String(150), nullable=False)
    amount=db.Column(db.Float, nullable=False, default=0)
    fee_month=db.Column(db.Date, index=True)
    invoice=db.relationship("FeeInvoice", back_populates="items")
    fee_structure=db.relationship("FeeStructure")

class StudentPromotionHistory(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    student_id=db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    from_class_id=db.Column(db.Integer, db.ForeignKey("class_room.id"))
    to_class_id=db.Column(db.Integer, db.ForeignKey("class_room.id"))
    from_session_id=db.Column(db.Integer, db.ForeignKey("academic_session.id"))
    to_session_id=db.Column(db.Integer, db.ForeignKey("academic_session.id"))
    promoted_on=db.Column(db.Date, default=datetime.utcnow)
    remarks=db.Column(db.Text)
    changed_by=db.Column(db.Integer, db.ForeignKey("user.id"))
    student=db.relationship("Student")
    from_class=db.relationship("ClassRoom", foreign_keys=[from_class_id])
    to_class=db.relationship("ClassRoom", foreign_keys=[to_class_id])
    from_session=db.relationship("AcademicSession", foreign_keys=[from_session_id])
    to_session=db.relationship("AcademicSession", foreign_keys=[to_session_id])
    user=db.relationship("User")

class StudentStatusHistory(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    student_id=db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    old_status=db.Column(db.String(30))
    new_status=db.Column(db.String(30), nullable=False)
    remarks=db.Column(db.Text)
    changed_at=db.Column(db.DateTime, default=datetime.utcnow)
    changed_by=db.Column(db.Integer, db.ForeignKey("user.id"))
    student=db.relationship("Student")
    user=db.relationship("User")

class Employee(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    employee_no=db.Column(db.String(50), unique=True, nullable=False)
    name=db.Column(db.String(150), nullable=False)
    employee_type=db.Column(db.String(30), default="Non-Teacher", nullable=False)
    department=db.Column(db.String(100)); designation=db.Column(db.String(100))
    gender=db.Column(db.String(20)); dob=db.Column(db.Date)
    father_name=db.Column(db.String(150)); cnic=db.Column(db.String(30), index=True)
    phone=db.Column(db.String(40)); email=db.Column(db.String(120)); address=db.Column(db.Text)
    qualification=db.Column(db.String(200)); experience_years=db.Column(db.Float, default=0)
    joining_date=db.Column(db.Date); basic_salary=db.Column(db.Float, default=0)
    bank_name=db.Column(db.String(120)); bank_account=db.Column(db.String(80)); iban=db.Column(db.String(80))
    emergency_contact_name=db.Column(db.String(150)); emergency_contact_phone=db.Column(db.String(40))
    photo_path=db.Column(db.String(255)); status=db.Column(db.String(30), default="Active")
    teacher=db.relationship("Teacher", back_populates="employee", uselist=False)

class StaffLeave(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False, index=True)
    employee = db.relationship("Employee")
    leave_type = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default="Pending")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])
    reviewed_at = db.Column(db.DateTime)
    review_note = db.Column(db.String(500))


class Payroll(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    employee_id=db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    month=db.Column(db.String(7), nullable=False)
    basic_salary=db.Column(db.Float, default=0)
    housing_allowance=db.Column(db.Float, default=0); transport_allowance=db.Column(db.Float, default=0)
    medical_allowance=db.Column(db.Float, default=0); other_allowances=db.Column(db.Float, default=0)
    overtime=db.Column(db.Float, default=0); bonus=db.Column(db.Float, default=0)
    absent_deduction=db.Column(db.Float, default=0); loan_deduction=db.Column(db.Float, default=0)
    advance_deduction=db.Column(db.Float, default=0); tax_deduction=db.Column(db.Float, default=0)
    provident_fund=db.Column(db.Float, default=0); other_deductions=db.Column(db.Float, default=0)
    allowances=db.Column(db.Float, default=0); deductions=db.Column(db.Float, default=0)
    gross_salary=db.Column(db.Float, default=0); net_salary=db.Column(db.Float, default=0)
    payment_method=db.Column(db.String(30), default="Bank"); payment_reference=db.Column(db.String(120))
    status=db.Column(db.String(30), default="Processed"); paid_at=db.Column(db.DateTime); remarks=db.Column(db.Text)
    employee=db.relationship("Employee")

class GradeScale(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    grade=db.Column(db.String(10), unique=True, nullable=False)
    min_percent=db.Column(db.Float, nullable=False); max_percent=db.Column(db.Float, nullable=False)
    remarks=db.Column(db.String(120))

class Vehicle(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    registration_no=db.Column(db.String(50), unique=True, nullable=False)
    vehicle_type=db.Column(db.String(50)); capacity=db.Column(db.Integer, default=30)
    driver_name=db.Column(db.String(120)); driver_phone=db.Column(db.String(40)); status=db.Column(db.String(30), default='Active')

class TransportRoute(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(120), nullable=False); pickup_points=db.Column(db.Text)
    map_points=db.Column(db.Text)
    monthly_fee=db.Column(db.Float, default=0); vehicle_id=db.Column(db.Integer, db.ForeignKey('vehicle.id'))
    vehicle=db.relationship('Vehicle')

class TransportAssignment(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    student_id=db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    route_id=db.Column(db.Integer, db.ForeignKey('transport_route.id'), nullable=False)
    pickup_point=db.Column(db.String(150)); status=db.Column(db.String(30), default='Active')
    student=db.relationship('Student'); route=db.relationship('TransportRoute')

class HostelRoom(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    block=db.Column(db.String(80), nullable=False); room_no=db.Column(db.String(30), nullable=False)
    capacity=db.Column(db.Integer, default=4); gender=db.Column(db.String(20)); status=db.Column(db.String(30), default='Available')

class HostelAllocation(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    student_id=db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    room_id=db.Column(db.Integer, db.ForeignKey('hostel_room.id'), nullable=False)
    bed_no=db.Column(db.String(20)); allocated_on=db.Column(db.Date, default=datetime.utcnow); status=db.Column(db.String(30), default='Active')
    student=db.relationship('Student'); room=db.relationship('HostelRoom')

class InventoryItem(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    item_code=db.Column(db.String(50), unique=True, nullable=False); name=db.Column(db.String(150), nullable=False)
    category=db.Column(db.String(80)); unit=db.Column(db.String(30), default='pcs'); quantity=db.Column(db.Integer, default=0)
    reorder_level=db.Column(db.Integer, default=5); location=db.Column(db.String(100)); status=db.Column(db.String(30), default='Active')

class InventoryTransaction(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    item_id=db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    transaction_type=db.Column(db.String(20), nullable=False); quantity=db.Column(db.Integer, nullable=False)
    reference=db.Column(db.String(120)); created_at=db.Column(db.DateTime, default=datetime.utcnow); created_by=db.Column(db.Integer, db.ForeignKey('user.id'))
    item=db.relationship('InventoryItem'); user=db.relationship('User')

class MessMenu(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    menu_date=db.Column(db.Date, nullable=False, index=True)
    meal_type=db.Column(db.String(30), nullable=False)
    menu=db.Column(db.String(500), nullable=False)
    estimated_cost=db.Column(db.Float, default=0)
    status=db.Column(db.String(30), default="Planned")
    created_by=db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    user=db.relationship("User")

class SequenceCounter(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    code_type=db.Column(db.String(40), unique=True, nullable=False)
    current_value=db.Column(db.Integer, default=0, nullable=False)

class Permission(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    role=db.Column(db.String(30), nullable=False)
    module=db.Column(db.String(80), nullable=False)
    action=db.Column(db.String(40), nullable=False)
    allowed=db.Column(db.Boolean, default=True)
    __table_args__=(db.UniqueConstraint('role','module','action', name='uq_role_module_action'),)


class SystemSetting(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    key=db.Column(db.String(100), unique=True, nullable=False)
    value=db.Column(db.Text)
    updated_at=db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WebsiteHeroSlide(db.Model):
    __tablename__ = "website_hero_slide"
    id=db.Column(db.Integer, primary_key=True)
    kicker=db.Column(db.String(180), default="PUBLIC SCHOOL GADAP · KARACHI")
    title=db.Column(db.String(300), nullable=False)
    text=db.Column(db.Text)
    image_path=db.Column(db.String(255), nullable=False)
    button_text=db.Column(db.String(100), default="Explore School")
    button_url=db.Column(db.String(255), default="#about")
    sort_order=db.Column(db.Integer, default=0)
    is_active=db.Column(db.Boolean, default=True, nullable=False)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    updated_at=db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WebsiteAcademicPage(db.Model):
    __tablename__ = "website_academic_page"
    id=db.Column(db.Integer, primary_key=True)
    page_type=db.Column(db.String(40), unique=True, nullable=False, index=True)
    slug=db.Column(db.String(120), unique=True, nullable=False, index=True)
    title=db.Column(db.String(180), nullable=False)
    hero_kicker=db.Column(db.String(180), default="ACADEMICS · PUBLIC SCHOOL GADAP")
    hero_image=db.Column(db.String(255))
    intro=db.Column(db.Text)
    overview=db.Column(db.Text)
    highlights=db.Column(db.Text)
    curriculum=db.Column(db.Text)
    student_experience=db.Column(db.Text)
    support_programs=db.Column(db.Text)
    subjects=db.Column(db.Text)
    answer_summary=db.Column(db.Text)
    faq_json=db.Column(db.Text)
    seo_title=db.Column(db.String(180))
    meta_description=db.Column(db.String(320))
    seo_keywords=db.Column(db.String(500))
    canonical_url=db.Column(db.String(500))
    is_published=db.Column(db.Boolean, default=True, nullable=False)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    updated_at=db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WebsiteNews(db.Model):
    __tablename__ = "website_news"
    id=db.Column(db.Integer, primary_key=True)
    title=db.Column(db.String(220), nullable=False)
    slug=db.Column(db.String(240), unique=True, nullable=False, index=True)
    excerpt=db.Column(db.Text)
    content=db.Column(db.Text, nullable=False)
    image_path=db.Column(db.String(255))
    category=db.Column(db.String(80), default="School News")
    author=db.Column(db.String(120))
    published_at=db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_published=db.Column(db.Boolean, default=True, nullable=False)
    is_featured=db.Column(db.Boolean, default=False, nullable=False)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    updated_at=db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BankAccount(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    bank_name=db.Column(db.String(120), nullable=False)
    account_title=db.Column(db.String(160), nullable=False)
    account_number=db.Column(db.String(80))
    iban=db.Column(db.String(80))
    branch=db.Column(db.String(120))
    is_active=db.Column(db.Boolean, default=True)

class WhatsAppMessage(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    student_id=db.Column(db.Integer, db.ForeignKey('student.id'))
    phone=db.Column(db.String(40), nullable=False)
    message=db.Column(db.Text, nullable=False)
    status=db.Column(db.String(30), default='Prepared')
    provider_message_id=db.Column(db.String(160))
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    sent_at=db.Column(db.DateTime)
    student=db.relationship('Student')
