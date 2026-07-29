import os
from datetime import datetime

import gspread
from gspread.exceptions import WorksheetNotFound
from requests.adapters import HTTPAdapter

from db import get_db, now_iso

# Default (connect, read) timeouts in seconds for all Google API calls. gspread
# and requests set no timeout by default, so a stalled network path (for
# example a black-holed IPv6 route) blocks forever instead of failing. These
# bound the wait so a failure is reported quickly and can be retried.
DEFAULT_CONNECT_TIMEOUT = 10
DEFAULT_READ_TIMEOUT = 30


class _TimeoutHTTPAdapter(HTTPAdapter):
    """A requests adapter that applies a default timeout to any request that
    doesn't specify one, so no Google API call can hang indefinitely."""

    def __init__(self, *args, timeout=None, **kwargs):
        self._timeout = timeout
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self._timeout
        return super().send(request, **kwargs)


def _apply_timeout(client, timeout):
    """Mount the timeout adapter on the client's underlying requests session.
    Works across gspread versions (Client.session in 5.x, Client.http_client.
    session in 6.x); a no-op if no session is found."""
    session = getattr(client, "session", None) or getattr(
        getattr(client, "http_client", None), "session", None
    )
    if session is not None:
        adapter = _TimeoutHTTPAdapter(timeout=timeout)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
    return client


def _sheet_safe(value):
    """Prefix values that could be read as spreadsheet formulas (=, +, -, @) so
    exported rows can't execute formulas when opened with USER_ENTERED input."""
    text = "" if value is None else str(value)
    if text[:1] in ("=", "+", "-", "@"):
        return "'" + text
    return text


def get_gspread_client():
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_path or not os.path.exists(creds_path):
        return None
    client = gspread.service_account(filename=creds_path)
    connect_timeout = float(os.getenv("SHEETS_CONNECT_TIMEOUT", DEFAULT_CONNECT_TIMEOUT))
    read_timeout = float(os.getenv("SHEETS_READ_TIMEOUT", DEFAULT_READ_TIMEOUT))
    return _apply_timeout(client, (connect_timeout, read_timeout))


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

    payload = []
    timestamp = datetime.utcnow().isoformat()
    for row in rows:
        payload.append(
            [
                _sheet_safe(order_number),
                timestamp,
                _sheet_safe(customer_name),
                _sheet_safe(row["sku"]),
                row["qty"],
                row["price"],
                _sheet_safe(remarks),
            ]
        )

    # Any Google Sheets API / network failure (rate limits, permission errors,
    # timeouts, transient 5xx, worksheet races) raises here. Convert it into a
    # clean (False, message) result so the caller can mark the order as
    # export_failed and a later retry can pick it up, instead of the exception
    # propagating and leaving the order stuck in an inconsistent state.
    try:
        worksheet = get_orders_worksheet(client, sheet_id)
        if payload:
            worksheet.append_rows(payload, value_input_option="USER_ENTERED")
    except Exception as exc:  # noqa: BLE001 - report any failure to the caller
        return False, f"Google Sheets export failed: {exc}"
    return True, "Exported."


def retry_failed_exports():
    with get_db() as conn:
        # Retry anything that is not confirmed exported. This includes orders
        # left in 'pending' (export never completed, e.g. the process crashed or
        # the API call raised before status could be updated) as well as
        # 'export_failed'. Restricting to 'export_failed' alone would silently
        # skip orders stuck mid-export, which is why a retry could report
        # success without ever re-sending the affected order.
        orders = conn.execute(
            "SELECT o.id, o.order_number, o.remarks, c.name as customer_name "
            "FROM orders o JOIN customers c ON o.customer_id = c.id "
            "WHERE o.export_status != 'exported' "
            "ORDER BY o.id"
        ).fetchall()
        if not orders:
            return True, "No pending or failed exports to retry."

        succeeded = 0
        failures = []
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
                succeeded += 1
            else:
                # Keep the order flagged so it stays visible for the next retry,
                # and continue with the remaining orders instead of aborting the
                # whole batch on the first failure.
                conn.execute(
                    "UPDATE orders SET export_status = 'export_failed' WHERE id = ?",
                    (order["id"],),
                )
                failures.append(f"{order['order_number']}: {message}")
            conn.commit()

    if failures:
        detail = "; ".join(failures)
        return False, f"Exported {succeeded} order(s); {len(failures)} still failing: {detail}"
    return True, f"Retry complete. Exported {succeeded} order(s)."
