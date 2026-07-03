import importlib
import re

import pytest


def extract_csrf(html):
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return match.group(1) if match else None


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    """Import a fresh copy of the app bound to an isolated, empty database."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "Adminpass123!")
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)

    import app as appmod

    importlib.reload(appmod)
    appmod.init_db()
    appmod._seed_default_admin()
    appmod._db_initialized = True
    return appmod


@pytest.fixture
def client(app_module):
    return app_module.app.test_client()


@pytest.fixture
def db(app_module):
    from db import get_db

    return get_db


def post_with_csrf(client, path, data, get_path=None):
    """Fetch get_path (or path) to obtain a live CSRF token, then POST with it merged in."""
    response = client.get(get_path or path)
    token = extract_csrf(response.data.decode())
    payload = dict(data)
    payload["csrf_token"] = token
    return client.post(path, data=payload, follow_redirects=True)


def login(client, username="admin", password="Adminpass123!"):
    return post_with_csrf(client, "/login", {"username": username, "password": password})
