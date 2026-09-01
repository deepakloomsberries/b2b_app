import csv
import io
import json

from conftest import login, post_with_csrf


def test_order_csv_export_escapes_commas_and_quotes(client, db):
    login(client)
    with db() as conn:
        conn.execute(
            "INSERT INTO customers (name, phone, address, created_at) VALUES (?, '1', 'a', datetime('now'))",
            ('Tricky, Customer "Ltd"',),
        )
        customer_id = conn.execute("SELECT id FROM customers WHERE phone = '1'").fetchone()[0]
        conn.execute(
            "INSERT INTO products (sku, title, price, is_active) VALUES ('SKU-1', ?, 10, 1)",
            ('Widget, Deluxe "Pro"',),
        )
        conn.execute("INSERT INTO stock (sku, stock_qty) VALUES ('SKU-1', 10)")
        conn.commit()

    post_with_csrf(
        client,
        "/place_order",
        {
            "customer_id": str(customer_id),
            "items_json": json.dumps([{"sku": "SKU-1", "qty": 2}]),
            "order_remarks": "",
        },
        get_path=f"/catalog/{customer_id}",
    )
    with db() as conn:
        order_number = conn.execute("SELECT order_number FROM orders").fetchone()[0]

    response = client.get(f"/orders/{order_number}/download")
    rows = list(csv.reader(io.StringIO(response.data.decode())))

    customer_row = next(row for row in rows if row[0] == "Customer")
    assert customer_row[1] == 'Tricky, Customer "Ltd"'
    item_row = next(row for row in rows if row and row[0] == "SKU-1")
    assert item_row[1] == 'Widget, Deluxe "Pro"'


def test_order_csv_export_includes_salesman_and_status(client, db):
    login(client)
    with db() as conn:
        conn.execute(
            "INSERT INTO customers (name, phone, address, created_at) VALUES ('Cust', '1', 'a', datetime('now'))"
        )
        customer_id = conn.execute("SELECT id FROM customers WHERE name = 'Cust'").fetchone()[0]
        conn.execute(
            "INSERT INTO products (sku, title, price, is_active) VALUES ('SKU-1', 'Widget', 10, 1)"
        )
        conn.execute("INSERT INTO stock (sku, stock_qty) VALUES ('SKU-1', 10)")
        conn.commit()

    post_with_csrf(
        client,
        "/place_order",
        {
            "customer_id": str(customer_id),
            "items_json": json.dumps([{"sku": "SKU-1", "qty": 1}]),
            "order_remarks": "",
        },
        get_path=f"/catalog/{customer_id}",
    )
    with db() as conn:
        order_number = conn.execute("SELECT order_number FROM orders").fetchone()[0]

    response = client.get(f"/orders/{order_number}/download")
    rows = list(csv.reader(io.StringIO(response.data.decode())))
    salesman_row = next(row for row in rows if row[0] == "Salesman")
    assert salesman_row[1] == "admin"
    status_row = next(row for row in rows if row[0] == "Status")
    assert status_row[1] == "Submitted"


def test_bulk_export_csv_includes_customer_and_salesman_columns(client, db):
    login(client)
    with db() as conn:
        conn.execute(
            "INSERT INTO customers (name, phone, address, created_at) VALUES ('Bulk Customer', '1', 'a', datetime('now'))"
        )
        customer_id = conn.execute(
            "SELECT id FROM customers WHERE name = 'Bulk Customer'"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO products (sku, title, price, is_active) VALUES ('SKU-1', 'Widget', 10, 1)"
        )
        conn.execute("INSERT INTO stock (sku, stock_qty) VALUES ('SKU-1', 10)")
        conn.commit()

    post_with_csrf(
        client,
        "/place_order",
        {
            "customer_id": str(customer_id),
            "items_json": json.dumps([{"sku": "SKU-1", "qty": 2}]),
            "order_remarks": "",
        },
        get_path=f"/catalog/{customer_id}",
    )
    with db() as conn:
        order_number = conn.execute("SELECT order_number FROM orders").fetchone()[0]

    response = post_with_csrf(
        client,
        "/orders/bulk_action",
        {"bulk_action": "export_csv", "order_numbers": order_number},
        get_path="/orders",
    )
    rows = list(csv.reader(io.StringIO(response.data.decode())))
    header = rows[0]
    assert header == [
        "Order Number",
        "Customer",
        "Salesman",
        "Order Status",
        "Created At",
        "SKU",
        "Title",
        "Qty",
        "Price",
    ]
    data_row = rows[1]
    assert data_row[header.index("Customer")] == "Bulk Customer"
    assert data_row[header.index("Salesman")] == "admin"
    assert data_row[header.index("Order Status")] == "Submitted"


def test_order_csv_export_neutralizes_formula_like_values(client, db):
    login(client)
    with db() as conn:
        conn.execute(
            "INSERT INTO customers (name, phone, address, created_at) VALUES (?, '1', 'a', datetime('now'))",
            ('=cmd|"/c calc"!A1',),
        )
        customer_id = conn.execute("SELECT id FROM customers WHERE phone = '1'").fetchone()[0]
        conn.execute(
            "INSERT INTO products (sku, title, price, is_active) VALUES ('SKU-1', 'Widget', 10, 1)"
        )
        conn.execute("INSERT INTO stock (sku, stock_qty) VALUES ('SKU-1', 10)")
        conn.commit()

    post_with_csrf(
        client,
        "/place_order",
        {
            "customer_id": str(customer_id),
            "items_json": json.dumps([{"sku": "SKU-1", "qty": 1}]),
            "order_remarks": "",
        },
        get_path=f"/catalog/{customer_id}",
    )
    with db() as conn:
        order_number = conn.execute("SELECT order_number FROM orders").fetchone()[0]

    response = client.get(f"/orders/{order_number}/download")
    rows = list(csv.reader(io.StringIO(response.data.decode())))
    customer_row = next(row for row in rows if row[0] == "Customer")
    assert customer_row[1].startswith("'=")
