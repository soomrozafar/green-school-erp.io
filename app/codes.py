from datetime import date
from .extensions import db
from .models import SequenceCounter

def next_code(code_type, prefix, width=5):
    """Generate sequential human-readable codes. PostgreSQL row locking is used when available."""
    q = SequenceCounter.query.filter_by(code_type=code_type)
    counter = q.with_for_update().first()
    if not counter:
        counter = SequenceCounter(code_type=code_type, current_value=0)
        db.session.add(counter)
        db.session.flush()
    counter.current_value += 1
    return f"{prefix}-{date.today().year}-{counter.current_value:0{width}d}"
