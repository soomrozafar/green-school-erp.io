import pytest
from app import create_app

@pytest.fixture()
def client():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
    with app.test_client() as c:
        yield c

def test_health(client):
    r = client.get('/api/v1/health')
    assert r.status_code == 200
    assert r.get_json()['status'] == 'ok'

def test_login_page(client):
    r = client.get('/login')
    assert r.status_code == 200

def test_protected_summary_requires_login(client):
    r = client.get('/api/v1/summary')
    assert r.status_code in (302, 401)
