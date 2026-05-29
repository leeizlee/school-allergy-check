# Deployment Guide

## What goes to GitHub

Commit the application source and templates:

- `app_admin.py`
- `app_kiosk.py`
- `core/`
- `services/`
- `static/`
- `data/`
- `scripts/`
- `requirements.txt`
- `wsgi.py`
- `Procfile`
- `render.yaml`
- `.env.example`
- `config/*.example.*`

Do not commit local secrets, runtime files, uploads, or generated Raspberry Pi bundles.
Those are already covered by `.gitignore`.

## Admin server

Recommended start command:

```bash
gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120
```

Build command:

```bash
pip install -r requirements.txt
```

Health check path:

```text
/health
```

## Required environment variables

Set these on the hosting platform:

- `APP_ENV=production`
- `FLASK_SECRET_KEY`
- `KIOSK_SCAN_API_TOKEN`
- `DEFAULT_STUDENT_PASSWORD`
- `OPENAI_API_KEY`
- `MENU_SHEET_ID`
- `STUDENT_SHEET_ID`
- `LOGIN_SHEET_ID`
- `LOG_SHEET_ID`
- `PUBLIC_ADMIN_URL`
- `RFID_DASHBOARD_URL`

For the Google service account, use one of these:

- `SERVICE_ACCOUNT_JSON_B64`: base64-encoded service account JSON
- `SERVICE_ACCOUNT_JSON`: full service account JSON string or a local file path
- `SERVICE_ACCOUNT_JSON_FILE`: local file path, mainly for Windows/local development

For Render, `render.yaml` marks secret values with `sync: false`, so Render asks for them in the dashboard during setup.

## Encoding the Google service account JSON

PowerShell:

```powershell
[Convert]::ToBase64String([System.IO.File]::ReadAllBytes("config\service_account.json"))
```

Put the printed value into `SERVICE_ACCOUNT_JSON_B64`.

## Raspberry Pi kiosk bundle

Create the Pi bundle locally:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_pi_bundle.ps1
```

The script reads `KIOSK_SCAN_API_TOKEN` from `config/local_secrets.bat` and writes it to:

```text
deploy/raspberry_pi/kiosk_secrets.env
```

That file and the generated zip are private deployment artifacts. Do not upload them to GitHub.

## After deployment

1. Open `/health` and confirm it returns JSON.
2. Open `/admin` and log in.
3. Set the Raspberry Pi `ADMIN_SERVER_URL` or discovery URL to the new HTTPS server address.
4. Scan one registered RFID and one unregistered/wrong RFID.
5. Confirm the admin RFID check screen still receives unregistered scans.
