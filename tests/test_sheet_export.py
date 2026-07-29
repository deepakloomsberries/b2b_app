import json

import google_sheets
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


def _place_order(client, customer_id, qty=1):
    return post_with_csrf(
        client,
        "/place_order",
        {
            "customer_id": str(customer_id),
            "items_json": json.dumps([{"sku": "SKU-1", "qty": qty}]),
            "order_remarks": "",
        },
        get_path=f"/catalog/{customer_id}",
    )


def test_order_marked_export_failed_when_export_returns_failure(client, db, monkeypatch):
    """A clean export failure must flip the order to export_failed so it is
    retryable — never leave it stuck at 'pending' or falsely 'exported'."""
    login(client)
    customer_id = _seed_customer_and_product(db)
    monkeypatch.setattr(
        google_sheets, "export_order_rows", lambda *a, **k: (False, "boom")
    )
    _place_order(client, customer_id)
    with db() as conn:
        status = conn.execute("SELECT export_status FROM orders").fetchone()[0]
    assert status == "export_failed"


def test_order_marked_export_failed_when_export_raises(client, db, monkeypatch):
    """An exception raised by the export must not crash the request or leave the
    order stuck; the order is saved and flagged export_failed."""
    login(client)
    customer_id = _seed_customer_and_product(db)

    def boom(*a, **k):
        raise RuntimeError("gspread API error")

    monkeypatch.setattr(google_sheets, "export_order_rows", boom)
    response = _place_order(client, customer_id)
    assert response.status_code == 200
    with db() as conn:
        row = conn.execute("SELECT export_status FROM orders").fetchone()
    assert row is not None
    assert row["export_status"] == "export_failed"


def test_order_marked_exported_on_success(client, db, monkeypatch):
    login(client)
    customer_id = _seed_customer_and_product(db)
    monkeypatch.setattr(
        google_sheets, "export_order_rows", lambda *a, **k: (True, "Exported.")
    )
    _place_order(client, customer_id)
    with db() as conn:
        status = conn.execute("SELECT export_status FROM orders").fetchone()[0]
    assert status == "exported"


def test_retry_picks_up_pending_orders(app_module, db, monkeypatch):
    """The core regression: an order stuck at 'pending' (export never completed)
    must be picked up by the retry sweep, not silently skipped."""
    with db() as conn:
        conn.execute(
            "INSERT INTO customers (name, phone, address, created_at) VALUES ('C', '1', 'a', datetime('now'))"
        )
        customer_id = conn.execute("SELECT id FROM customers").fetchone()[0]
        conn.execute(
            "INSERT INTO orders (order_number, customer_id, created_at, export_status, submitted_by) "
            "VALUES ('ORD-PENDING', ?, datetime('now'), 'pending', 'x')",
            (customer_id,),
        )
        order_id = conn.execute("SELECT id FROM orders WHERE order_number = 'ORD-PENDING'").fetchone()[0]
        conn.execute(
            "INSERT INTO order_items (order_id, sku, title_snapshot, price_snapshot, qty) "
            "VALUES (?, 'SKU-1', 'Widget', 10, 1)",
            (order_id,),
        )
        conn.commit()

    monkeypatch.setattr(
        google_sheets, "export_order_rows", lambda *a, **k: (True, "Exported.")
    )
    success, _ = google_sheets.retry_failed_exports()
    assert success is True
    with db() as conn:
        status = conn.execute(
            "SELECT export_status FROM orders WHERE order_number = 'ORD-PENDING'"
        ).fetchone()[0]
    assert status == "exported"


def test_retry_continues_past_a_failing_order(app_module, db, monkeypatch):
    """One order that keeps failing must not abort the whole retry batch."""
    with db() as conn:
        conn.execute(
            "INSERT INTO customers (name, phone, address, created_at) VALUES ('C', '1', 'a', datetime('now'))"
        )
        customer_id = conn.execute("SELECT id FROM customers").fetchone()[0]
        for order_number in ("ORD-A", "ORD-B"):
            conn.execute(
                "INSERT INTO orders (order_number, customer_id, created_at, export_status, submitted_by) "
                "VALUES (?, ?, datetime('now'), 'export_failed', 'x')",
                (order_number, customer_id),
            )
            oid = conn.execute("SELECT id FROM orders WHERE order_number = ?", (order_number,)).fetchone()[0]
            conn.execute(
                "INSERT INTO order_items (order_id, sku, title_snapshot, price_snapshot, qty) "
                "VALUES (?, 'SKU-1', 'Widget', 10, 1)",
                (oid,),
            )
        conn.commit()

    def selective(order_number, *a, **k):
        if order_number == "ORD-A":
            return False, "still failing"
        return True, "Exported."

    monkeypatch.setattr(google_sheets, "export_order_rows", selective)
    success, message = google_sheets.retry_failed_exports()
    assert success is False  # ORD-A still failing
    with db() as conn:
        rows = dict(
            conn.execute("SELECT order_number, export_status FROM orders").fetchall()
        )
    assert rows["ORD-A"] == "export_failed"
    assert rows["ORD-B"] == "exported"  # not blocked by ORD-A's failure
