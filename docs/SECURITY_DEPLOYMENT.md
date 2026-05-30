# Security Deployment Notes

## Do not commit secrets

Keep these files out of GitHub:

- `config/local_secrets.bat`
- `config/service_account.json`
- `deploy/raspberry_pi/kiosk_secrets.env`
- `deploy/*.zip`
- `.env`
- runtime logs and upload files

Use these templates instead:

- `.env.example`
- `config/local_secrets.example.bat`
- `config/service_account.example.json`

## Required production environment variables

Set these on the hosting platform before running with `APP_ENV=production`:

- `FLASK_SECRET_KEY`
- `KIOSK_SCAN_API_TOKEN`
- `DEFAULT_STUDENT_PASSWORD`
- `SERVICE_ACCOUNT_JSON`
- `SERVICE_ACCOUNT_JSON_B64`
- `OPENAI_API_KEY`
- `MENU_SHEET_ID`
- `STUDENT_SHEET_ID`
- `LOGIN_SHEET_ID`
- `LOG_SHEET_ID`

## Password storage

New and reset passwords are stored as Werkzeug password hashes.
Existing plain-text passwords still work once, then are upgraded to hashes on successful login.

## Kiosk token

The Raspberry Pi kiosk must send the same `KIOSK_SCAN_API_TOKEN` as the admin server.
For local builds, put that value in `config/local_secrets.bat`; `scripts/build_pi_bundle.ps1`
copies it into `deploy/raspberry_pi/kiosk_secrets.env`.

The generated `start_kiosk.sh` loads `kiosk_secrets.env` and refuses to start if the token is not set.
The generated Raspberry Pi zip is a private deployment artifact because it can contain this token.

When the admin server has a stable HTTPS address, set `ADMIN_SERVER_URL` on the Raspberry Pi to that URL.

## Important rotation note

If any real API token or service account file was ever copied into a GitHub repository or shared in chat/logs, revoke it and create a new one before deployment.
