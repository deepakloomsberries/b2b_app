# B2B Order App

A self-hosted B2B order capture app built with Flask, SQLite, and optional Google Sheets integration.

## Features

- Customer selection and quick order creation
- Product catalogue upload via CSV
- Category/subcategory image management (200×200 px recommended)
- Stock sync from Google Sheets
- Order export to Google Sheets (per-month worksheets)
- PDF and Excel order export
- Grid/list view toggle per user session
- Review order page with item removal and remarks
- Draft orders (saved carts)
- Admin panel: user management, notifications, audit logs
- Role-based access: `admin`, `warehouse`, `user`
- Up to 4 product images per SKU
- Customer visit marking and location fields
- PWA support (installable on mobile)

## Setup

### 1. Create a virtual environment

```bash
python3.10 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

| Variable | Description |
|---|---|
| `FLASK_SECRET_KEY` | Long random string for session signing. Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_USERNAME` | Username for the initial admin account (default: `admin`) |
| `ADMIN_PASSWORD` | Password for the initial admin account. **Required** — set before first run |

Google Sheets variables are only needed if you use the stock sync or order export features.

### 4. Run the app

```bash
python app.py
```

The app runs at `http://0.0.0.0:8000`.

On first start, if no admin user exists, a default admin account is created using `ADMIN_USERNAME` and `ADMIN_PASSWORD` from your `.env`. If `ADMIN_PASSWORD` is not set, a random password is generated and printed to stdout — copy it before the output scrolls away.

## Authentication

All routes require login. Users are managed via the Admin panel (`/admin`).

Roles:
- `admin` — full access including admin panel
- `warehouse` — order and stock management
- `user` — order creation and catalogue browsing

## CSV Catalogue Format

Upload a CSV to replace the existing catalogue. Required columns:

```
sku, title, price, cash_price, credit_price, category, subcategory,
image_url, image_url_1, image_url_2, image_url_3, image_url_4,
category_image_url, subcategory_image_url
```

See `sample_data/catalogue_sample.csv` for an example.

## Stock Sync (Cron)

Run the stock sync script on a schedule to pull quantities from Google Sheets:

```bash
*/10 * * * * /path/to/venv/bin/python /path/to/project/scripts/stock_sync.py
```

The stock sheet must have SKU in column A and quantity in column B, with a header row.

## Running as a systemd Service

```ini
[Unit]
Description=B2B Order App
After=network.target

[Service]
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/python /path/to/project/app.py
Restart=always
EnvironmentFile=/path/to/project/.env

[Install]
WantedBy=multi-user.target
```

## Security Recommendations

- Set a strong, unique `FLASK_SECRET_KEY` and `ADMIN_PASSWORD` before first run.
- Run behind a reverse proxy (nginx, Caddy) with HTTPS enabled.
- Restrict network access with a firewall or VPN if this is an internal tool.
- Do not enable `FLASK_DEBUG=1` in production.
- The `.env` file and `*.db` database files are excluded from version control by `.gitignore` — keep them out of any public repository.

## PWA / Mobile Install

- On iOS, use Safari → Share → Add to Home Screen.
- Chrome on iPhone does not show a native install prompt.
- To update the app icon, replace `static/icons/app-icon.svg` and bump the cache version in `static/js/service-worker.js`.
