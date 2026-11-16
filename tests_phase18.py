"""Phase 18 regression tests. Install requirements first, then run pytest."""
from pathlib import Path
import pytest

@pytest.mark.phase18
def test_phase18_artifacts_present():
    root=Path(__file__).parent
    for name in ["PHASE18_QA_CHECKLIST.md","PHASE18_REQUIREMENTS.md","README_PHASE18.md"]:
        assert (root/name).exists()

@pytest.mark.phase18
def test_production_uses_postgres_template():
    text=(Path(__file__).parent/".env.production.example").read_text()
    assert "postgresql+psycopg://" in text
    assert "SCHOOL_ERP_AUTO_CREATE_DB=0" in text

@pytest.mark.phase18
def test_family_route_and_filtered_exports_are_in_source():
    students=(Path(__file__).parent/"app/students.py").read_text()
    exports=(Path(__file__).parent/"app/exports.py").read_text()
    assert '/family/<int:parent_id>' in students
    assert 'request.args.get("status"' in exports
