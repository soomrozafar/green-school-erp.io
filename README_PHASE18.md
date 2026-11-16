# Public School Gadap ERP — Phase 18

Phase 18 hardens the admission/family workflow and makes the system test-ready. It adds non-empty guardian matching, guardian contact validation, a dedicated family profile route, filter-preserving student exports, stronger browser cache controls, safer sequence initialization and expanded QA documentation.

## Windows local setup
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
$env:SCHOOL_ERP_SECRET_KEY="replace-with-a-long-random-secret"
$env:SCHOOL_ERP_SECURE_COOKIES="0"
python run.py
```

## Run QA
```powershell
pytest -q
```

The build environment used to package this release did not have network access for installing Flask dependencies, so live pytest execution is not represented as passed here. Source compilation and ZIP integrity were validated.
