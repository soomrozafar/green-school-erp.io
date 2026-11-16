"""Start a disposable public demo using a fresh synthetic-only database."""
import os
from pathlib import Path
import secrets

DEMO_DATABASE = Path("/tmp") / f"green-school-demo-{secrets.token_hex(8)}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DEMO_DATABASE.as_posix()}"
os.environ["SCHOOL_ERP_SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ["SCHOOL_ERP_SECURE_COOKIES"] = "1"
os.environ["SCHOOL_ERP_PUBLIC_DEMO"] = "1"

import seed_demo

seed_demo.getpass = lambda _: secrets.token_urlsafe(48)
seed_demo.main()
os.execvp("gunicorn", ["gunicorn", "--bind", f"0.0.0.0:{os.environ.get('PORT', '8000')}",
                       "--workers", "1", "--forwarded-allow-ips=*", "run:app"])
