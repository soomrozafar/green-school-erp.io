from typing import NamedTuple

from sqlalchemy import func

from . import models as m
from .access import EXAM_APPROVERS
from .extensions import db

ACADEMIC = ("staff", *EXAM_APPROVERS)
ADMISSIONS = ("admission_officer", "staff")
OPERATIONS = ("operations_admin",)
HR = ("hr_officer", "principal", "vice_principal")
ACCOUNTS = ("accountant",)


class Report(NamedTuple):
    name: str
    group: str
    model: type
    columns: tuple
    roles: tuple = ()
    joins: tuple = ()
    date_field: object = None
    bucket: object = None
    totals: tuple = ()
    student_scope: bool = False


student_name = func.trim(m.Student.first_name + " " + func.coalesce(m.Student.last_name, ""))
student_columns = (("Admission no.", m.Student.admission_no), ("Student", student_name))


REPORTS = {
    "students": Report("Student Register", "Admissions", m.Student,
                       student_columns + (("Class", m.ClassRoom.name), ("Section", m.ClassRoom.section),
                                          ("Admitted", m.Student.admission_date), ("Status", m.Student.status)),
                       ADMISSIONS, (m.Student.class_room,), m.Student.admission_date, m.Student.status,
                       student_scope=True),
    "families": Report("Families & Guardians", "Admissions", m.Parent,
                       (("Guardian", m.Parent.name), ("Relationship", m.Parent.relation)),
                       ADMISSIONS, bucket=m.Parent.relation),
    "promotions": Report("Student Promotions", "Admissions", m.StudentPromotionHistory,
                         student_columns + (("Date", m.StudentPromotionHistory.promoted_on),),
                         ADMISSIONS, (m.StudentPromotionHistory.student,), m.StudentPromotionHistory.promoted_on),
    "student-attendance": Report("Student Attendance", "Academics", m.Attendance,
                                 student_columns + (("Date", m.Attendance.date), ("Status", m.Attendance.status)),
                                 (*ACADEMIC, "teacher"), (m.Attendance.student, m.Student.class_room),
                                 m.Attendance.date, m.Attendance.status, student_scope=True),
    "teachers": Report("Teacher Directory", "Academics", m.Teacher,
                       (("Employee no.", m.Employee.employee_no), ("Teacher", m.Employee.name), ("Status", m.Teacher.status)),
                       ACADEMIC, (m.Teacher.employee,), bucket=m.Teacher.status),
    "timetable": Report("Class Timetable", "Academics", m.Timetable,
                        (("Class", m.ClassRoom.name), ("Section", m.ClassRoom.section), ("Subject", m.Subject.name),
                         ("Teacher", m.Employee.name), ("Day", m.Timetable.day), ("Start", m.Timetable.start_time),
                         ("End", m.Timetable.end_time), ("Room", m.Timetable.room)),
                        (*ACADEMIC, "teacher"), (m.Timetable.class_room, m.Timetable.subject, m.Timetable.teacher, m.Teacher.employee),
                        bucket=m.Timetable.day),
    "exams": Report("Exam Schedule", "Academics", m.Exam,
                    (("Exam", m.Exam.name), ("Term", m.Exam.term), ("Class", m.ClassRoom.name),
                     ("Starts", m.Exam.start_date), ("Ends", m.Exam.end_date), ("Published", m.Exam.approved_at)),
                    ACADEMIC, (m.Exam.class_room,), m.Exam.start_date, m.Exam.term),
    "results": Report("Published Results", "Academics", m.Result,
                       student_columns + (("Exam", m.Exam.name), ("Subject", m.Subject.name),
                                          ("Marks", m.Result.marks), ("Out of", m.Result.total)),
                       ACADEMIC, (m.Result.student, m.Student.class_room, m.Result.exam, m.Result.subject),
                       m.Exam.approved_at, m.Exam.term, student_scope=True),
    "fee-structures": Report("Fee Structures", "Finance", m.FeeStructure,
                             (("Fee", m.FeeStructure.name), ("Frequency", m.FeeStructure.frequency), ("Amount", m.FeeStructure.amount), ("Class", m.ClassRoom.name)),
                             ACCOUNTS, (m.FeeStructure.class_room,), totals=(("Configured amounts", m.FeeStructure.amount),)),
    "invoices": Report("Fee Invoices & Outstanding", "Finance", m.FeeInvoice,
                        (("Invoice", m.FeeInvoice.invoice_no),) + student_columns +
                        (("Billed", m.FeeInvoice.amount), ("Paid", m.FeeInvoice.paid),
                         ("Due date", m.FeeInvoice.due_date), ("Status", m.FeeInvoice.status)),
                        ACCOUNTS, (m.FeeInvoice.student, m.Student.class_room), m.FeeInvoice.due_date, m.FeeInvoice.status,
                        (("Billed", m.FeeInvoice.amount), ("Paid", m.FeeInvoice.paid),
                         ("Outstanding", m.FeeInvoice.amount - func.coalesce(m.FeeInvoice.paid, 0))), True),
    "collections": Report("Fee Collections & Receipts", "Finance", m.FeePayment,
                           (("Receipt", m.FeePayment.receipt_no), ("Invoice", m.FeeInvoice.invoice_no),
                            ("Received", m.FeePayment.paid_at), ("Method", m.FeePayment.payment_method),
                            ("Amount", m.FeePayment.amount)), ACCOUNTS, (m.FeePayment.invoice,),
                           m.FeePayment.paid_at, m.FeePayment.payment_method, (("Collected", m.FeePayment.amount),)),
    "online-payments": Report("Online Payment Status", "Finance", m.OnlineFeePayment,
                              (("Invoice", m.FeeInvoice.invoice_no), ("Environment", m.OnlineFeePayment.environment),
                               ("State", m.OnlineFeePayment.state), ("PKR", m.OnlineFeePayment.amount_minor / 100.0)),
                              ACCOUNTS, (m.OnlineFeePayment.invoice,), bucket=m.OnlineFeePayment.state),
    "employees": Report("Employee Register", "HR & Payroll", m.Employee,
                         (("Employee no.", m.Employee.employee_no), ("Employee", m.Employee.name),
                          ("Department", m.Employee.department), ("Designation", m.Employee.designation),
                          ("Status", m.Employee.status)), HR, bucket=m.Employee.status),
    "teacher-attendance": Report("Teacher Attendance", "HR & Payroll", m.TeacherAttendance,
                                 (("Employee", m.Employee.name), ("Date", m.TeacherAttendance.date),
                                  ("Status", m.TeacherAttendance.status)), HR,
                                 ((m.Teacher, m.Teacher.id == m.TeacherAttendance.teacher_id), m.Teacher.employee), m.TeacherAttendance.date, m.TeacherAttendance.status),
    "leave": Report("Staff Leave", "HR & Payroll", m.StaffLeave,
                    (("Employee", m.Employee.name), ("Type", m.StaffLeave.leave_type), ("From", m.StaffLeave.start_date),
                     ("To", m.StaffLeave.end_date), ("Status", m.StaffLeave.status)),
                    HR, (m.StaffLeave.employee,), m.StaffLeave.start_date, m.StaffLeave.status),
    "payroll": Report("Payroll Register", "HR & Payroll", m.Payroll,
                      (("Employee", m.Employee.name), ("Month", m.Payroll.month), ("Basic", m.Payroll.basic_salary),
                       ("Bonus", m.Payroll.bonus), ("Deductions", m.Payroll.deductions), ("Net", m.Payroll.net_salary),
                       ("Status", m.Payroll.status)), ACCOUNTS, (m.Payroll.employee,), bucket=m.Payroll.status,
                      totals=(("Net pay", m.Payroll.net_salary), ("Bonus", m.Payroll.bonus), ("Deductions", m.Payroll.deductions))),
    "library": Report("Library Catalogue", "Operations", m.Book,
                      (("ISBN", m.Book.isbn), ("Title", m.Book.title), ("Author", m.Book.author),
                       ("Category", m.Book.category), ("Copies", m.Book.quantity), ("Available", m.Book.available)),
                      ("librarian",), bucket=m.Book.category, totals=(("Copies", m.Book.quantity), ("Available", m.Book.available))),
    "loans": Report("Library Circulation", "Operations", m.LibraryIssue,
                    student_columns + (("Book", m.Book.title), ("Issued", m.LibraryIssue.issue_date),
                                       ("Due", m.LibraryIssue.due_date), ("Returned", m.LibraryIssue.return_date),
                                       ("Status", m.LibraryIssue.status)),
                    ("librarian",), (m.LibraryIssue.student, m.LibraryIssue.book), m.LibraryIssue.issue_date, m.LibraryIssue.status),
    "transport": Report("Transport Assignments", "Operations", m.TransportAssignment,
                        student_columns + (("Route", m.TransportRoute.name), ("Pickup", m.TransportAssignment.pickup_point),
                                           ("Status", m.TransportAssignment.status)),
                        OPERATIONS, (m.TransportAssignment.student, m.TransportAssignment.route), bucket=m.TransportAssignment.status),
    "fleet": Report("Transport Fleet", "Operations", m.Vehicle,
                    (("Vehicle", m.Vehicle.registration_no), ("Driver", m.Vehicle.driver_name),
                     ("Capacity", m.Vehicle.capacity), ("Status", m.Vehicle.status)),
                    OPERATIONS, bucket=m.Vehicle.status, totals=(("Seats", m.Vehicle.capacity),)),
    "hostel": Report("Hostel Occupancy", "Operations", m.HostelAllocation,
                     student_columns + (("Block", m.HostelRoom.block), ("Room", m.HostelRoom.room_no),
                                        ("Bed", m.HostelAllocation.bed_no), ("Allocated", m.HostelAllocation.allocated_on),
                                        ("Status", m.HostelAllocation.status)),
                     OPERATIONS, (m.HostelAllocation.student, m.HostelAllocation.room), m.HostelAllocation.allocated_on,
                     m.HostelAllocation.status),
    "rooms": Report("Hostel Rooms", "Operations", m.HostelRoom,
                    (("Block", m.HostelRoom.block), ("Room", m.HostelRoom.room_no),
                     ("Capacity", m.HostelRoom.capacity), ("Status", m.HostelRoom.status)),
                    OPERATIONS, bucket=m.HostelRoom.status, totals=(("Bed capacity", m.HostelRoom.capacity),)),
    "inventory": Report("Inventory Stock", "Operations", m.InventoryItem,
                        (("Code", m.InventoryItem.item_code), ("Item", m.InventoryItem.name),
                         ("Category", m.InventoryItem.category), ("Stock", m.InventoryItem.quantity),
                         ("Reorder level", m.InventoryItem.reorder_level), ("Location", m.InventoryItem.location),
                         ("Stock level", db.case((m.InventoryItem.quantity <= m.InventoryItem.reorder_level, "Low stock"), else_="In stock"))),
                        OPERATIONS, bucket=db.case((m.InventoryItem.quantity <= m.InventoryItem.reorder_level, "Low stock"), else_="In stock")),
    "stock-movements": Report("Inventory Movements", "Operations", m.InventoryTransaction,
                              (("Item", m.InventoryItem.name), ("Date", m.InventoryTransaction.created_at),
                               ("Type", m.InventoryTransaction.transaction_type), ("Quantity", m.InventoryTransaction.quantity)),
                              OPERATIONS, (m.InventoryTransaction.item,), m.InventoryTransaction.created_at, m.InventoryTransaction.transaction_type),
    "mess": Report("Mess & Dining", "Operations", m.MessMenu,
                   (("Date", m.MessMenu.menu_date), ("Meal", m.MessMenu.meal_type), ("Menu", m.MessMenu.menu),
                    ("Estimated cost", m.MessMenu.estimated_cost), ("Status", m.MessMenu.status)),
                   OPERATIONS, date_field=m.MessMenu.menu_date, bucket=m.MessMenu.meal_type,
                   totals=(("Estimated cost", m.MessMenu.estimated_cost),)),
    "notifications": Report("Announcements", "Communication", m.Notification,
                            (("Title", m.Notification.title), ("Audience", m.Notification.audience),
                             ("Created", m.Notification.created_at), ("Active", m.Notification.is_active)),
                            ("staff",), date_field=m.Notification.created_at, bucket=m.Notification.audience),
    "whatsapp": Report("WhatsApp Delivery", "Communication", m.WhatsAppMessage,
                       (("Created", m.WhatsAppMessage.created_at), ("Sent", m.WhatsAppMessage.sent_at),
                        ("Status", m.WhatsAppMessage.status)), date_field=m.WhatsAppMessage.created_at, bucket=m.WhatsAppMessage.status),
    "login": Report("Login Activity", "Administration", m.LoginEvent,
                    (("User", m.LoginEvent.username), ("Event", m.LoginEvent.event), ("Time", m.LoginEvent.created_at)),
                    date_field=m.LoginEvent.created_at, bucket=m.LoginEvent.event),
    "audit": Report("Audit Activity", "Administration", m.AuditLog,
                    (("Module", m.AuditLog.module), ("Action", m.AuditLog.action), ("Time", m.AuditLog.created_at)),
                    date_field=m.AuditLog.created_at, bucket=m.AuditLog.module),
    "classes": Report("Class Sections", "Academics", m.ClassRoom,
                      (("Class", m.ClassRoom.name), ("Section", m.ClassRoom.section),
                       ("Session", m.AcademicSession.name), ("Capacity", m.ClassRoom.capacity)),
                      ACADEMIC, (m.ClassRoom.session,), bucket=m.ClassRoom.name),
    "subjects": Report("Subject Register", "Academics", m.Subject,
                       (("Code", m.Subject.code), ("Subject", m.Subject.name), ("Maximum marks", m.Subject.max_marks)),
                       ACADEMIC),
    "grades": Report("Grade Scale", "Academics", m.GradeScale,
                     (("Grade", m.GradeScale.grade), ("Minimum %", m.GradeScale.min_percent),
                      ("Maximum %", m.GradeScale.max_percent), ("Remarks", m.GradeScale.remarks)), ACADEMIC),
    "voucher-batches": Report("Bulk Voucher Batches", "Finance", m.VoucherBatch,
                              (("Batch", m.VoucherBatch.id), ("Date", m.VoucherBatch.created_at),
                               ("Students", m.VoucherBatch.student_count), ("New invoices", m.VoucherBatch.created_count)),
                              ACCOUNTS, date_field=m.VoucherBatch.created_at,
                              totals=(("New invoices", m.VoucherBatch.created_count),)),
    "bank-accounts": Report("Bank Account Register", "Finance", m.BankAccount,
                            (("Bank", m.BankAccount.bank_name), ("Account title", m.BankAccount.account_title),
                             ("Branch", m.BankAccount.branch), ("Active", m.BankAccount.is_active)), ACCOUNTS),
    "routes": Report("Transport Routes", "Operations", m.TransportRoute,
                     (("Route", m.TransportRoute.name), ("Pickup points", m.TransportRoute.pickup_points),
                      ("Monthly fee", m.TransportRoute.monthly_fee)), OPERATIONS),
}
