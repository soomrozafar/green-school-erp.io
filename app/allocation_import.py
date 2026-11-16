import csv
from io import StringIO

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from .extensions import db
from .academics import ensure_teacher
from .models import AuditLog, Employee, Subject, Teacher
from .timetable import _lock_schedule, resolve
from . import timetable_sources as sources


def parse(text):
    if not text or len(text) > sources.MAX_TEXT:
        raise ValueError("Provide subject allocation rows within the import size limit.")
    delimiter = "\t" if "\t" in text.splitlines()[0] else ","
    rows = [row for row in csv.reader(StringIO(text), delimiter=delimiter) if any(cell.strip() for cell in row)]
    if rows and [value.strip().lower() for value in rows[0]] == ["teacher", "subject"]:
        rows.pop(0)
    if not rows or len(rows) > sources.MAX_ROWS or any(len(row) != 2 or not all(cell.strip() for cell in row) for row in rows):
        raise ValueError("Use two columns, Teacher and Subject, with one assignment per row and up to 150 rows.")
    return rows


def match(rows):
    employees = Employee.query.filter_by(employee_type="Teacher", status="Active").options(
        joinedload(Employee.teacher).selectinload(Teacher.subjects)
    ).all()
    teachers = [item for item in employees if item.teacher is None or item.teacher.status == "Active"]
    subjects = Subject.query.all()
    reviewed, errors, seen = [], [], set()
    for index, (teacher_name, subject_name) in enumerate(rows, 1):
        try:
            employee = resolve(teacher_name, teachers, lambda item: (item.employee_no, item.name), "Teacher")
            subject = resolve(subject_name, subjects, lambda item: (item.code or "", item.name), "Subject")
            pair = (employee.id, subject.id)
            if pair not in seen:
                reviewed.append((employee, subject, bool(employee.teacher and subject in employee.teacher.subjects)))
                seen.add(pair)
        except ValueError as error:
            errors.append(f"Row {index} · {error}")
    return reviewed, errors


def handle_import():
    signer = URLSafeTimedSerializer(current_app.secret_key, salt="teacher-subject-import")
    text = request.form.get("allocation_text", "").strip()
    reviewed, errors, token = [], [], None
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "save":
                draft = signer.loads(request.form.get("draft", ""), max_age=1800)
                if draft["user"] != current_user.id:
                    abort(403)
                text = draft["text"]
                _lock_schedule()
            else:
                upload = request.files.get("source_file")
                if upload and upload.filename:
                    if text:
                        raise ValueError("Choose a file or paste text.")
                    text = sources.read_source(upload).strip()
                if action == "ai":
                    text = sources.extract_rows(text, ("teacher", "subject"),
                                                "Extract only explicitly stated teacher and subject pairs. "
                                                "Preserve names and codes verbatim. Never invent a pair.") or ""
                    if not text:
                        raise ValueError("Ollama could not create a draft. Use the CSV or Excel format shown below.")
            reviewed, errors = match(parse(text))
            if action == "save" and not errors:
                expected = [tuple(item) for item in draft["pairs"]]
                if expected != [(employee.id, subject.id) for employee, subject, _ in reviewed]:
                    raise ValueError("Teacher or subject matching changed. Preview the import again.")
                count = 0
                for employee, subject, exists in reviewed:
                    if not exists:
                        teacher = ensure_teacher(employee, [subject])
                        teacher.subjects.append(subject)
                        count += 1
                if count:
                    db.session.add(AuditLog(user_id=current_user.id, action="Import subject assignments", module="Academics",
                                            details=f"{count} assignments added"))
                db.session.commit()
                flash(f"{count} subject assignments added.", "success")
                return redirect(url_for("academics.teachers"), code=303)
            if not errors:
                token = signer.dumps({"user": current_user.id, "text": text,
                                      "pairs": [(employee.id, subject.id) for employee, subject, _ in reviewed]})
            elif action == "save":
                db.session.rollback()
        except BadSignature:
            errors = ["This preview expired. Generate a new preview."]
        except ValueError as error:
            db.session.rollback()
            errors = [str(error)]
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Teacher subject import failed")
            errors = ["Could not save the assignments. Generate a new preview and try again."]
    return render_template("academics/allocation_import.html", text=text[:sources.MAX_TEXT],
                           reviewed=reviewed, errors=errors, token=token)
