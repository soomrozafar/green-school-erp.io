import csv, io
from xml.sax.saxutils import escape
from types import SimpleNamespace
from flask import Blueprint, Response, render_template, send_file, request, abort
from flask_login import login_required, current_user
from .access import roles_required
from .models import ClassRoom
from .extensions import db
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode import qr
from reportlab.lib.utils import ImageReader
import os, hmac, hashlib, base64
from .models import Student, FeeInvoice, FeePayment, Employee, Result
from sqlalchemy.orm import selectinload, joinedload

exports_bp=Blueprint('exports', __name__, url_prefix='/exports')

def csv_response(filename, headers, rows):
    out=io.StringIO(); w=csv.writer(out); w.writerow(headers); w.writerows(rows)
    return Response('\ufeff'+out.getvalue(), mimetype='text/csv; charset=utf-8', headers={'Content-Disposition':f'attachment; filename={filename}'})

def xlsx_response(filename, sheet, headers, rows):
    wb=Workbook(); ws=wb.active; ws.title=sheet
    ws.append(headers)
    for row in rows: ws.append(list(row))
    ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
    for col in ws.columns:
        width=min(max(len(str(cell.value or '')) for cell in col)+2, 40)
        ws.column_dimensions[col[0].column_letter].width=width
    out=io.BytesIO(); wb.save(out); out.seek(0)
    return send_file(out, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@exports_bp.route('/students.csv')
@login_required
@roles_required("admin","admission_officer","teacher","staff")
def students_csv():
    q=Student.query
    status=request.args.get("status","").strip(); class_id=request.args.get("class_id","").strip()
    if status: q=q.filter_by(status=status)
    if class_id and class_id.isdigit(): q=q.filter_by(class_id=int(class_id))
    students=q.order_by(Student.id).all()
    return csv_response('students.csv',['Admission No','Name','Father','Class','Status','Phone'],[(s.admission_no,f'{s.first_name} {s.last_name or ""}'.strip(),s.father_name or '',f'{s.class_room.name} - {s.class_room.section}' if s.class_room else '',s.status,s.phone or '') for s in students])

@exports_bp.route('/fees.csv')
@login_required
@roles_required('admin','accountant')
def fees_csv():
    rows=FeeInvoice.query.order_by(FeeInvoice.id).all()
    return csv_response('fee_invoices.csv',['Invoice','Student','Fee Type','Amount','Paid','Balance','Status','Due Date'],[(i.invoice_no,i.student.first_name,i.fee_type,i.amount,i.paid,round(i.amount-i.paid,2),i.status,i.due_date.isoformat() if i.due_date else '') for i in rows])

@exports_bp.route('/employees.csv')
@login_required
@roles_required('admin')
def employees_csv():
    rows=Employee.query.order_by(Employee.id).all()
    return csv_response('employees.csv',['Employee No','Name','Department','Designation','Phone','Basic Salary','Status'],[(e.employee_no,e.name,e.department or '',e.designation or '',e.phone or '',e.basic_salary,e.status) for e in rows])

@exports_bp.route('/students.xlsx')
@login_required
@roles_required("admin","admission_officer","teacher","staff")
def students_xlsx():
    q=Student.query
    status=request.args.get("status","").strip(); class_id=request.args.get("class_id","").strip()
    if status: q=q.filter_by(status=status)
    if class_id and class_id.isdigit(): q=q.filter_by(class_id=int(class_id))
    rows=q.order_by(Student.id).all()
    data=[(s.admission_no,f'{s.first_name} {s.last_name or ""}'.strip(),s.father_name or '',f'{s.class_room.name} - {s.class_room.section}' if s.class_room else '',s.gender or '',s.status,s.phone or '') for s in rows]
    return xlsx_response('students.xlsx','Students',['Admission No','Name','Father','Class','Gender','Status','Phone'],data)

@exports_bp.route('/fees.xlsx')
@login_required
@roles_required('admin','accountant')
def fees_xlsx():
    rows=FeeInvoice.query.order_by(FeeInvoice.id).all()
    data=[(i.invoice_no,i.student.first_name,i.fee_type,i.amount,i.paid,round(i.amount-i.paid,2),i.status,i.due_date.isoformat() if i.due_date else '') for i in rows]
    return xlsx_response('fee_invoices.xlsx','Fees',['Invoice','Student','Fee Type','Amount','Paid','Balance','Status','Due Date'],data)

@exports_bp.route('/employees.xlsx')
@login_required
@roles_required('admin')
def employees_xlsx():
    rows=Employee.query.order_by(Employee.id).all()
    data=[(e.employee_no,e.name,e.department or '',e.designation or '',e.phone or '',e.email or '',e.basic_salary,e.status) for e in rows]
    return xlsx_response('employees.xlsx','Employees',['Employee No','Name','Department','Designation','Phone','Email','Basic Salary','Status'],data)

@exports_bp.route('/receipt/<int:payment_id>')
@login_required
@roles_required('admin','accountant')
def receipt(payment_id):
    payment=FeePayment.query.get_or_404(payment_id)
    return render_template('finance/receipt.html', payment=payment)



def _card_token(student):
    from flask import current_app
    msg=f"{student.id}:{student.admission_no}".encode()
    return base64.urlsafe_b64encode(hmac.new(current_app.config["SECRET_KEY"].encode(), msg, hashlib.sha256).digest()[:18]).decode().rstrip("=")

def _id_card_flowable(student, side, token, styles):
    W,H=85.6*mm,54*mm
    cls=f"{student.class_room.name} - {student.class_room.section}" if student.class_room else "-"
    address="Green School"
    from flask import request
    qr_url=f"{request.url_root.rstrip('/')}/students/verify-card/{student.admission_no}?token={token}"
    if side=='front':
        logo_path=os.path.join(os.path.dirname(__file__), 'static', 'assets', 'green-school-logo.png')
        logo=Image(logo_path,width=13*mm,height=13*mm) if os.path.exists(logo_path) else Paragraph('GS',styles['CardTitle'])
        head=Table([[logo, Paragraph('<b>GREEN SCHOOL</b><br/><font size="6">School Management ERP</font>',styles['CardHead'])]], colWidths=[15*mm, W-15*mm])
        head.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(1,0),(1,0),'CENTER'),('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2)]))
        photo=Image(os.path.join(os.path.dirname(__file__),'static',student.photo_path),width=23*mm,height=28*mm) if student.photo_path and os.path.exists(os.path.join(os.path.dirname(__file__),'static',student.photo_path)) else Paragraph('<b>PHOTO</b>',styles['Photo'])
        details=[[Paragraph(f'<b>{student.first_name} {student.last_name or ""}</b>',styles['CardName'])], [Paragraph(f'<b>Student ID:</b> {student.admission_no}',styles['CardText'])], [Paragraph(f'<b>Class:</b> {cls}',styles['CardText'])], [Paragraph(f'<b>Father/Guardian:</b> {student.father_name or (student.parent.name if student.parent else "-")}',styles['CardText'])], [Paragraph(f'<b>Status:</b> {student.status}',styles['CardText'])]]
        body=Table([[photo,Table(details,colWidths=[W-31*mm])]],colWidths=[27*mm,W-27*mm])
        body.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('BOX',(0,0),(0,0),0.5,colors.grey),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3)]))
        data=[[head],[body],[Paragraph('<font size="5.5">This card identifies the student as enrolled at Green School.</font>',styles['CardText'])]]
    else:
        qrbox=Drawing(27*mm,27*mm); q=qr.QrCodeWidget(qr_url); q.barWidth=0.9*mm; q.barHeight=0.9*mm; q.x=0; q.y=0; qrbox.add(q)
        data=[[Paragraph('<b>STUDENT ID CARD · BACK</b>',styles['CardTitle'])],[qrbox],[Paragraph(f'<b>Verification</b><br/>Scan the QR code to verify this student record.<br/><br/><b>School:</b> Green School<br/><b>Address:</b> {address}<br/><b>Emergency Contact:</b> {student.parent.mobile if student.parent and student.parent.mobile else student.phone or "-"}',styles['CardText'])],[Paragraph('If found, please return this card to the school office.',styles['CardText'])]]
    card=Table(data,colWidths=[W],rowHeights=None)
    card.setStyle(TableStyle([('BOX',(0,0),(-1,-1),1,colors.HexColor('#173b67')),('INNERGRID',(0,0),(-1,-1),0.25,colors.lightgrey),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eef5fb')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
    return card

def _id_card_styles():
    st=getSampleStyleSheet()
    st.add(ParagraphStyle(name='CardHead',parent=st['Normal'],fontSize=8.2,leading=9,alignment=1))
    st.add(ParagraphStyle(name='CardTitle',parent=st['Normal'],fontSize=8,leading=9,alignment=1))
    st.add(ParagraphStyle(name='CardName',parent=st['Normal'],fontSize=8.5,leading=9.5))
    st.add(ParagraphStyle(name='CardText',parent=st['Normal'],fontSize=5.8,leading=7))
    st.add(ParagraphStyle(name='Photo',parent=st['Normal'],fontSize=7,leading=8,alignment=1,textColor=colors.grey))
    return st

@exports_bp.route('/student-id-card/<int:student_id>.pdf')
@login_required
@roles_required('admin', 'admission_officer', 'staff', 'teacher', 'student')
def student_id_card_pdf(student_id):
    if current_user.role == "student" and current_user.student_id != student_id:
        abort(403)
    student = db.get_or_404(Student, student_id)
    token = _card_token(student)
    out=io.BytesIO(); doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=20*mm,leftMargin=20*mm,topMargin=25*mm,bottomMargin=25*mm)
    st=_id_card_styles(); story=[Paragraph('Student ID Card · Front',st['Heading2']),Spacer(1,8),_id_card_flowable(student,'front',token,st),PageBreak(),Paragraph('Student ID Card · Back',st['Heading2']),Spacer(1,8),_id_card_flowable(student,'back',token,st)]
    doc.build(story); out.seek(0); return send_file(out,as_attachment=True,download_name=f'student-id-card-{student.admission_no}.pdf',mimetype='application/pdf')

@exports_bp.route('/report-card/<int:student_id>/<int:exam_id>.pdf')
@login_required
def report_card_pdf(student_id, exam_id):
    from .academics import report_card_records, grade_for
    student, exam, rows = report_card_records(student_id, exam_id)
    if not exam.approved_at:
        abort(403)
    total=sum(r.total or 0 for r in rows); obtained=sum(r.marks or 0 for r in rows); pct=round(obtained/total*100,2) if total else 0
    grade = grade_for(pct)
    out=io.BytesIO(); doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=36,leftMargin=36,topMargin=36,bottomMargin=36)
    styles=getSampleStyleSheet(); story=[Paragraph('GREEN SCHOOL ERP',styles['Title']),Paragraph('Student Report Card',styles['Heading2']),Spacer(1,10)]
    cls=f'{student.class_room.name} - {student.class_room.section}' if student.class_room else '-'
    story += [Paragraph(f'<b>Student:</b> {student.first_name} {student.last_name or ""}',styles['Normal']),Paragraph(f'<b>Admission No:</b> {student.admission_no} &nbsp;&nbsp; <b>Class:</b> {cls}',styles['Normal']),Paragraph(f'<b>Exam:</b> {exam.name}',styles['Normal']),Spacer(1,14)]
    data=[['Subject','Marks','Total','Percentage']]+[[r.subject.name,r.marks,r.total, f'{round((r.marks/r.total)*100,2) if r.total else 0}%'] for r in rows]
    table=Table(data,repeatRows=1); table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1f6feb')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.5,colors.grey),('PADDING',(0,0),(-1,-1),6)])); story += [table,Spacer(1,12),Paragraph(f'<b>Total:</b> {obtained} / {total} &nbsp;&nbsp; <b>Percentage:</b> {pct}% &nbsp;&nbsp; <b>Grade:</b> {grade}',styles['Heading3'])]
    doc.build(story); out.seek(0)
    return send_file(out,as_attachment=True,download_name=f'report-card-{student.admission_no}-{exam.id}.pdf',mimetype='application/pdf')

def _voucher_token(invoice):
    """Create a tamper-resistant public verification token for a fee voucher."""
    from flask import current_app
    msg=f"{invoice.id}:{invoice.invoice_no}:{float(invoice.amount or 0):.2f}".encode()
    return base64.urlsafe_b64encode(
        hmac.new(current_app.config["SECRET_KEY"].encode(), msg, hashlib.sha256).digest()[:18]
    ).decode().rstrip("=")

def _voucher_flowables(invoice, styles, items, continuation=False, final=True):
    """Build the three-copy A4 voucher with a real school logo and scannable QR.

    A fresh logo Image and QR Drawing are created for every copy because ReportLab
    flowables are stateful and should not be reused across table cells.
    """
    student = invoice.student
    cls = f'{student.class_room.name} - {student.class_room.section}' if student.class_room else '-'
    from flask import url_for

    verify_url = url_for('exports.verify_voucher', invoice_no=invoice.invoice_no,
                         token=_voucher_token(invoice), _external=True)
    due_date = invoice.due_date.strftime("%d %b %Y") if invoice.due_date else "As per schedule"
    ink = colors.HexColor('#155b49')
    tint = colors.HexColor('#edf5ef')
    border = colors.HexColor('#b5c9be')
    logo_path = os.path.join(os.path.dirname(__file__), 'static', 'assets', 'green-school-logo.png')

    def make_logo():
        # Use a fresh ReportLab Image per voucher copy. The previous implementation
        # could silently omit the image on some ReportLab builds when the flowable
        # was nested deeply inside the 3-column voucher table.
        if os.path.isfile(logo_path):
            return Image(logo_path, width=13 * mm, height=13 * mm, kind='proportional')
        return Paragraph('<b>GS</b>', styles['VoucherSchool'])

    def make_qr():
        size = 16 * mm
        widget = qr.QrCodeWidget(verify_url, barWidth=size, barHeight=size)
        drawing = Drawing(size, size)
        drawing.add(widget)
        return drawing

    cells = []
    for copy_name in ['STUDENT COPY', 'BANK COPY', 'SCHOOL COPY']:
        label = Table([[Paragraph(f'<b>{copy_name}</b>', styles['VoucherCopy'])]], colWidths=[168])
        label.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), ink),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        parts = [label, Spacer(1, 5)]

        # Fresh flowables for every copy: logo and QR are therefore rendered
        # independently in all three columns.
        header = Table([
            [
                make_logo(),
                Paragraph(
                    '<b>Green School</b><br/>'
                    '<font size="6">School Management ERP</font>',
                    styles['VoucherSchool']
                ),
                make_qr(),
            ]
        ], colWidths=[39, 81, 48])
        header.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('ALIGN', (2, 0), (2, 0), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        parts.append(header)
        reference = Table([[Paragraph(
            f'Voucher No. <b>{escape(invoice.invoice_no)}</b><br/>Due date <b>{due_date}</b>'
            + ('<br/>Continuation' if continuation else ''),
            styles['VoucherTiny']
        )]], colWidths=[168])
        reference.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), tint)]))
        parts.extend([reference, Spacer(1, 5)])

        info = [
            [
                Paragraph('<b>Student</b><br/>' + escape(f'{student.first_name} {student.last_name or ""}'), styles['VoucherTiny']),
                Paragraph('<b>Code</b><br/>' + escape(student.admission_no), styles['VoucherTiny'])
            ],
            [
                Paragraph('<b>Father / Guardian</b><br/>' + escape(student.father_name or (student.parent.name if student.parent else '-')), styles['VoucherTiny']),
                Paragraph('<b>Class</b><br/>' + escape(cls), styles['VoucherTiny'])
            ]
        ]
        it = Table(info, colWidths=[84, 84])
        it.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.35, border),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        parts.extend([it, Spacer(1, 6)])

        data = [[
            Paragraph('<b>Fee Item</b>', styles['VoucherTiny']),
            Paragraph('<b>PKR</b>', styles['VoucherAmount'])
        ]]
        for item in items:
            data.append([
                Paragraph(escape(str(item.description)), styles['VoucherTiny']),
                Paragraph(f'{float(item.amount):,.2f}', styles['VoucherAmount'])
            ])
        if final and invoice.paid:
            data.append([
                Paragraph('Already paid', styles['VoucherTiny']),
                Paragraph(f'{invoice.paid:,.2f}', styles['VoucherAmount']),
            ])
        data.append([
            Paragraph('<b>Total Payable</b>' if final else '<b>Continued on the next page</b>', styles['VoucherTiny']),
            Paragraph(f'<b>{float(invoice.amount - invoice.paid):,.2f}</b>' if final else '', styles['VoucherAmount'])
        ])
        amt = Table(data, colWidths=[118, 50])
        amt.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.35, border),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('BACKGROUND', (0, 0), (-1, 0), tint),
            ('BACKGROUND', (0, -1), (-1, -1), tint),
        ]))
        parts.append(amt)
        parts.extend([
            Paragraph('Computer-generated voucher. Scan QR to verify.', styles['VoucherTiny']),
        ])
        if final:
            parts.extend([Spacer(1, 22),
                          Paragraph('Cashier / Bank signature __________________', styles['VoucherTiny'])])
        # ReportLab Table cells accept a list of flowables. KeepTogether is
        # a container flowable and cannot be drawn directly inside a Table cell
        # on some ReportLab versions, causing: "KeepTogether object has no
        # attribute draw". Keep the flowables as a native cell list instead.
        cells.append(parts)

    outer = Table([cells], colWidths=[180, 180, 180])
    outer.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, border),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, border),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return outer

def _voucher_styles():
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='VoucherCopy', parent=styles['Normal'], fontSize=8, leading=10, alignment=1, textColor=colors.white))
    styles.add(ParagraphStyle(name='VoucherSchool', parent=styles['Normal'], fontSize=9, leading=10, alignment=1, textColor=colors.HexColor('#155b49')))
    styles.add(ParagraphStyle(name='VoucherTiny', parent=styles['Normal'], fontSize=7.2, leading=8.2, spaceAfter=2))
    styles.add(ParagraphStyle(name='VoucherAmount', parent=styles['VoucherTiny'], alignment=2))
    return styles

@exports_bp.route('/voucher/<int:invoice_id>.pdf')
@login_required
@roles_required('admin','accountant','admission_officer')
def voucher_pdf(invoice_id):
    invoice = db.get_or_404(FeeInvoice, invoice_id)
    return build_bulk_voucher_pdf([invoice], filename=f'fee-voucher-{invoice.invoice_no}.pdf')


@exports_bp.route('/verify-voucher/<invoice_no>')
def verify_voucher(invoice_no):
    token=request.args.get('token','')
    invoice=FeeInvoice.query.filter_by(invoice_no=invoice_no).first()
    if not invoice or not hmac.compare_digest(token, _voucher_token(invoice)):
        return Response('Invalid or expired voucher verification link.', status=404, mimetype='text/plain')
    return render_template('finance/voucher_verify.html', invoice=invoice)

def build_bulk_voucher_pdf(invoices, filename=None):
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=17, leftMargin=17, topMargin=17, bottomMargin=17)
    styles = _voucher_styles()
    story = []
    for invoice in invoices:
        items = list(invoice.items) or [SimpleNamespace(description=invoice.fee_type, amount=invoice.amount)]
        offset = 0
        while offset < len(items):
            count = len(items) - offset
            while True:
                final = offset + count == len(items)
                sheet = _voucher_flowables(invoice, styles, items[offset:offset + count],
                                           continuation=offset > 0, final=final)
                if sheet.wrap(doc.width - 12, doc.height - 12)[1] <= doc.height - 12 or count == 1:
                    break
                count //= 2
            if story:
                story.append(PageBreak())
            story.append(sheet)
            offset += count
    doc.build(story)
    out.seek(0)
    return send_file(out, as_attachment=True, download_name=filename or f'bulk-fee-vouchers-{len(invoices)}.pdf',
                     mimetype='application/pdf')


@exports_bp.route('/bulk-vouchers.pdf')
@login_required
@roles_required('admin','accountant','admission_officer')
def bulk_voucher_pdf():
    raw=request.args.get('invoice_ids','').strip()
    ids=[int(x) for x in raw.split(',') if x.isdigit()]
    if not ids:
        return Response('No vouchers selected.', status=400, mimetype='text/plain')
    invoices=FeeInvoice.query.options(joinedload(FeeInvoice.student).joinedload(Student.class_room), joinedload(FeeInvoice.student).joinedload(Student.parent), selectinload(FeeInvoice.items)).filter(FeeInvoice.id.in_(ids)).order_by(FeeInvoice.id).all()
    if not invoices:
        return Response('No vouchers found.', status=404, mimetype='text/plain')
    return build_bulk_voucher_pdf(invoices)
