from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from .access import roles_required
from .extensions import db
from .models import AuditLog, ClassRoom, Subject, Teacher, Timetable
from . import timetable_sources as sources

timetable_bp = Blueprint("timetable", __name__, url_prefix="/timetable")
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
SCHEDULE_ROLES = {"admin", "staff"}


def catalogue():
    return (
        ClassRoom.query.order_by(ClassRoom.name, ClassRoom.section).all(),
        Subject.query.order_by(Subject.name).all(),
        Teacher.query.options(joinedload(Teacher.employee)).filter_by(status="Active").all(),
    )


def resolve(value, records, labels, field):
    key = sources.normalized(value)
    matches = [item for item in records if key and key in {sources.normalized(x) for x in labels(item)}]
    if len(matches) != 1:
        raise ValueError(f"{field} '{value}' must match one existing record. Use its ID or exact name/code.")
    return matches[0]


def normalize_row(row, choices):
    classes, subjects, teachers = choices
    class_room = resolve(row["class"], classes,
                         lambda c: (c.id, c.name, f"{c.name} {c.section}"), "Class")
    subject = resolve(row["subject"], subjects, lambda s: (s.id, s.name, s.code or ""), "Subject")
    teacher = resolve(row["teacher"], teachers,
                      lambda t: (t.id, t.employee.name, t.employee.employee_no) if t.employee else (),
                      "Teacher")
    day = next((d for d in DAYS if row["day"].strip().lower() in {d.lower(), d[:3].lower()}), None)
    if day is None:
        raise ValueError("Choose a weekday such as Monday.")
    start, end = sources.parse_time(row["start"]), sources.parse_time(row["end"])
    if start >= end:
        raise ValueError("End time must be after start time.")
    room = row["room"].strip()
    if len(room) > 50:
        raise ValueError("Room must be 50 characters or fewer.")
    return dict(day=day, class_id=class_room.id, subject_id=subject.id, teacher_id=teacher.id,
                start_time=start, end_time=end, room=room)


def schedule_fields(item):
    values = {field: getattr(item, field) for field in (
        "day", "class_id", "subject_id", "teacher_id", "start_time", "end_time", "room",
    )}
    values["room"] = values["room"] or ""
    return values


def check_conflicts(row, occupied):
    for existing in occupied:
        if existing == row:
            return "Already scheduled"
        if (existing["day"].casefold() != row["day"].casefold()
                or sources.parse_time(existing["end_time"]) <= row["start_time"]
                or sources.parse_time(existing["start_time"]) >= row["end_time"]):
            continue
        for field, label in (("class_id", "class"), ("teacher_id", "teacher"), ("room", "room")):
            left = sources.normalized(row[field])
            right = sources.normalized(existing[field])
            if field == "room":
                left, right = left.removeprefix("room "), right.removeprefix("room ")
            if left and left == right:
                return f"Overlapping {label} assignment"
    return None


def review_rows(rows, choices):
    classes, subjects, teachers = ({item.id: item for item in group} for group in choices)
    occupied = [schedule_fields(slot) for slot in Timetable.query.all()]
    reviewed, errors = [], []
    for index, row in enumerate(rows, 1):
        try:
            record = normalize_row(row, choices)
            issue = check_conflicts(record, occupied)
            if issue and issue != "Already scheduled":
                raise ValueError(issue)
            if not issue:
                occupied.append(record)
            c, s, t = classes[record["class_id"]], subjects[record["subject_id"]], teachers[record["teacher_id"]]
            reviewed.append(dict(record, class_name=f"{c.name} - {c.section}", subject_name=s.name,
                                 teacher_name=t.employee.name, duplicate=bool(issue), allocation=s not in t.subjects))
        except ValueError as error:
            errors.append(f"Row {index}: {error}")
    return reviewed, errors


def _lock_schedule():
    # All timetable writes use the same existing class row as a transaction lock.
    first_id = db.session.query(db.func.min(ClassRoom.id)).scalar_subquery()
    ClassRoom.query.filter(ClassRoom.id == first_id).update({ClassRoom.capacity: ClassRoom.capacity},
                                                         synchronize_session=False)


def save_rows(reviewed, choices, allocate):
    teachers = {item.id: item for item in choices[2]}
    subjects = {item.id: item for item in choices[1]}
    written = 0
    for row in reviewed:
        if not row["duplicate"]:
            db.session.add(Timetable(**{key: row[key] for key in (
                "day", "class_id", "subject_id", "teacher_id", "start_time", "end_time", "room",
            )}))
            written += 1
        if allocate and subjects[row["subject_id"]] not in teachers[row["teacher_id"]].subjects:
            teachers[row["teacher_id"]].subjects.append(subjects[row["subject_id"]])
    return written


def draft_serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="erp-timetable-review")


@timetable_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        if current_user.role not in SCHEDULE_ROLES:
            abort(403)
        try:
            _lock_schedule()
            choices = catalogue()
            form = request.form
            row = {"day": form.get("day", ""), "class": form.get("class_id", ""),
                   "subject": form.get("subject_id", ""), "teacher": form.get("teacher_id", ""),
                   "start": form.get("start_time", ""), "end": form.get("end_time", ""), "room": form.get("room", "")}
            reviewed, errors = review_rows([row], choices)
            if errors:
                raise ValueError(errors[0])
            count = save_rows(reviewed, choices, allocate=False)
            db.session.commit()
            flash("Timetable entry saved." if count else "This entry is already scheduled.", "success")
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "warning")
        return redirect(url_for("timetable.index"), code=303)
    classes, subjects, teachers = catalogue()
    slots = Timetable.query.options(joinedload(Timetable.class_room), joinedload(Timetable.subject),
                                    joinedload(Timetable.teacher).joinedload(Teacher.employee)).all()
    slots.sort(key=lambda slot: (DAYS.index(slot.day) if slot.day in DAYS else len(DAYS), slot.start_time))
    return render_template("timetable.html", timetable=slots, classes=classes, subjects=subjects,
                           teachers=teachers, days=DAYS, can_manage=current_user.role in SCHEDULE_ROLES)


@timetable_bp.route("/import", methods=["GET", "POST"])
@login_required
@roles_required("admin", "staff")
def import_schedule():
    text = request.form.get("timetable_text", "").strip()
    reviewed, errors, token = [], [], None
    if request.method == "POST":
        try:
            if request.form.get("action") == "save":
                draft = draft_serializer().loads(request.form.get("draft", ""), max_age=1800)
                if draft["user"] != current_user.id:
                    abort(403)
                text = draft["text"]
                _lock_schedule()
                choices = catalogue()
                reviewed, errors = review_rows(sources.table_rows(text), choices)
                if not errors:
                    count = save_rows(reviewed, choices, allocate=request.form.get("allocate") == "1")
                    db.session.add(AuditLog(user_id=current_user.id, action="Import timetable", module="Academics",
                                          details=f"{count} timetable entries added"))
                    db.session.commit()
                    flash(f"{count} timetable entries added.", "success")
                    return redirect(url_for("timetable.index"), code=303)
                db.session.rollback()
            else:
                upload = request.files.get("source_file")
                if upload and upload.filename:
                    if text:
                        raise ValueError("Choose either pasted text or a file for this draft.")
                    text = sources.read_source(upload).strip()
                try:
                    rows = sources.table_rows(text)
                except ValueError:
                    if not text:
                        raise
                    ai_text = sources.draft_with_ai(text)
                    if not ai_text:
                        raise
                    rows = sources.table_rows(ai_text)
                    text = ai_text
                    flash("AI extracted these entries. Compare them with your source before saving.", "info")
                reviewed, errors = review_rows(rows, catalogue())
                if not errors:
                    token = draft_serializer().dumps({"user": current_user.id, "text": text})
        except ValueError as error:
            errors = [str(error)]
        except BadSignature:
            errors = ["The preview expired. Review the draft again before saving."]
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Timetable import failed")
            errors = ["Could not save the timetable. Review the draft and try again."]
    return render_template("timetable_import.html", text=text[:sources.MAX_TEXT],
                           reviewed=reviewed, errors=errors, token=token)
