from werkzeug.security import generate_password_hash

from conftest import login, post_with_csrf


def _create_user(db, name, role, password):
    with db() as conn:
        conn.execute(
            "INSERT INTO users (name, role, password, created_at) VALUES (?, ?, ?, datetime('now'))",
            (name, role, generate_password_hash(password)),
        )
        conn.commit()


def _seed_order(db):
    with db() as conn:
        conn.execute(
            "INSERT INTO customers (name, phone, address, created_at) VALUES ('Cust', '1', 'a', datetime('now'))"
        )
        conn.execute(
            "INSERT INTO orders (order_number, customer_id, created_at, submitted_by) "
            "VALUES ('ORD-1', 1, datetime('now'), 'admin')"
        )
        conn.commit()


def test_plain_user_cannot_change_order_status(client, db):
    _create_user(db, "salesuser", "user", "Salespass123!")
    _seed_order(db)
    login(client, username="salesuser", password="Salespass123!")

    response = post_with_csrf(
        client, "/orders/ORD-1/status", {"order_status": "delivered"}, get_path="/orders"
    )
    assert b"Warehouse or admin access required" in response.data
    with db() as conn:
        status = conn.execute(
            "SELECT order_status FROM orders WHERE order_number = 'ORD-1'"
        ).fetchone()[0]
    assert status == "submitted"


def test_warehouse_user_can_change_order_status(client, db):
    _create_user(db, "whuser", "warehouse", "Whpass123!")
    _seed_order(db)
    login(client, username="whuser", password="Whpass123!")

    post_with_csrf(client, "/orders/ORD-1/status", {"order_status": "delivered"}, get_path="/orders")
    with db() as conn:
        status = conn.execute(
            "SELECT order_status FROM orders WHERE order_number = 'ORD-1'"
        ).fetchone()[0]
    assert status == "delivered"


def test_plain_user_cannot_bulk_update_orders(client, db):
    _create_user(db, "salesuser", "user", "Salespass123!")
    _seed_order(db)
    login(client, username="salesuser", password="Salespass123!")

    response = post_with_csrf(
        client,
        "/orders/bulk_action",
        {"bulk_action": "status", "bulk_status": "cancelled", "order_numbers": "ORD-1"},
        get_path="/orders",
    )
    assert b"Warehouse or admin access required" in response.data


def test_plain_user_cannot_access_admin_panel(client, db):
    _create_user(db, "salesuser", "user", "Salespass123!")
    login(client, username="salesuser", password="Salespass123!")
    response = client.get("/admin", follow_redirects=True)
    assert b"Admin access required" in response.data
