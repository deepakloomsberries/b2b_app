import json

from conftest import login, post_with_csrf


def _seed_customer_and_product(db, stock_qty=10):
    with db() as conn:
        conn.execute(
            "INSERT INTO customers (name, phone, address, created_at) VALUES ('Cust', '1', 'a', datetime('now'))"
        )
        conn.execute(
            "INSERT INTO products (sku, title, price, is_active) VALUES ('SKU-1', 'Widget', 10, 1)"
        )
        conn.execute("INSERT INTO stock (sku, stock_qty) VALUES ('SKU-1', ?)", (stock_qty,))
        conn.commit()
        return conn.execute("SELECT id FROM customers WHERE name = 'Cust'").fetchone()[0]


def test_place_order_blocked_when_stock_insufficient(client, db):
    login(client)
    customer_id = _seed_customer_and_product(db, stock_qty=1)
    response = post_with_csrf(
        client,
        "/place_order",
        {
            "customer_id": str(customer_id),
            "items_json": json.dumps([{"sku": "SKU-1", "qty": 5}]),
            "order_remarks": "",
        },
        get_path=f"/catalog/{customer_id}",
    )
    assert b"Not enough available stock" in response.data
    with db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    assert count == 0


def test_place_order_success_creates_order_and_audit_log(client, db):
    login(client)
    customer_id = _seed_customer_and_product(db, stock_qty=10)
    post_with_csrf(
        client,
        "/place_order",
        {
            "customer_id": str(customer_id),
            "items_json": json.dumps([{"sku": "SKU-1", "qty": 2}]),
            "order_remarks": "please rush",
        },
        get_path=f"/catalog/{customer_id}",
    )
    with db() as conn:
        order = conn.execute("SELECT * FROM orders").fetchone()
        assert order is not None
        assert order["order_status"] == "submitted"
        audit = conn.execute(
            "SELECT * FROM audit_logs WHERE action = 'order_placed'"
        ).fetchone()
        assert audit is not None
        details = json.loads(audit["details"])
        assert details["order_number"] == order["order_number"]


def test_duplicate_order_within_five_minutes_is_rejected(client, db):
    login(client)
    customer_id = _seed_customer_and_product(db, stock_qty=10)
    payload = {
        "customer_id": str(customer_id),
        "items_json": json.dumps([{"sku": "SKU-1", "qty": 2}]),
        "order_remarks": "",
    }
    post_with_csrf(client, "/place_order", payload, get_path=f"/catalog/{customer_id}")
    response = post_with_csrf(client, "/place_order", payload, get_path=f"/catalog/{customer_id}")
    assert b"already submitted recently" in response.data
    with db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    assert count == 1


def test_orders_list_filters_by_salesman(client, db):
    login(client)
    with db() as conn:
        conn.execute(
            "INSERT INTO customers (name, phone, address, created_at) VALUES ('Cust', '1', 'a', datetime('now'))"
        )
        customer_id = conn.execute("SELECT id FROM customers WHERE name = 'Cust'").fetchone()[0]
        conn.execute(
            "INSERT INTO orders (order_number, customer_id, created_at, submitted_by) "
            "VALUES ('ORD-ALICE', ?, datetime('now'), 'Alice')",
            (customer_id,),
        )
        conn.execute(
            "INSERT INTO orders (order_number, customer_id, created_at, submitted_by) "
            "VALUES ('ORD-BOB', ?, datetime('now'), 'Bob')",
            (customer_id,),
        )
        conn.commit()

    response = client.get("/orders?view=history&salesman=Alice")
    html = response.data.decode()
    assert "ORD-ALICE" in html
    assert "ORD-BOB" not in html

    # The filter dropdown should list every distinct salesman who has ever submitted.
    unfiltered = client.get("/orders?view=history").data.decode()
    assert 'value="Alice"' in unfiltered
    assert 'value="Bob"' in unfiltered


def test_orders_list_paginates_with_next_and_previous(client, db):
    login(client)
    with db() as conn:
        conn.execute(
            "INSERT INTO customers (name, phone, address, created_at) VALUES ('Cust', '1', 'a', datetime('now'))"
        )
        customer_id = conn.execute("SELECT id FROM customers WHERE name = 'Cust'").fetchone()[0]
        for i in range(15):
            conn.execute(
                "INSERT INTO orders (order_number, customer_id, created_at, submitted_by) "
                "VALUES (?, ?, ?, 'admin')",
                (f"ORD-{i:02d}", customer_id, f"2025-01-{i + 1:02d}T00:00:00"),
            )
        conn.commit()

    page1 = client.get("/orders?view=history&limit=10&page=1").data.decode()
    assert "ORD-14" in page1  # newest first
    assert "ORD-04" not in page1  # 11th newest, belongs on page 2
    assert ">Next<" in page1
    assert ">Previous<" not in page1

    page2 = client.get("/orders?view=history&limit=10&page=2").data.decode()
    assert "ORD-04" in page2
    assert "ORD-14" not in page2
    assert ">Previous<" in page2
    assert ">Next<" not in page2


def test_customers_list_shows_most_recent_order_total(client, db):
    login(client)
    with db() as conn:
        conn.execute(
            "INSERT INTO customers (name, phone, address, created_at) VALUES ('WithOrders', '1', 'a', datetime('now'))"
        )
        customer_id = conn.execute("SELECT id FROM customers WHERE name = 'WithOrders'").fetchone()[0]
        conn.execute(
            "INSERT INTO orders (order_number, customer_id, created_at, submitted_by) "
            "VALUES ('ORD-OLD', ?, '2020-01-01T00:00:00', 'x')",
            (customer_id,),
        )
        old_id = conn.execute("SELECT id FROM orders WHERE order_number = 'ORD-OLD'").fetchone()[0]
        conn.execute(
            "INSERT INTO order_items (order_id, sku, title_snapshot, price_snapshot, qty) "
            "VALUES (?, 'SKU-A', 'Old item', 10, 1)",
            (old_id,),
        )
        conn.execute(
            "INSERT INTO orders (order_number, customer_id, created_at, submitted_by) "
            "VALUES ('ORD-NEW', ?, '2025-06-01T00:00:00', 'x')",
            (customer_id,),
        )
        new_id = conn.execute("SELECT id FROM orders WHERE order_number = 'ORD-NEW'").fetchone()[0]
        conn.execute(
            "INSERT INTO order_items (order_id, sku, title_snapshot, price_snapshot, qty) "
            "VALUES (?, 'SKU-B', 'New item', 20, 3)",
            (new_id,),
        )
        conn.commit()

    response = client.get("/customers")
    html = response.data.decode()
    snippet = html[html.find("WithOrders"):html.find("WithOrders") + 1500]
    assert "2025" in snippet
    assert "value: SAR 60.00" in snippet
    assert "value: SAR 10.00" not in snippet
