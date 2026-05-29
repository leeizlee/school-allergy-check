# School Allergy Check

Flask-based school meal allergy management and RFID kiosk integration.

## Main Components

- `app_admin.py`: admin web server, student/menu management, AI helpers, kiosk scan API
- `app_kiosk.py`: Raspberry Pi RFID kiosk client
- `core/`: shared domain and Google Sheet helper logic
- `services/`: AI, OCR, and sheet import helpers
- `scripts/build_pi_bundle.ps1`: creates the Raspberry Pi deployment bundle
- `render.yaml`: Render deployment blueprint

## Local Run

1. Copy `config/local_secrets.example.bat` to `config/local_secrets.bat`.
2. Fill in local secrets and Google Sheet IDs.
3. Place the Google service account file at `config/service_account.json`.
4. Run:

```bat
server_gui.bat
```

or:

```powershell
python app_admin.py
```

## Deployment

See `DEPLOYMENT.md`.

Do not commit local secret files, service account JSON, uploads, runtime logs, or generated Raspberry Pi bundles.
