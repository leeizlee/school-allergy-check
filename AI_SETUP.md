# AI Setup

## Install Packages

```powershell
pip install -r requirements.txt
```

## Local Secrets

Copy the example file and fill in real values:

```powershell
copy config\local_secrets.example.bat config\local_secrets.bat
```

Required local values:

```bat
set "OPENAI_API_KEY=replace-with-openai-api-key"
set "FLASK_SECRET_KEY=replace-with-a-long-random-secret"
set "KIOSK_SCAN_API_TOKEN=replace-with-a-long-random-token"
```

Google Sheets can use the local service account file:

```bat
set "SERVICE_ACCOUNT_JSON_FILE=config\service_account.json"
```

## OCR

Meal image OCR now uses OpenAI vision OCR through `services/ocr_service.py`.
Tesseract and PaddleOCR are no longer required for the current deployment path.

Optional model override:

```bat
set "OPENAI_OCR_MODEL=gpt-4.1-mini"
```

## Run Locally

```bat
server_gui.bat
```

or:

```powershell
python app_admin.py
```

## Safety Notes

- AI output is a draft for review, not the final safety decision.
- Do not commit `config/local_secrets.bat`, `config/service_account.json`, `.env`, or generated deployment zips.
- Rotate any API token that was ever uploaded or shared.
