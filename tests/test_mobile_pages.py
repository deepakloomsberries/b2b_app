from werkzeug.security import generate_password_hash

from conftest import login


def _seed_two_orders(db):
    with db() as conn:
        conn.execute(
            "INSERT INTO customers (name, phone, address, created_at) VALUES ('Cust', '1', 'a', datetime('now'))"
        )
        customer_id = conn.execute("SELECT id FROM customers WHERE name = 'Cust'").fetchone()[0]
        conn.execute(
            "INSERT INTO orders (order_number, customer_id, created_at, submitted_by) "
            "VALUES ('ORD-OLD', ?, '2020-01-01T00:00:00', 'x')",
            (customer_id,),
        )
        conn.execute(
            "INSERT INTO orders (order_number, customer_id, created_at, submitted_by) "
            "VALUES ('ORD-NEW', ?, '2025-06-01T00:00:00', 'x')",
            (customer_id,),
        )
        conn.commit()


def test_orders_mobile_defaults_to_newest_first(client, db):
    _seed_two_orders(db)
    login(client)
    response = client.get("/orders-mobile")
    html = response.data.decode()
    assert html.index("ORD-NEW") < html.index("ORD-OLD")


def test_orders_mobile_sort_asc_shows_oldest_first(client, db):
    _seed_two_orders(db)
    login(client)
    response = client.get("/orders-mobile?sort=asc")
    html = response.data.decode()
    assert html.index("ORD-OLD") < html.index("ORD-NEW")


def test_dashboard_admin_tile_hidden_for_non_admin(client, db):
    with db() as conn:
        conn.execute(
            "INSERT INTO users (name, role, password, created_at) VALUES ('sales1', 'user', ?, datetime('now'))",
            (generate_password_hash("Sales123!"),),
        )
        conn.commit()
    login(client, username="sales1", password="Sales123!")
    response = client.get("/")
    assert b"Admin</span>" not in response.data


def test_dashboard_admin_tile_shown_for_admin(client, db):
    login(client)
    response = client.get("/")
    assert b"Admin</span>" in response.data


def test_error_pages_use_real_button_class(client):
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404
    assert b'class="button"' in response.data
    assert b'class="btn"' not in response.data
