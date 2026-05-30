# Project Structure

이 문서는 기능을 바꾸지 않고 역할별로 정리한 현재 파일 구조를 설명합니다.

```text
school-allergy-check/
├─ admin/
│  ├─ __init__.py
│  └─ app_admin.py
├─ kiosk/
│  ├─ __init__.py
│  └─ app_kiosk.py
├─ core/
│  ├─ __init__.py
│  ├─ admin_domain.py
│  └─ admin_sheet_utils.py
├─ services/
│  ├─ __init__.py
│  ├─ ai_service.py
│  ├─ ocr_service.py
│  └─ sheets_service.py
├─ config/
│  ├─ local_secrets.example.bat
│  └─ service_account.example.json
├─ data/
│  └─ allergy_dict.json
├─ docs/
│  ├─ AI_SETUP.md
│  ├─ DEPLOYMENT.md
│  ├─ PROJECT_STRUCTURE.md
│  └─ SECURITY_DEPLOYMENT.md
├─ scripts/
│  ├─ __init__.py
│  ├─ build_pi_bundle.ps1
│  ├─ build_render_env.ps1
│  ├─ server_gui.py
│  └─ update_github_pages_redirect.py
├─ static/
│  ├─ logoimage_dark.png
│  └─ logoimage_white.png
├─ uploads/
├─ runtime/
├─ app_admin.py
├─ app_kiosk.py
├─ server_gui.py
├─ server_gui.bat
├─ wsgi.py
├─ render.yaml
├─ Procfile
├─ requirements.txt
└─ latest-url.json
```

## 역할별 정리

- `admin/`: 관리자 Flask 서버의 실제 구현입니다. Render는 `wsgi.py`를 통해 이 앱을 불러옵니다.
- `kiosk/`: Raspberry Pi RFID 키오스크 클라이언트 구현입니다.
- `core/`: 관리자 기능에서 공유하는 도메인 처리와 Google Sheet 유틸리티입니다.
- `services/`: AI, OCR, Google Sheets 연동 서비스입니다.
- `config/`: 설정 예시 파일만 둡니다. 실제 비밀 파일은 Git에 포함하지 않습니다.
- `scripts/`: 배포 번들 생성, 로컬 GUI 실행, GitHub Pages URL 갱신 같은 실행 보조 스크립트입니다.
- `static/`: 정적 이미지 파일입니다.
- `uploads/`: 업로드 파일이 생기는 위치입니다. 실제 업로드 파일은 Git 추적 대상에서 제외합니다.
- `runtime/`: 실행 중 생성되는 pid, log, ngrok URL 같은 임시 런타임 파일 위치입니다. Git 추적 대상에서 제외합니다.
- `docs/`: 배포, AI 설정, 보안, 구조 문서입니다.

## 호환 실행 파일

루트의 `app_admin.py`, `app_kiosk.py`, `server_gui.py`는 기존 실행 방식이 깨지지 않도록 남겨둔 얇은 launcher입니다.

- `python app_admin.py`
- `python app_kiosk.py`
- `server_gui.bat`
- `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`

위 실행 방식은 계속 유지됩니다.

## Git 제외 대상

다음 파일은 민감정보 또는 실행 중 생성물이라 Git에 포함하지 않습니다.

- `config/local_secrets.bat`
- `config/service_account.json`
- `kiosk_secrets.env`
- `.env`, `.env.*`
- `runtime/`
- `uploads/*` (`uploads/.gitkeep` 제외)
- `deploy/raspberry_pi/`, `deploy/raspberry_pi_onefile/`, `deploy/*.zip`
- `__pycache__/`, `*.pyc`, 로그, 임시 파일, 테스트 캐시
