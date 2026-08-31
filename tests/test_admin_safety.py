import io
import json
import re

from conftest import login, post_with_csrf


def test_upload_form_defaults_to_safe_upsert_mode(client):
    login(client)
    html = client.get("/admin").data.decode()
    select_block = html[html.find('name="upload_mode"'):html.find("</select>")]
    assert 'value="upsert" selected' in select_block
    # "replace" must not be the pre-selected option, since it silently
    # deletes every product not in the uploaded file.
    assert 'value="replace" selected' not in select_block


def test_replace_upload_logs_pre_delete_count_for_recovery(client, db):
    login(client)
    with db() as conn:
        conn.execute(
            "INSERT INTO products (sku, title, price, is_active) VALUES ('SKU-OLD', 'Old Widget', 5, 1)"
        )
        conn.commit()

    csv_content = b"sku,title,price\nSKU-NEW,New Widget,10\n"
    response = client.get("/admin")
    token = re.search(r'name="csrf_token" value="([^"]+)"', response.data.decode()).group(1)
    client.post(
        "/admin",
        data={
            "action": "upload_catalogue",
            "upload_mode": "replace",
            "csrf_token": token,
            "catalogue_csv": (io.BytesIO(csv_content), "catalogue.csv"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    with db() as conn:
        audit = conn.execute(
            "SELECT details FROM audit_logs WHERE action = 'catalogue_replace_delete'"
        ).fetchone()
        assert audit is not None
        details = json.loads(audit["details"])
        assert details["products_deleted"] == 1

        skus = {row["sku"] for row in conn.execute("SELECT sku FROM products").fetchall()}
        assert skus == {"SKU-NEW"}


def test_upsert_upload_does_not_delete_existing_products(client, db):
    login(client)
    with db() as conn:
        conn.execute(
            "INSERT INTO products (sku, title, price, is_active) VALUES ('SKU-KEEP', 'Keep Me', 5, 1)"
        )
        conn.commit()

    csv_content = b"sku,title,price\nSKU-NEW,New Widget,10\n"
    response = client.get("/admin")
    token = re.search(r'name="csrf_token" value="([^"]+)"', response.data.decode()).group(1)
    client.post(
        "/admin",
        data={
            "action": "upload_catalogue",
            "upload_mode": "upsert",
            "csrf_token": token,
            "catalogue_csv": (io.BytesIO(csv_content), "catalogue.csv"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    with db() as conn:
        skus = {row["sku"] for row in conn.execute("SELECT sku FROM products").fetchall()}
        assert skus == {"SKU-KEEP", "SKU-NEW"}


def test_bulk_delete_products_removes_selected_and_logs_audit(client, db):
    login(client)
    with db() as conn:
        conn.execute(
            "INSERT INTO products (sku, title, price, is_active) VALUES "
            "('SKU-A', 'Widget A', 5, 1), ('SKU-B', 'Widget B', 6, 1), ('SKU-C', 'Widget C', 7, 1)"
        )
        conn.execute("INSERT INTO stock (sku, stock_qty) VALUES ('SKU-A', 10), ('SKU-B', 20)")
        conn.execute("INSERT INTO reserved_stock (sku, reserved_qty) VALUES ('SKU-A', 2)")
        conn.commit()

    response = post_with_csrf(
        client,
        "/admin",
        {"action": "bulk_delete_products", "skus": ["SKU-A", "SKU-B"]},
        get_path="/admin",
    )
    assert b"Deleted 2 product(s)." in response.data

    with db() as conn:
        remaining = {row["sku"] for row in conn.execute("SELECT sku FROM products").fetchall()}
        assert remaining == {"SKU-C"}

        stock_remaining = {row["sku"] for row in conn.execute("SELECT sku FROM stock").fetchall()}
        assert "SKU-A" not in stock_remaining
        assert "SKU-B" not in stock_remaining

        reserved_remaining = {
            row["sku"] for row in conn.execute("SELECT sku FROM reserved_stock").fetchall()
        }
        assert "SKU-A" not in reserved_remaining

        audit = conn.execute(
            "SELECT details FROM audit_logs WHERE action = 'product_bulk_delete'"
        ).fetchone()
        assert audit is not None
        details = json.loads(audit["details"])
        assert details["count"] == 2
        assert {p["sku"] for p in details["products"]} == {"SKU-A", "SKU-B"}


def test_bulk_delete_products_with_no_selection_shows_warning(client, db):
    login(client)
    with db() as conn:
        conn.execute(
            "INSERT INTO products (sku, title, price, is_active) VALUES ('SKU-KEEP', 'Keep Me', 5, 1)"
        )
        conn.commit()

    response = post_with_csrf(
        client, "/admin", {"action": "bulk_delete_products"}, get_path="/admin"
    )
    assert b"Select at least one product to delete." in response.data
    with db() as conn:
        skus = {row["sku"] for row in conn.execute("SELECT sku FROM products").fetchall()}
    assert skus == {"SKU-KEEP"}


def test_plain_user_cannot_bulk_delete_products(client, db):
    from werkzeug.security import generate_password_hash

    with db() as conn:
        conn.execute(
            "INSERT INTO users (name, role, password, created_at) VALUES (?, 'user', ?, datetime('now'))",
            ("salesuser", generate_password_hash("Salespass123!")),
        )
        conn.execute(
            "INSERT INTO products (sku, title, price, is_active) VALUES ('SKU-KEEP', 'Keep Me', 5, 1)"
        )
        conn.commit()
    login(client, username="salesuser", password="Salespass123!")

    response = post_with_csrf(
        client,
        "/admin",
        {"action": "bulk_delete_products", "skus": ["SKU-KEEP"]},
        get_path="/orders",
    )
    assert b"Admin access required" in response.data
    with db() as conn:
        skus = {row["sku"] for row in conn.execute("SELECT sku FROM products").fetchall()}
    assert skus == {"SKU-KEEP"}


def test_static_url_includes_cache_busting_version(client):
    login(client)
    html = client.get("/login").data.decode()
    match = re.search(r'href="(/static/css/styles\.css\?v=\d+)"', html)
    assert match is not None
    response = client.get(match.group(1))
    assert response.status_code == 200
