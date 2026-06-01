# AllergySafe

RFID 기반 AI 급식 메뉴 알레르기 위험도 자동 판단 시스템입니다.

학생증 또는 RFID 카드가 인식되면 학생 정보와 당일 급식 메뉴를 비교해 알레르기 위험 여부를 판단하고, 관리자 화면에서 학생/급식/로그/AI 분석/운영 상태를 관리할 수 있습니다.

## 핵심 기능

- RFID 급식 체크: 키오스크에서 RFID를 읽고 서버에 스캔 결과를 전송합니다.
- 알레르기 위험 판정: 학생 알레르기 코드와 당일 급식 알레르기 코드를 비교해 안전/위험/미등록 상태를 판단합니다.
- 관리자 대시보드: 학생 수, RFID 등록률, 오늘 급식, 위험 감지, 최근 로그를 한 화면에서 확인합니다.
- 학생관리: 학생 등록, 수정, 삭제, RFID 등록 여부 확인, 알레르기 코드 관리, 시트 기반 대량 등록을 지원합니다.
- 급식관리: 날짜별 급식 메뉴를 등록/수정/삭제하고 알레르기 코드를 관리합니다.
- 급식로그: RFID 스캔 기록, 위험 감지 기록, 미등록 RFID 기록을 확인합니다.
- AI급식추가: 급식표 이미지/엑셀/CSV를 분석해 메뉴와 알레르기 정보를 미리보기 후 저장합니다.
- AI안전도우미: 오늘 급식 기준 위험 브리핑, 학생별 안전계획, 메뉴 코드 점검을 보조합니다.
- 알림센터: 학생 등록, 메뉴 변경, RFID 스캔, AI 작업 완료 같은 운영 이벤트를 확인합니다.
- 시스템 상태: 서버, Google Sheets, AI 기능, RFID 연결, 최근 오류, 최근 AI 작업 상태를 점검합니다.
- 감사 로그: 학생/급식/AI/휴지통 관련 주요 변경 작업을 기록합니다.
- 휴지통: 삭제된 학생과 급식 데이터를 복구하거나 완전삭제합니다.
- 프로필 사진: 관리자 계정 프로필 이미지를 업로드하고 원형 영역에 맞게 자르기/회전 후 저장합니다.

## 화면별 사용 설명

### 관리자 홈

접속 경로: `/admin`

- 오늘 급식 안전 상태와 운영 지표를 요약해서 보여줍니다.
- 학생 수, 알레르기 학생 수, RFID 등록/미등록 수, 오늘 메뉴 수, 위험 가능 메뉴 수, 오늘 스캔 수를 확인합니다.
- 최근 스캔 로그와 AI 안전 상태를 빠르게 확인합니다.
- 상단 검색창에서 학생 또는 메뉴를 검색할 수 있습니다.

### 학생관리

접속 경로: `/student-manage`

- 학생 목록을 조회하고 이름, 학번, RFID, 알레르기 정보로 검색합니다.
- 학생 추가 버튼으로 개별 학생을 등록합니다.
- 수정 버튼으로 이름, 학번, RFID, 알레르기 코드를 수정합니다.
- 선택 삭제로 학생을 휴지통으로 이동합니다.
- 시트 추가 기능으로 여러 학생을 한 번에 등록할 수 있습니다.
- RFID 미등록 학생과 알레르기 보유 학생은 상태 표시로 구분합니다.

### 급식관리

접속 경로: `/menu-manage`

- 날짜별 급식 메뉴를 확인합니다.
- 메뉴명과 알레르기 번호를 등록/수정/삭제합니다.
- 오늘 급식과 이후 급식을 구분해 관리합니다.
- 알레르기 번호는 badge 형태로 표시해 빠르게 확인할 수 있습니다.
- AI급식추가에서 분석한 메뉴를 검토 후 저장하면 이 화면에 반영됩니다.

### 급식로그

접속 경로: `/lunch-log`

- RFID 인식 기록을 날짜와 반 기준으로 확인합니다.
- 안전, 위험, 미등록, 오류 상태를 구분해 보여줍니다.
- 위험 감지 항목은 별도 상태 표시로 강조합니다.
- 오늘 스캔 수, 위험 감지 수, 미등록 RFID 수 같은 운영 지표를 확인합니다.

### AI급식추가

접속 경로: `/admin/meal/upload`

- 급식표 이미지, 엑셀, CSV 파일을 업로드합니다.
- AI가 날짜, 메뉴명, 알레르기 번호를 추출합니다.
- 분석 결과는 바로 저장하지 않고 미리보기 화면에서 사람이 검토합니다.
- 확인이 끝나면 저장 버튼으로 급식관리 데이터에 반영합니다.
- 저장 중 Google Sheets 제한이 발생하면 백그라운드에서 자동 재시도하고 완료 후 알림을 띄웁니다.

### AI안전도우미

접속 경로:

- `/admin/ai-tools`
- `/admin/ai-tools/daily-brief`
- `/admin/ai-tools/student-plan`
- `/admin/ai-tools/menu-review`

주요 기능:

- 오늘 위험 브리핑: 당일 급식과 학생 알레르기 정보를 기반으로 위험 가능성을 요약합니다.
- 학생별 안전계획: 특정 학생을 선택해 대체식/주의 메뉴/현장 조치 안내를 생성합니다.
- 메뉴 코드 점검: 메뉴명과 알레르기 코드가 적절한지 AI가 보조 점검합니다.
- AI는 최종 판단자가 아니라 관리자 판단을 돕는 보조 도구입니다.

### 알림센터

접속 경로: `/notifications`

- RFID 스캔, 학생 등록, 메뉴 등록/수정, AI 분석 완료 같은 이벤트를 확인합니다.
- 사이드바 카테고리와 세부 메뉴에 새 알림 수가 표시됩니다.
- 알림을 클릭하면 관련 화면으로 이동하고 읽음 처리됩니다.

### 시스템 상태

접속 경로: `/system-status`

- 서버 상태, Google Sheets 연결, AI 상태, RFID 상태를 확인합니다.
- 최근 오류와 최근 AI 작업 상태를 확인합니다.
- 배포 후 운영 점검용 화면으로 사용합니다.

### 감사 로그

접속 경로: `/audit-log`

- 학생 추가/수정/삭제, 메뉴 추가/수정/삭제, AI 실행, 휴지통 복구/완전삭제 같은 주요 작업을 기록합니다.
- 작업자, 시간, 경로, 성공/실패 상태를 확인할 수 있습니다.

### 휴지통

접속 경로: `/trash`

- 삭제된 학생과 급식 메뉴를 확인합니다.
- 복구 또는 완전삭제를 수행합니다.
- 완전삭제는 되돌리기 어려운 작업이므로 신중하게 사용합니다.

### 키오스크

접속 경로: `/kiosk`

- RFID 리더가 학생증 또는 카드를 인식합니다.
- 서버의 `/api/kiosk/scan`으로 RFID 값을 전송합니다.
- 서버는 학생 정보, 당일 급식, 알레르기 코드를 기준으로 판정 결과를 반환합니다.
- 키오스크 화면과 동작은 관리자 UI 개편과 분리되어 유지됩니다.

## 주요 API와 동작

- `POST /api/kiosk/scan`: RFID 스캔 결과를 서버로 전송합니다.
- `POST /api/student`: 학생을 추가합니다.
- `POST /api/student/update`: 학생 정보를 수정합니다.
- `POST /api/student/delete-selected`: 선택한 학생을 휴지통으로 이동합니다.
- `POST /api/student/sheet-add`: 학생 대량 추가 데이터를 미리보기로 변환합니다.
- `POST /api/student/sheet-confirm`: 학생 대량 추가를 확정합니다.
- `POST /api/menu`: 급식 메뉴를 추가합니다.
- `POST /api/menu/group-update`: 날짜별 급식 메뉴 묶음을 수정합니다.
- `POST /api/menu/delete-selected`: 선택한 급식 메뉴를 휴지통으로 이동합니다.
- `POST /admin/meal/analyze`: 급식표 파일을 AI/OCR로 분석합니다.
- `POST /admin/meal/save`: 분석된 급식 메뉴를 저장합니다.
- `POST /api/meal/save-async`: AI급식 저장을 백그라운드 작업으로 등록합니다.
- `GET /api/admin/background-jobs`: 백그라운드 작업 상태를 조회합니다.
- `POST /api/ai/safety-plan`: 학생별 안전계획을 생성합니다.
- `POST /api/ai/daily-brief`: 오늘 급식 위험 브리핑을 생성합니다.
- `POST /api/ai/menu-review`: 메뉴 알레르기 코드 점검을 수행합니다.
- `GET /api/admin/system-status`: 시스템 상태를 JSON으로 조회합니다.
- `GET /api/admin/audit-log`: 감사 로그를 JSON으로 조회합니다.

## 프로젝트 구조

```text
school-allergy-check/
├─ admin/       관리자 Flask 서버 구현
├─ kiosk/       Raspberry Pi RFID 키오스크 클라이언트
├─ core/        공통 도메인/Google Sheets 유틸리티
├─ services/    AI, OCR, Sheets 연동 서비스
├─ config/      설정 예시 파일
├─ data/        알레르기 사전 등 정적 데이터
├─ docs/        배포, 보안, 구조 문서
├─ scripts/     실행/배포 보조 스크립트
├─ static/      CSS, JS, 이미지, 프로필 사진 등 정적 파일
├─ templates/   Flask/Jinja 화면 템플릿
├─ uploads/     업로드 파일 저장 위치
├─ runtime/     로그, pid, 임시 실행 파일 위치
├─ app_admin.py 루트 호환 관리자 실행 파일
├─ app_kiosk.py 루트 호환 키오스크 실행 파일
├─ wsgi.py      Render/Gunicorn 진입점
└─ render.yaml  Render 배포 설정
```

자세한 구조는 `docs/PROJECT_STRUCTURE.md`를 참고하세요.

## 로컬 실행

1. `config/local_secrets.example.bat`를 `config/local_secrets.bat`로 복사합니다.
2. Google Sheets ID, API 키, 토큰 등 로컬 비밀값을 채웁니다.
3. Google 서비스 계정 파일을 `config/service_account.json`에 둡니다.
4. 아래 명령 중 하나로 실행합니다.

```bat
server_gui.bat
```

```powershell
python app_admin.py
```

키오스크 클라이언트만 실행할 때:

```powershell
python app_kiosk.py
```

## Render 배포

권장 시작 명령:

```bash
gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120
```

빌드 명령:

```bash
pip install -r requirements.txt
```

헬스 체크:

```text
/health
```

자세한 배포 방법은 `docs/DEPLOYMENT.md`를 참고하세요.

## 필요한 비밀 설정

배포 환경에는 다음 값을 설정합니다.

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
- `SERVICE_ACCOUNT_JSON_B64` 또는 `SERVICE_ACCOUNT_JSON`

다음 파일은 GitHub에 올리면 안 됩니다.

- `config/local_secrets.bat`
- `config/service_account.json`
- `.env`, `.env.*`
- Google service account JSON
- OpenAI API Key
- ngrok token
- `runtime/`
- `uploads/`
- 생성된 Raspberry Pi 배포 번들

## 버전별 변경 내역

### v5.3.1.0

- Gentelella v4 스타일을 참고해 관리자 UI를 대시보드형 구조로 개편했습니다.
- 공통 관리자 레이아웃, 사이드바, 상단바, 카드, 테이블, 배지, 차트 스타일을 정리했습니다.
- 관리자 홈, 학생관리, 급식관리, 급식로그, AI급식추가, AI안전도우미, 휴지통 화면을 새 UI에 맞게 재구성했습니다.
- 알림센터, 시스템 상태 페이지, 감사 로그 화면을 추가했습니다.
- AI급식 저장과 학생 대량 등록 일부 작업을 백그라운드 재시도 방식으로 보강했습니다.
- 작업 완료 시 우측 상단 알림과 사이드바 new/count 표시가 뜨도록 개선했습니다.
- 관리자 프로필 사진 업로드, 원형 크롭, 회전, 저장 기능을 추가했습니다.
- 다크모드, 축소 사이드바, 스크롤바, 글꼴/굵기 등 UI 세부 스타일을 다듬었습니다.
- 관리자 내부 역할 분리는 제거하고, 관리자 계정은 동일한 관리자 권한으로 동작하도록 정리했습니다.
- `/kiosk` 체크시스템은 기존 동작을 유지했습니다.

### v5.2.1.0

- 기능 변경 없이 프로젝트 구조를 역할별 폴더로 정리했습니다.
- 관리자 서버는 `admin/`, 키오스크/RFID는 `kiosk/`, 공통 로직은 `core/`, AI/OCR/Sheets 로직은 `services/`로 분리했습니다.
- 루트의 `app_admin.py`, `app_kiosk.py`, `server_gui.py`는 기존 실행 경로가 깨지지 않도록 호환 launcher로 유지했습니다.
- `.gitignore`, `.dockerignore`를 정리해 비밀 파일, 업로드, 런타임 로그, 캐시, 배포 번들이 Git에 포함되지 않도록 했습니다.
- `docs/PROJECT_STRUCTURE.md`, `docs/DEPLOYMENT.md`, `docs/SECURITY_DEPLOYMENT.md`, `docs/AI_SETUP.md` 문서를 정리했습니다.
- Render 실행 명령과 로컬 실행 방식이 유지되도록 `wsgi.py`와 경로를 점검했습니다.

### v5.1.1.0

- v5 구조 정리 전 현재 데모 상태를 보존한 기준 브랜치입니다.
- 관리자 서버, 학생/급식 관리, RFID 체크, AI 기능의 기존 데모 동작을 유지합니다.
- 이후 v5.2 구조 정리와 v5.3 UI 개편의 기준점으로 사용합니다.

### v4.1.1.0

- v5 이전 데모 보존용으로 사용했던 기준 버전입니다.
- 현재는 v5.1.1.0이 데모 기준 역할을 대신합니다.

## 개발 원칙

- Flask/Jinja 구조를 유지합니다.
- React, Tailwind, Vite 같은 별도 프론트엔드 빌드 구조로 바꾸지 않습니다.
- Render에서는 Flask static 기반으로 바로 배포되도록 유지합니다.
- 기존 라우트/API/form name/input id는 가능한 유지합니다.
- `/kiosk`는 관리자 UI 개편과 분리해 안정성을 우선합니다.
- 비밀 파일, 업로드 파일, 런타임 파일은 Git에 포함하지 않습니다.
