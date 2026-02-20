import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "app.db")


def get_db_path():
    return os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)


@contextmanager
def get_db(db_path=None):
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path=None):
    schema = """
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT,
        address TEXT,
        created_at TEXT,
        last_visited_at TEXT,
        phone_code TEXT,
        email TEXT,
        longitude TEXT,
        latitude TEXT,
        city TEXT,
        state TEXT,
        country TEXT,
        zip_code TEXT,
        buyer_group TEXT,
        app_user INTEGER DEFAULT 0,
        priority_flag TEXT,
        outstanding_balance REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        sku TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        price REAL NOT NULL,
        price_cash REAL,
        price_credit REAL,
        category TEXT,
        subcategory TEXT,
        sub_subcategory TEXT,
        mfr_no TEXT,
        sort_order INTEGER,
        image_url TEXT,
        image_url_1 TEXT,
        image_url_2 TEXT,
        image_url_3 TEXT,
        image_url_4 TEXT,
        is_active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS categories (
        name TEXT PRIMARY KEY,
        image_url TEXT
    );
    CREATE TABLE IF NOT EXISTS subcategories (
        name TEXT PRIMARY KEY,
        category_name TEXT,
        image_url TEXT,
        FOREIGN KEY(category_name) REFERENCES categories(name)
    );
    CREATE TABLE IF NOT EXISTS sub_subcategories (
        name TEXT PRIMARY KEY,
        subcategory_name TEXT,
        image_url TEXT,
        FOREIGN KEY(subcategory_name) REFERENCES subcategories(name)
    );
    CREATE TABLE IF NOT EXISTS stock (
        sku TEXT PRIMARY KEY,
        stock_qty INTEGER NOT NULL DEFAULT 0,
        last_synced_at TEXT
    );
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY,
        order_number TEXT UNIQUE NOT NULL,
        customer_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        export_status TEXT NOT NULL DEFAULT 'exported',
        order_status TEXT NOT NULL DEFAULT 'submitted',
        submitted_by TEXT,
        assigned_user_id INTEGER,
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    );
    CREATE TABLE IF NOT EXISTS reserved_stock (
        sku TEXT PRIMARY KEY,
        reserved_qty INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY,
        order_id INTEGER NOT NULL,
        sku TEXT NOT NULL,
        title_snapshot TEXT NOT NULL,
        price_snapshot REAL NOT NULL,
        qty INTEGER NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id)
    );
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        role TEXT DEFAULT 'user',
        password TEXT NOT NULL,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS drafts (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        items_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    );
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        entity TEXT NOT NULL,
        details TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        audience_role TEXT NOT NULL DEFAULT 'all',
        priority TEXT NOT NULL DEFAULT 'info',
        action_url TEXT,
        expires_at TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS notification_reads (
        id INTEGER PRIMARY KEY,
        notification_id INTEGER NOT NULL,
        reader_name TEXT NOT NULL,
        read_at TEXT NOT NULL,
        UNIQUE(notification_id, reader_name),
        FOREIGN KEY(notification_id) REFERENCES notifications(id)
    );
    """
    with get_db(db_path) as conn:
        conn.executescript(schema)
        ensure_column(conn, "products", "price_cash", "REAL")
        ensure_column(conn, "products", "price_credit", "REAL")
        ensure_column(conn, "products", "image_url_1", "TEXT")
        ensure_column(conn, "products", "image_url_2", "TEXT")
        ensure_column(conn, "products", "image_url_3", "TEXT")
        ensure_column(conn, "products", "image_url_4", "TEXT")
        ensure_column(conn, "products", "sub_subcategory", "TEXT")
        ensure_column(conn, "products", "mfr_no", "TEXT")
        ensure_column(conn, "products", "sort_order", "INTEGER")
        ensure_column(conn, "customers", "last_visited_at", "TEXT")
        ensure_column(conn, "customers", "phone_code", "TEXT")
        ensure_column(conn, "customers", "email", "TEXT")
        ensure_column(conn, "customers", "longitude", "TEXT")
        ensure_column(conn, "customers", "latitude", "TEXT")
        ensure_column(conn, "customers", "city", "TEXT")
        ensure_column(conn, "customers", "state", "TEXT")
        ensure_column(conn, "customers", "country", "TEXT")
        ensure_column(conn, "customers", "zip_code", "TEXT")
        ensure_column(conn, "customers", "buyer_group", "TEXT")
        ensure_column(conn, "customers", "app_user", "INTEGER")
        ensure_column(conn, "customers", "priority_flag", "TEXT")
        ensure_column(conn, "customers", "outstanding_balance", "REAL")
        ensure_column(conn, "users", "password", "TEXT")
        ensure_column(conn, "users", "role", "TEXT")
        ensure_column(conn, "orders", "order_status", "TEXT")
        ensure_column(conn, "orders", "submitted_by", "TEXT")
        ensure_column(conn, "orders", "assigned_user_id", "INTEGER")
        ensure_column(conn, "orders", "remarks", "TEXT")
        default_settings = [
            ("product_view", "grid"),
            ("reservation_mode", "on"),
            ("allow_oversell", "off"),
            ("show_stock_to_customers", "on"),
            ("low_stock_threshold", "5"),
            ("currency_symbol", "SAR"),
        ]
        for key, value in default_settings:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
                (key, value),
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_products_subcategory ON products(subcategory)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_products_sub_subcategory ON products(sub_subcategory)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email) "
            "WHERE email IS NOT NULL AND email <> ''"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_drafts_customer ON drafts(customer_id)"
        )
        conn.commit()


def ensure_column(conn, table, column, column_type):
    columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
    column_names = {row["name"] for row in columns}
    if column not in column_names:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def get_setting(key, default=None):
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()


def now_iso():
    return datetime.utcnow().isoformat()
