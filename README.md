# Ghausia ERP

A simple, production-ready ERP for small cloth-processing factories (Ghausia textile factory). Built with Python, Django, SQLite, Bootstrap 5, and server-rendered templates. Designed for non-technical factory staff with manual data entry, audit history, and automatic calculations.

## Purpose

Track cloth from vendor receiving through all production stages:

**Vendor Receiving → Singeing → Dyeing → Six Chamber → Calender → Comfort → Finished Stock**

The same production lot number connects every stage. The system also tracks chemicals, dyes, mixtures, maintenance materials, machine breakdowns, electricity readings, material stock, and shrinkage/loss calculations.

## Features

- Server-rendered Django templates with Bootstrap 5 UI
- Role-based access (Administrator, Supervisor, Data Entry User)
- Audit fields on all important records (created/updated/cancelled by whom and when)
- Cancel instead of delete — records are never permanently removed via the UI
- Automatic document numbering (receipts, lots, batches, transactions, maintenance jobs)
- Material stock calculated from transactions (not manually edited)
- Production lot tracking with stage-wise loss and shrinkage
- Maintenance repeat-failure tracking (days since previous breakdown)
- Daily electricity meter readings with automatic unit calculation
- Spreadsheet-style multi-row entry and Excel (.xlsx) import/export for receiving and purchases
- Simple dashboard with counts (no charts or complex reports)

## Technology Stack

| Component | Choice |
|-----------|--------|
| Python | 3.12+ |
| Django | 5.1+ (tested with 6.0) |
| Database | SQLite locally, PostgreSQL on Railway |
| UI | Django templates + Bootstrap 5 |
| Auth | Django built-in |
| Deployment | Waitress (Windows factory PC or Railway) |

**Not used:** React, DRF, Docker, Redis, Celery, barcode systems, APIs.

## Folder Structure

```
├── accounts/          # Home page, users, permissions, tests, seed command
├── audit/             # AuditModel abstract base
├── common/            # Shared forms, views, template tags
├── config/            # Django settings, URLs, admin
├── master_data/       # Vendors, cloth types, employees, machines, materials
├── receiving/         # Cloth receiving
├── production/        # Lots, singeing, dyeing, six chamber, calender, comfort, finished stock
├── inventory/         # Material transactions and stock
├── maintenance/       # Machine maintenance and material usage
├── electricity/       # Meters and daily readings
├── templates/         # HTML templates
├── static/            # CSS
├── logs/              # Application and error logs
├── backups/           # Database backups (via batch script)
├── start.py           # Railway / production start (migrate, static, seed, Waitress)
├── Procfile
├── requirements.txt
├── setup_windows.bat
├── start_windows.bat
└── backup_database.bat
```

## Windows Installation (Recommended)

1. Install [Python 3.12+](https://www.python.org/) — check **"Add Python to PATH"** during install.
2. Copy the project folder to your PC (e.g. `C:\TextileERP`).
3. Double-click **`setup_windows.bat`**.
4. When prompted, create a superuser (or skip and run later).
5. Optional demo data: `python manage.py seed_demo_data`
6. Start the system: double-click **`start_windows.bat`**.

Open **http://127.0.0.1:8000** in your browser.

## Manual Installation (Mac/Linux/Windows)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py seed_demo_data    # optional
python manage.py runserver         # dev only
```

Production-style start (all platforms):

```bash
waitress-serve --listen=0.0.0.0:8000 config.wsgi:application
```

## Deploy on Railway (login from anywhere)

This is the right way to open the ERP from home, the factory, or a phone. Railway gives a public HTTPS URL. Staff still sign in with a username and password; new people are added by an administrator (Users → New user), not by a public sign-up page.

1. Create a Railway project from this repo.
2. Add a **PostgreSQL** plugin/service and attach it so `DATABASE_URL` is set. Do not rely on `db.sqlite3` on Railway — that file is wiped on deploy.
3. Set variables on the web service:

   ```
   SECRET_KEY=<long random string>
   DEBUG=False
   ALLOWED_HOSTS=your-app.up.railway.app
   CSRF_TRUSTED_ORIGINS=https://your-app.up.railway.app
   ```

   If you use a custom domain, add that host to `ALLOWED_HOSTS` and `https://your-domain` to `CSRF_TRUSTED_ORIGINS`.
4. Deploy. The start command (`python start.py`) runs migrations, collects CSS, seeds demo users if they do not already exist, and serves the app.
5. Open `https://your-app.up.railway.app` and sign in. Demo logins stay the same until you change them: `admin` / `admin123`, `supervisor` / `super123`, `dataentry` / `data123`.

Re-deploys do **not** reset passwords that already exist.

Optional: add a Railway volume and set `MEDIA_ROOT` to a path on that volume if you need receipt photos to survive restarts.

## Demo Users (after seed_demo_data)

| Username   | Password  | Role              |
|------------|-----------|-------------------|
| admin      | admin123  | Administrator     |
| supervisor | super123  | Supervisor        |
| dataentry  | data123   | Data Entry User   |

**Change these passwords before production use.**

## User Roles

| Role | Permissions |
|------|-------------|
| **Administrator** | Full access, manage users, master data, edit/cancel records |
| **Supervisor** | View all, add/edit production, cancel records, override stock limits |
| **Data Entry User** | Add records, view records — cannot cancel or manage users |

Assign groups via Django Admin → Users → Groups.

## Allow Other Factory Computers to Connect

1. Find your PC's IP address (`ipconfig` on Windows).
2. Edit `.env`:
   ```
   ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100
   ```
   Replace `192.168.1.100` with your actual IP.
3. Restart the server with `start_windows.bat`.
4. On another PC on the same network, open `http://YOUR-PC-IP:8000`.
5. Allow port 8000 through Windows Firewall if needed.

## Spreadsheet Entry and Excel Import

For fast factory data entry:

### Cloth Receiving

1. Open **Cloth Receiving** → **Spreadsheet Entry** (`/receiving/sheet/`)
2. Fill many rows (Tab between cells; paste from Excel with Ctrl+V / Cmd+V)
3. Leave **Lot / Palli Number** blank to auto-generate
4. Click **Save All Rows**

Or use Excel files:

1. **Download Excel Template**
2. Fill rows in Excel (keep the header row)
3. **Import Excel** and upload the `.xlsx` file

### Material Purchases

1. Open **Material Transactions** → **Purchase Spreadsheet** (`/inventory/purchase/sheet/`)
2. Or download the purchase template, fill it in Excel, and import

Row-level errors are shown if a lot number is duplicated, cloth type/material is unknown, or numbers are invalid.

## Running Tests

```bash
python manage.py test
```

## Database Backup

Double-click **`backup_database.bat`** or manually:

```bash
copy db.sqlite3 backups\db_backup_YYYY-MM-DD.sqlite3
```

## Restore a Backup

1. Stop the server.
2. Replace `db.sqlite3` with your backup file.
3. Restart the server.

## Important Business Rules

- **Production lot numbers** link all stages — created automatically when cloth is received.
- **Material stock** is always calculated from transactions; never edit stock directly.
- **Cancelled records** are excluded from calculations but kept in the database.
- **Output metres > input metres** requires supervisor override.
- **Insufficient material stock** blocks usage unless user is Supervisor or Administrator.
- **Only one active singeing entry** and **one active finished stock record** per lot.
- **Dyeing** allows multiple batches; use **Complete Dyeing Stage** to advance the lot.
- **Electricity**: closing reading must be ≥ opening reading; one active reading per meter per date.

## Common Troubleshooting

| Problem | Solution |
|---------|----------|
| `DisallowedHost` error | Add your IP/hostname to `ALLOWED_HOSTS` in `.env` |
| Login fails on Railway | Set `CSRF_TRUSTED_ORIGINS=https://your-app.up.railway.app` and `DEBUG=False` |
| Cannot login | Run `createsuperuser` or `seed_demo_data` |
| Static files missing | Run `python manage.py collectstatic --noinput` |
| Port 8000 in use | Change port in `start_windows.bat` |
| Database locked | Stop duplicate server instances |
| Insufficient stock | Add purchase entry or ask supervisor to override |

## Design Decisions

- **Time zone** defaults to `Asia/Karachi` — change in `config/settings.py` if needed.
- **Secure cookies** are disabled in DEBUG mode so local HTTP works without HTTPS.
- **Process material usage** for Six Chamber is supported via model but optional in UI (simplest path documented here).
- **User management** is in-app: sign in, then Users → New user. There is no public self-registration.

## License

Internal factory use. Modify as needed for your operation.
