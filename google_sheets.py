import os
from datetime import datetime

import gspread
from gspread.exceptions import WorksheetNotFound

from db import get_db, now_iso


def get_gspread_client():
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_path or not os.path.exists(creds_path):
        return None
    return gspread.service_account(filename=creds_path)


def sync_stock_from_sheet():
    client = get_gspread_client()
    if client is None:
        return False, "Missing Google service account credentials."

    sheet_id = os.getenv("STOCK_SHEET_ID")
    tab_name = os.getenv("STOCK_SHEET_TAB_NAME", "Stock")
    if not sheet_id:
        return False, "Missing STOCK_SHEET_ID."

    worksheet = client.open_by_key(sheet_id).worksheet(tab_name)
    rows = worksheet.get_all_values()
    if not rows:
        return True, "No stock rows found."

    updated = 0
    now = now_iso()
    with get_db() as conn:
        for row in rows[1:]:
            if len(row) < 2:
                continue
            sku = row[0].strip()
            if not sku:
                continue
            try:
                qty = int(row[1])
            except ValueError:
                qty = 0
            product = conn.execute("SELECT sku FROM products WHERE sku = ?", (sku,)).fetchone()
            if not product:
                print(f"Stock sync: SKU not found in products: {sku}")
                continue
            conn.execute(
                "INSERT INTO stock (sku, stock_qty, last_synced_at) VALUES (?, ?, ?) "
                "ON CONFLICT(sku) DO UPDATE SET stock_qty = excluded.stock_qty, last_synced_at = excluded.last_synced_at",
                (sku, qty, now),
            )
            updated += 1
        conn.commit()
    return True, f"Stock sync complete. Updated {updated} rows."


def get_orders_worksheet(client, sheet_id):
    spreadsheet = client.open_by_key(sheet_id)
    month_label = datetime.utcnow().strftime("%b %Y")
    try:
        worksheet = spreadsheet.worksheet(month_label)
    except WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=month_label, rows=1000, cols=13)
        worksheet.append_row(
            [
                "Order Number",
                "Timestamp",
                "Customer",
                "SKU",
                "Qty",
                "Price",
                "Remarks",
            ],
            value_input_option="USER_ENTERED",
        )
    return worksheet


def export_order_rows(order_number, customer_name, rows, remarks=""):
    client = get_gspread_client()
    if client is None:
        return False, "Missing Google service account credentials."

    sheet_id = os.getenv("ORDERS_SHEET_ID")
    if not sheet_id:
        return False, "Missing ORDERS_SHEET_ID."

    worksheet = get_orders_worksheet(client, sheet_id)
    payload = []
    timestamp = datetime.utcnow().isoformat()
    for row in rows:
        payload.append(
            [
                order_number,
                timestamp,
                customer_name,
                row["sku"],
                row["qty"],
                row["price"],
                remarks,
            ]
        )
    if payload:
        worksheet.append_rows(payload, value_input_option="USER_ENTERED")
    return True, "Exported."


def retry_failed_exports():
    with get_db() as conn:
        orders = conn.execute(
            "SELECT o.id, o.order_number, o.remarks, c.name as customer_name "
            "FROM orders o JOIN customers c ON o.customer_id = c.id "
            "WHERE o.export_status = 'export_failed'"
        ).fetchall()
        if not orders:
            return True, "No failed exports to retry."

        for order in orders:
            items = conn.execute(
                "SELECT sku, qty, price_snapshot as price FROM order_items WHERE order_id = ?",
                (order["id"],),
            ).fetchall()
            rows = [dict(item) for item in items]
            success, message = export_order_rows(
                order["order_number"],
                order["customer_name"],
                rows,
                remarks=order["remarks"] or "",
            )
            if success:
                conn.execute(
                    "UPDATE orders SET export_status = 'exported' WHERE id = ?",
                    (order["id"],),
                )
                conn.commit()
            else:
                return False, message
    return True, "Retry complete."
