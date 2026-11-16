import os
from datetime import datetime, timedelta, timezone
from math import asin, cos, isfinite, radians, sin, sqrt

from .access import teacher_profile
from .extensions import db
from .models import Teacher, TeacherAttendance


def campus():
    settings = [os.environ.get(f"SCHOOL_ERP_CAMPUS_{key}") for key in ("LAT", "LON", "RADIUS_M")]
    if not any(settings):
        return None
    lat, lon, radius = map(float, settings)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 < radius <= 5000):
        raise ValueError("Invalid campus coordinates or radius.")
    return lat, lon, radius


def check_in(user, form):
    try:
        fence = campus()
    except (TypeError, ValueError):
        return "School location is misconfigured. Contact the school office."
    if fence is None:
        return None
    teacher = teacher_profile(user)
    if teacher is None:
        return "Contact the school office to link your active teacher profile."
    try:
        lat, lon, accuracy = (float(form[key]) for key in ("latitude", "longitude", "accuracy"))
    except (KeyError, ValueError):
        return "Use Share campus location and sign in again."
    if not (-90 <= lat <= 90 and -180 <= lon <= 180 and isfinite(accuracy) and 0 < accuracy <= 100):
        return "A more accurate location is required. Enable precise location and try again."
    center_lat, center_lon, radius = fence
    distance = 12_742_000 * asin(min(1, sqrt(
        sin(radians(lat - center_lat) / 2) ** 2
        + cos(radians(lat)) * cos(radians(center_lat)) * sin(radians(lon - center_lon) / 2) ** 2
    )))
    if distance + accuracy > radius:
        return "Could not verify you are inside the school premises. Move inside and try again."
    today = datetime.now(timezone(timedelta(hours=5))).date()
    # Serialize sign-ins for this teacher and preserve manually recorded status.
    Teacher.query.filter_by(id=teacher.id).update({Teacher.status: Teacher.status}, synchronize_session=False)
    if not TeacherAttendance.query.filter_by(teacher_id=teacher.id, date=today).first():
        db.session.add(TeacherAttendance(teacher_id=teacher.id, date=today, status="Present", recorded_by=user.id))
    return None
