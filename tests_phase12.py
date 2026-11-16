def test_phase12_files_exist():
    from pathlib import Path
    required = [
        Path("app/production.py"), Path("app/templates/admin/audit.html"),
        Path("app/templates/admin/login_history.html"), Path("app/templates/admin/integrity.html"),
        Path("app/templates/admin/backups.html")
    ]
    assert all(p.exists() for p in required)
