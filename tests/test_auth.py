from conftest import extract_csrf, login, post_with_csrf


def test_login_success_redirects_home(client):
    response = login(client)
    assert response.status_code == 200
    assert b"Logout" in response.data


def test_login_wrong_password_shows_error(client):
    response = login(client, password="wrong")
    assert b"Invalid credentials" in response.data


def test_anonymous_request_redirects_to_login(client):
    response = client.get("/customers", follow_redirects=True)
    assert b"Login" in response.data
    assert response.request.path == "/login"


def test_post_without_csrf_token_is_rejected(client):
    login(client)
    response = client.post(
        "/customers/new", data={"name": "NoToken", "phone": "1", "address": "a"},
        follow_redirects=True,
    )
    assert b"session expired" in response.data.lower()


def test_post_with_forged_csrf_token_is_rejected(client, app_module):
    login(client)
    other_client = app_module.app.test_client()
    forged = extract_csrf(other_client.get("/login").data.decode())
    response = client.post(
        "/customers/new",
        data={"name": "Forged", "phone": "1", "address": "a", "csrf_token": forged},
        follow_redirects=True,
    )
    assert b"session expired" in response.data.lower()


def test_fetch_style_post_gets_json_error_not_redirect_on_bad_csrf(client):
    # A JS fetch() call identifies itself by sending the token via header
    # instead of a form field. If CSRF fails, it must get a real error
    # status (fetch() auto-follows redirects and would otherwise see a
    # misleading 200 on the redirect target).
    login(client)
    response = client.post(
        "/save_draft",
        data={"customer_id": "1", "items_json": "[]"},
        headers={"X-CSRFToken": "not-a-real-token"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "csrf_failed"}


def test_login_locks_after_five_failed_attempts(client):
    for _ in range(5):
        login(client, password="wrong")
    response = login(client, password="Adminpass123!")
    assert b"Too many failed attempts" in response.data


def test_lockout_is_shared_between_username_and_email(client, db):
    with db() as conn:
        conn.execute("UPDATE users SET email = 'admin@example.com' WHERE name = 'admin'")
        conn.commit()

    for _ in range(3):
        login(client, username="admin", password="wrong")
    for _ in range(3):
        response = login(client, username="admin@example.com", password="wrong")

    assert b"Too many failed attempts" in response.data


def test_lockout_clears_on_successful_login(client, db):
    for _ in range(5):
        login(client, password="wrong")
    with db() as conn:
        conn.execute("DELETE FROM login_attempts")
        conn.commit()
    response = login(client, password="Adminpass123!")
    assert b"Logout" in response.data
