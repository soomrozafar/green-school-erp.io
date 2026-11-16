from pathlib import Path
import os
BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / 'instance'
INSTANCE_DIR.mkdir(exist_ok=True)

def ollama_address():
    port = os.environ.get("SCHOOL_ERP_OLLAMA_PORT", "11434")
    if not port.isascii() or not port.isdecimal() or len(port) > 5 or not 1 <= int(port) <= 65535:
        raise ValueError("SCHOOL_ERP_OLLAMA_PORT must be a valid TCP port.")
    return f"127.0.0.1:{int(port)}"


class Config:
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SCHOOL_ERP_SECURE_COOKIES', '0') == '1'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{INSTANCE_DIR / "school.db"}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    AUTO_CREATE_DB = os.environ.get('SCHOOL_ERP_AUTO_CREATE_DB', '1') == '1'
    AUTO_SCHEMA_UPGRADE = os.environ.get('SCHOOL_ERP_AUTO_SCHEMA_UPGRADE', '1') == '1'
    MAX_CONTENT_LENGTH = int(os.environ.get('SCHOOL_ERP_MAX_UPLOAD_MB', '10')) * 1024 * 1024
