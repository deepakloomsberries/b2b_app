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


def test_static_url_includes_cache_busting_version(client):
    login(client)
    html = client.get("/login").data.decode()
    match = re.search(r'href="(/static/css/styles\.css\?v=\d+)"', html)
    assert match is not None
    response = client.get(match.group(1))
    assert response.status_code == 200
