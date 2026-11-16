from sqlalchemy import inspect, text
from .extensions import db

COLUMNS = {
    'parent': {
        'mobile': 'VARCHAR(40)', 'cnic': 'VARCHAR(30)', 'latitude': 'DOUBLE PRECISION', 'longitude': 'DOUBLE PRECISION'
    },
    'student': {'latitude': 'DOUBLE PRECISION', 'longitude': 'DOUBLE PRECISION', 'photo_path': 'VARCHAR(255)'},
    'user': {'student_id': 'INTEGER', 'parent_id': 'INTEGER REFERENCES parent(id)', 'teacher_id': 'INTEGER REFERENCES teacher(id)'},
    'exam': {'approved_at': 'TIMESTAMP', 'approved_by_id': 'INTEGER'},
    'library_issue': {'due_date': 'DATE'},
    'transport_route': {'map_points': 'TEXT'},
    'fee_invoice_item': {'fee_month': 'DATE'},
    'employee': {'employee_type':'VARCHAR(30)','gender':'VARCHAR(20)','dob':'DATE','father_name':'VARCHAR(150)','cnic':'VARCHAR(30)','address':'TEXT','qualification':'VARCHAR(200)','experience_years':'REAL','bank_name':'VARCHAR(120)','bank_account':'VARCHAR(80)','iban':'VARCHAR(80)','emergency_contact_name':'VARCHAR(150)','emergency_contact_phone':'VARCHAR(40)','photo_path':'VARCHAR(255)'},
    'teacher': {'employee_id':'INTEGER','status':'VARCHAR(30)'},
    'payroll': {'housing_allowance':'REAL','transport_allowance':'REAL','medical_allowance':'REAL','other_allowances':'REAL','overtime':'REAL','bonus':'REAL','absent_deduction':'REAL','loan_deduction':'REAL','advance_deduction':'REAL','tax_deduction':'REAL','provident_fund':'REAL','other_deductions':'REAL','gross_salary':'REAL','payment_method':'VARCHAR(30)','payment_reference':'VARCHAR(120)','remarks':'TEXT'},
}

def ensure_columns():
    """Small additive compatibility migration for Phase 17. Safe for fresh and existing DBs."""
    engine=db.engine
    insp=inspect(engine)
    for table, cols in COLUMNS.items():
        if table not in insp.get_table_names():
            continue
        existing={c['name'] for c in insp.get_columns(table)}
        for col, typ in cols.items():
            if col in existing: continue
            # SQLite does not accept PostgreSQL DOUBLE PRECISION; REAL is portable.
            sql_type='REAL' if engine.dialect.name=='sqlite' and 'DOUBLE' in typ else typ
            with engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {sql_type}'))

    if "login_event" in insp.get_table_names():
        with engine.begin() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_login_event_recent ON login_event (event, created_at)"))

    # Convert legacy Teacher rows into the Employee master without deleting history.
    if 'teacher' in insp.get_table_names() and 'employee' in insp.get_table_names():
        teacher_cols={c['name'] for c in inspect(engine).get_columns('teacher')}
        legacy_cols={'employee_no','name','subject','phone','email','designation'}
        # Fresh Phase 29 databases no longer contain the legacy teacher fields.
        # Only run the legacy conversion when those old columns actually exist.
        if not legacy_cols.issubset(teacher_cols):
            return
        with engine.begin() as conn:
            rows=conn.execute(text("SELECT id, employee_no, name, subject, phone, email, designation, status FROM teacher WHERE employee_id IS NULL")).mappings().all()
            for r in rows:
                emp=conn.execute(text("SELECT id FROM employee WHERE employee_no=:no"), {'no':r['employee_no']}).first()
                if emp: emp_id=emp[0]
                else:
                    conn.execute(text("INSERT INTO employee (employee_no,name,employee_type,phone,email,designation,status,basic_salary) VALUES (:no,:name,'Teacher',:phone,:email,:designation,:status,0)"), {'no':r['employee_no'],'name':r['name'],'phone':r['phone'],'email':r['email'],'designation':r['designation'],'status':r['status'] or 'Active'})
                    emp_id=conn.execute(text("SELECT id FROM employee WHERE employee_no=:no"), {'no':r['employee_no']}).scalar_one()
                conn.execute(text("UPDATE teacher SET employee_id=:eid WHERE id=:tid"), {'eid':emp_id,'tid':r['id']})
                # Preserve the old single subject as a subject assignment where possible.
                if r['subject']:
                    sub=conn.execute(text("SELECT id FROM subject WHERE lower(name)=lower(:name) LIMIT 1"), {'name':r['subject']}).first()
                    if sub:
                        exists=conn.execute(text("SELECT 1 FROM teacher_subject WHERE teacher_id=:tid AND subject_id=:sid LIMIT 1"), {'tid':r['id'],'sid':sub[0]}).first()
                        if not exists:
                            conn.execute(text("INSERT INTO teacher_subject (teacher_id,subject_id) VALUES (:tid,:sid)"), {'tid':r['id'],'sid':sub[0]})
