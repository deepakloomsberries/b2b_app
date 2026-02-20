import os
import sys

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from google_sheets import sync_stock_from_sheet  # noqa: E402
from db import init_db  # noqa: E402


def main():
    load_dotenv()
    init_db()
    success, message = sync_stock_from_sheet()
    if success:
        print(message)
    else:
        print(message)
        sys.exit(1)


if __name__ == "__main__":
    main()
