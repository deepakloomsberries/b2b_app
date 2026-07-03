from conftest import login, post_with_csrf


def _seed_customer(db, outstanding_balance):
    with db() as conn:
        conn.execute(
            "INSERT INTO customers (name, phone, address, created_at, outstanding_balance) "
            "VALUES ('Cust', '1', 'a', datetime('now'), ?)",
            (outstanding_balance,),
        )
        conn.commit()
        return conn.execute("SELECT id FROM customers WHERE name = 'Cust'").fetchone()[0]


def test_no_warning_when_credit_limit_disabled(client, db):
    login(client)
    customer_id = _seed_customer(db, outstanding_balance=5000)
    response = client.get(f"/catalog/{customer_id}")
    assert b"Over the SAR" not in response.data
    assert b"over the SAR" not in response.data


def test_warning_shown_when_over_credit_limit(client, db):
    login(client)
    customer_id = _seed_customer(db, outstanding_balance=5000)
    post_with_csrf(
        client,
        "/admin",
        {"action": "save_settings", "reservation_mode": "on", "allow_oversell": "off",
         "show_stock_to_customers": "on", "currency_symbol": "SAR",
         "low_stock_threshold": "5", "credit_limit": "1000"},
        get_path="/admin",
    )
    response = client.get(f"/catalog/{customer_id}")
    assert b"over the SAR 1000.00 credit limit" in response.data

    list_response = client.get("/customers")
    assert b"Over credit limit" in list_response.data


def test_no_warning_when_under_credit_limit(client, db):
    login(client)
    customer_id = _seed_customer(db, outstanding_balance=500)
    post_with_csrf(
        client,
        "/admin",
        {"action": "save_settings", "reservation_mode": "on", "allow_oversell": "off",
         "show_stock_to_customers": "on", "currency_symbol": "SAR",
         "low_stock_threshold": "5", "credit_limit": "1000"},
        get_path="/admin",
    )
    response = client.get(f"/catalog/{customer_id}")
    assert b"over the SAR" not in response.data
