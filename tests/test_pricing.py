import json

from werkzeug.security import generate_password_hash

from conftest import login, post_with_csrf


def _seed(db, salesman_price=None, min_price_percent=None, vat_rate=None):
    with db() as conn:
        conn.execute(
            "INSERT INTO users (name, role, password, created_at) VALUES ('sales1', 'user', ?, datetime('now'))",
            (generate_password_hash("Sales123!"),),
        )
        conn.execute(
            "INSERT INTO customers (name, phone, address, created_at) VALUES ('Cust', '1', 'a', datetime('now'))"
        )
        conn.execute(
            "INSERT INTO products (sku, title, price, price_credit, price_cash, is_active) "
            "VALUES ('SKU-1', 'Widget', 100, 100, 90, 1)"
        )
        conn.execute("INSERT INTO stock (sku, stock_qty) VALUES ('SKU-1', 50)")
        sales_user_id = conn.execute("SELECT id FROM users WHERE name = 'sales1'").fetchone()[0]
        customer_id = conn.execute("SELECT id FROM customers WHERE name = 'Cust'").fetchone()[0]
        if salesman_price is not None:
            conn.execute(
                "INSERT INTO salesman_prices (user_id, sku, price, updated_at) VALUES (?, 'SKU-1', ?, datetime('now'))",
                (sales_user_id, salesman_price),
            )
        if min_price_percent is not None:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('min_price_percent', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(min_price_percent),),
            )
        if vat_rate is not None:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('vat_rate', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(vat_rate),),
            )
        conn.commit()
        return sales_user_id, customer_id


def test_catalog_shows_salesman_override_price(client, db):
    sales_user_id, customer_id = _seed(db, salesman_price=80)
    login(client, username="sales1", password="Sales123!")
    response = client.get(f"/catalog/{customer_id}")
    assert b'"has_override": true' in response.data
    assert b'"price": 80.0' in response.data


def test_catalog_shows_standard_price_for_salesman_without_override(client, db):
    _, customer_id = _seed(db)
    login(client, username="sales1", password="Sales123!")
    response = client.get(f"/catalog/{customer_id}")
    # No override set - the salesman should see the standard price, unmodified.
    assert b'"has_override": false' in response.data
    assert b'"price": 100.0' in response.data


def test_admin_can_set_and_clear_salesman_price(client, db):
    sales_user_id, customer_id = _seed(db)
    login(client)
    post_with_csrf(
        client,
        "/admin",
        {"action": "set_salesman_price", "pricing_user_id": str(sales_user_id),
         "pricing_sku": "SKU-1", "pricing_price": "77"},
        get_path=f"/admin?salesman_id={sales_user_id}",
    )
    with db() as conn:
        price = conn.execute(
            "SELECT price FROM salesman_prices WHERE user_id = ? AND sku = 'SKU-1'", (sales_user_id,)
        ).fetchone()["price"]
    assert price == 77.0

    post_with_csrf(
        client,
        "/admin",
        {"action": "clear_salesman_price", "pricing_user_id": str(sales_user_id), "pricing_sku": "SKU-1"},
        get_path=f"/admin?salesman_id={sales_user_id}",
    )
    with db() as conn:
        row = conn.execute(
            "SELECT price FROM salesman_prices WHERE user_id = ? AND sku = 'SKU-1'", (sales_user_id,)
        ).fetchone()
    assert row is None


def test_order_time_price_below_floor_is_rejected(client, db):
    _seed(db, salesman_price=80, min_price_percent=90)  # floor = 72
    login(client, username="sales1", password="Sales123!")
    with db() as conn:
        customer_id = conn.execute("SELECT id FROM customers WHERE name = 'Cust'").fetchone()[0]

    response = post_with_csrf(
        client,
        "/place_order",
        {
            "customer_id": str(customer_id),
            "items_json": json.dumps([{"sku": "SKU-1", "qty": 1, "unit_price": 50}]),
            "order_remarks": "",
        },
        get_path=f"/catalog/{customer_id}",
    )
    assert b"outside the allowed range" in response.data
    with db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0


def test_order_time_price_above_assigned_price_is_rejected(client, db):
    _seed(db, salesman_price=80)
    login(client, username="sales1", password="Sales123!")
    with db() as conn:
        customer_id = conn.execute("SELECT id FROM customers WHERE name = 'Cust'").fetchone()[0]

    response = post_with_csrf(
        client,
        "/place_order",
        {
            "customer_id": str(customer_id),
            "items_json": json.dumps([{"sku": "SKU-1", "qty": 1, "unit_price": 150}]),
            "order_remarks": "",
        },
        get_path=f"/catalog/{customer_id}",
    )
    assert b"outside the allowed range" in response.data
    with db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0


def test_order_time_price_within_floor_is_accepted(client, db):
    _seed(db, salesman_price=80, min_price_percent=90)  # floor = 72
    login(client, username="sales1", password="Sales123!")
    with db() as conn:
        customer_id = conn.execute("SELECT id FROM customers WHERE name = 'Cust'").fetchone()[0]

    post_with_csrf(
        client,
        "/place_order",
        {
            "customer_id": str(customer_id),
            "items_json": json.dumps([{"sku": "SKU-1", "qty": 2, "unit_price": 75}]),
            "order_remarks": "",
        },
        get_path=f"/catalog/{customer_id}",
    )
    with db() as conn:
        order = conn.execute("SELECT id FROM orders").fetchone()
        assert order is not None
        item = conn.execute(
            "SELECT price_snapshot FROM order_items WHERE order_id = ?", (order["id"],)
        ).fetchone()
        assert item["price_snapshot"] == 75.0


def test_default_min_price_percent_disallows_any_discount(client, db):
    # min_price_percent defaults to 100 - floor equals the assigned price exactly.
    _seed(db, salesman_price=80)
    login(client, username="sales1", password="Sales123!")
    with db() as conn:
        customer_id = conn.execute("SELECT id FROM customers WHERE name = 'Cust'").fetchone()[0]

    response = post_with_csrf(
        client,
        "/place_order",
        {
            "customer_id": str(customer_id),
            "items_json": json.dumps([{"sku": "SKU-1", "qty": 1, "unit_price": 79}]),
            "order_remarks": "",
        },
        get_path=f"/catalog/{customer_id}",
    )
    assert b"outside the allowed range" in response.data


def test_order_success_shows_subtotal_vat_and_total(client, db):
    _seed(db, vat_rate=20)
    login(client)
    with db() as conn:
        customer_id = conn.execute("SELECT id FROM customers WHERE name = 'Cust'").fetchone()[0]

    response = post_with_csrf(
        client,
        "/place_order",
        {
            "customer_id": str(customer_id),
            "items_json": json.dumps([{"sku": "SKU-1", "qty": 2}]),  # 2 x 100 = 200
            "order_remarks": "",
        },
        get_path=f"/catalog/{customer_id}",
    )
    html = response.data.decode()
    assert "200.00" in html  # subtotal
    assert "40.00" in html  # 20% VAT
    assert "240.00" in html  # total


def test_quotation_returns_pdf_without_creating_order(client, db):
    _seed(db, salesman_price=80)
    login(client, username="sales1", password="Sales123!")
    with db() as conn:
        customer_id = conn.execute("SELECT id FROM customers WHERE name = 'Cust'").fetchone()[0]

    response = post_with_csrf(
        client,
        "/quotation",
        {
            "customer_id": str(customer_id),
            "items_json": json.dumps([{"sku": "SKU-1", "qty": 3, "unit_price": 80}]),
        },
        get_path=f"/catalog/{customer_id}",
    )
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    assert response.data[:4] == b"%PDF"
    with db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
