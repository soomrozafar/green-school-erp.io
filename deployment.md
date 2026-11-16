# Production Deployment

## Linux + Gunicorn

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
gunicorn --bind 127.0.0.1:8000 --workers 3 run:app
```

Put Nginx in front of Gunicorn and enable HTTPS. Set `SCHOOL_ERP_SECRET_KEY` and a production `DATABASE_URL` as environment variables.

## Docker

```bash
docker build -t school-erp .
docker run -p 8000:8000 -e SCHOOL_ERP_SECRET_KEY='change-me' school-erp
```

Do not use the default development secret in production. Use PostgreSQL/MySQL for production rather than SQLite for multi-user workloads.
