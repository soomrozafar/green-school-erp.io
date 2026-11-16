import csv
from datetime import date
from io import BytesIO

from flask import Blueprint, Response, abort, render_template, request, send_file, stream_with_context
from flask_login import current_user, login_required
from openpyxl import Workbook
from sqlalchemy import String, cast, func, or_

from . import models as m
from .access import teacher_profile
from .extensions import db
from .report_catalogue import REPORTS

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def available_reports():
    return {key: spec for key, spec in REPORTS.items()
            if current_user.role == "admin" or current_user.role in spec.roles}


def report_query(key, spec, include_bucket=True):
    query = db.session.query(spec.model.id).select_from(spec.model)
    for relationship in spec.joins:
        if isinstance(relationship, tuple):
            query = query.outerjoin(*relationship)
        else:
            query = query.outerjoin(relationship)
    if key == "results":
        query = query.filter(m.Exam.approved_at.is_not(None))
    if current_user.role == "teacher":
        teacher = teacher_profile(current_user)
        if not teacher:
            query = query.filter(db.false())
        elif key == "timetable":
            query = query.filter(m.Timetable.teacher_id == teacher.id)
        else:
            classes = db.select(m.Timetable.class_id).where(m.Timetable.teacher_id == teacher.id)
            query = query.filter(m.Student.class_id.in_(classes))
    if spec.student_scope:
        class_id = request.args.get("class_id", type=int)
        session_id = request.args.get("session_id", type=int)
        if class_id is not None:
            query = query.filter(m.Student.class_id == class_id)
        if session_id is not None:
            query = query.filter(m.ClassRoom.session_id == session_id)
    term = request.args.get("q", "").strip()[:80]
    if term:
        query = query.filter(or_(*(cast(column, String).icontains(term, autoescape=True)
                                   for _, column in spec.columns)))
    bucket = request.args.get("status", "").strip()[:100]
    if include_bucket and bucket and spec.bucket is not None:
        query = query.filter(cast(spec.bucket, String) == bucket)
    if spec.date_field is not None:
        start = request.args.get("start")
        end = request.args.get("end")
        try:
            start = date.fromisoformat(start) if start else None
            end = date.fromisoformat(end) if end else None
        except ValueError:
            abort(400, description="Enter valid report dates.")
        if start and end and start > end:
            abort(400, description="The start date must be on or before the end date.")
        if start:
            query = query.filter(spec.date_field >= start)
        if end:
            if str(spec.date_field.type) == "DATE":
                query = query.filter(spec.date_field <= end)
            else:
                query = query.filter(func.date(spec.date_field) <= end)
    return query


@reports_bp.get("/")
@login_required
def index():
    reports = available_reports()
    if not reports:
        abort(403)
    if any(request.args.get(key) for key in ("class_id", "session_id", "status")) and "students" in reports:
        return detail("students")
    groups = dict.fromkeys(spec.group for spec in reports.values())
    return render_template("reports.html", groups=groups, reports=reports)


@reports_bp.get("/<key>")
@login_required
def detail(key):
    spec = available_reports().get(key)
    if spec is None:
        abort(403 if key in REPORTS else 404)
    query = report_query(key, spec)
    rows = query.with_entities(*(column for _, column in spec.columns)).order_by(spec.model.id.desc())
    headers = [label for label, _ in spec.columns]
    output = request.args.get("format")
    if output == "csv":
        return download(key, output, headers, rows)

    count, *totals = query.with_entities(
        func.count(spec.model.id), *(func.coalesce(func.sum(column), 0) for _, column in spec.totals)
    ).one()
    breakdown = []
    choices = []
    if spec.bucket is not None:
        breakdown = query.with_entities(spec.bucket, func.count(spec.model.id)).group_by(
            spec.bucket
        ).order_by(func.count(spec.model.id).desc(), spec.bucket).limit(12).all()
    metrics = list(zip((label for label, _ in spec.totals), totals))
    if count and key in ("student-attendance", "teacher-attendance"):
        present = query.filter(func.lower(spec.bucket).in_(("present", "late", "p"))).count()
        metrics.append(("Present or late (%)", round(present / count * 100, 1)))
    if count and key == "results":
        earned, maximum = query.with_entities(func.sum(m.Result.marks), func.sum(m.Result.total)).one()
        if maximum:
            metrics.append(("Overall marks (%)", round((earned or 0) / maximum * 100, 2)))
    summary = [("Matching rows", count), *metrics]
    if output == "xlsx":
        return download(key, output, headers, rows, summary, breakdown)
    if spec.bucket is not None:
        choices = [str(value) for (value,) in report_query(key, spec, include_bucket=False).with_entities(spec.bucket).distinct()
                   .order_by(spec.bucket).limit(100) if value not in (None, "")]
    page = max(request.args.get("page", 1, type=int), 1)
    pages = max((count + 49) // 50, 1)
    page = min(page, pages)
    return render_template("report_detail.html", key=key, report=spec, headers=headers,
                           rows=rows.offset((page - 1) * 50).limit(50).all(),
                           page=page, pages=pages, count=count,
                           totals=metrics, breakdown=breakdown, choices=choices,
                           classes=m.ClassRoom.query.order_by(m.ClassRoom.name, m.ClassRoom.section).all() if spec.student_scope else [],
                           sessions=m.AcademicSession.query.order_by(m.AcademicSession.id.desc()).all() if spec.student_scope else [],
                           filters={key: request.args[key] for key in ("q", "status", "start", "end", "class_id", "session_id")
                                    if request.args.get(key)})


def spreadsheet_value(value):
    # Keep user-entered strings from being interpreted as spreadsheet formulas.
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


class CSVBuffer:
    def write(self, value):
        return value


def download(key, output, headers, rows, summary=(), breakdown=()):
    if output == "csv":
        def stream():
            writer = csv.writer(CSVBuffer())
            yield "\ufeff" + writer.writerow(headers)
            for row in rows.yield_per(500):
                yield writer.writerow(map(spreadsheet_value, row))
        return Response(stream_with_context(stream()), content_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{key}.csv"'})
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Report")
    analysis = workbook.create_sheet("Analysis")
    analysis.append(("Metric", "Value"))
    for row in summary:
        analysis.append(row)
    if breakdown:
        analysis.append(("Group", "Rows"))
        for label, total in breakdown:
            analysis.append((spreadsheet_value(label) if label else "Unspecified", total))
    sheet.freeze_panes = "A2"
    sheet.append(headers)
    for row in rows.yield_per(500):
        sheet.append([spreadsheet_value(value) for value in row])
    data = BytesIO()
    workbook.save(data)
    data.seek(0)
    return send_file(data, as_attachment=True, download_name=f"{key}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

