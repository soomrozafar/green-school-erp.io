import pytest
from app import create_app
from app.extensions import db

@pytest.fixture()
def app():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.app_context():
        from app.models import User
        u=User(username='admin', role='admin'); u.set_password('testpass123'); db.session.add(u); db.session.commit()
    yield app
    with app.app_context(): db.session.remove()

def test_login_page(app):
    assert app.test_client().get('/login').status_code == 200

def test_api_health(app):
    r=app.test_client().get('/api/v1/health'); assert r.status_code == 200; assert r.get_json()['status']=='ok'

def test_permissions_requires_admin(app):
    c=app.test_client(); r=c.get('/admin/permissions'); assert r.status_code in (302, 303)
