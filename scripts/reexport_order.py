"""Re-export one or more orders to Google Sheets, regardless of their current
export_status.

Use this to recover orders that were wrongly recorded as 'exported' (e.g. the
sheet export raised an error before the status could be corrected), so the
normal "Retry exports" sweep never picks them up.

Usage:
    python scripts/reexport_order.py ORD-20260729-3595 [ORD-... ...]

Each order that exports successfully is marked 'exported'; any that fails is
marked 'export_failed' so it will be retried by the normal sweep too.
"""

import os
import sys

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from google_sheets import export_order_rows  # noqa: E402
from db import get_db, init_db  # noqa: E402


def reexport(order_number):
    with get_db() as conn:
        order = conn.execute(
            "SELECT o.id, o.order_number, o.remarks, c.name AS customer_name "
            "FROM orders o JOIN customers c ON o.customer_id = c.id "
            "WHERE o.order_number = ?",
            (order_number,),
        ).fetchone()
        if order is None:
            return False, f"{order_number}: not found."

        items = conn.execute(
            "SELECT sku, qty, price_snapshot AS price FROM order_items WHERE order_id = ?",
            (order["id"],),
        ).fetchall()
        rows = [dict(item) for item in items]

        success, message = export_order_rows(
            order["order_number"],
            order["customer_name"],
            rows,
            remarks=order["remarks"] or "",
        )
        new_status = "exported" if success else "export_failed"
        conn.execute(
            "UPDATE orders SET export_status = ? WHERE id = ?",
            (new_status, order["id"]),
        )
        conn.commit()
        return success, f"{order_number}: {message}"


def main():
    load_dotenv()
    init_db()

    order_numbers = sys.argv[1:]
    if not order_numbers:
        print("Usage: python scripts/reexport_order.py ORD-... [ORD-... ...]")
        sys.exit(2)

    exit_code = 0
    for order_number in order_numbers:
        success, message = reexport(order_number)
        print(message)
        if not success:
            exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
