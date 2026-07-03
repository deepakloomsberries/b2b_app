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
