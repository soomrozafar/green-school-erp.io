"""Phase 17 regression tests. Run after installing requirements in a test environment."""
import pytest

@pytest.mark.phase17
def test_phase17_documentation_present():
    from pathlib import Path
    root=Path(__file__).parent
    assert (root/'PHASE17_QA_CHECKLIST.md').exists()
    assert (root/'PHASE17_REQUIREMENTS.md').exists()
