from pathlib import Path


path = Path("admin/app_admin.py")
text = path.read_text(encoding="utf-8-sig")


def replace_once(old, new, label):
    global text
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"{label} anchor not found")
    text = text.replace(old, new, 1)


def insert_before(marker, addition, label):
    global text
    if addition.strip() in text:
        return
    if marker not in text:
        raise SystemExit(f"{label} marker not found")
    text = text.replace(marker, addition + marker, 1)


replace_once(
    "from pathlib import Path\n",
    "from pathlib import Path\nfrom zoneinfo import ZoneInfo\n",
    "zoneinfo import",
)

replace_once(
    "from services.ocr_service import OCRServiceError, extract_text\n",
    "from services.email_service import (\n"
    "    build_daily_email,\n"
    "    email_delivery_configured,\n"
    "    is_valid_email,\n"
    "    send_email,\n"
    ")\n"
    "from services.ocr_service import OCRServiceError, extract_text\n",
    "email service import",
)

replace_once(
    "PUBLIC_ADMIN_URL = os.getenv(\"PUBLIC_ADMIN_URL\", \"http://allergy-admin.duckdns.org:5001\")\n",
    "PUBLIC_ADMIN_URL = os.getenv(\"PUBLIC_ADMIN_URL\", \"http://allergy-admin.duckdns.org:5001\")\n"
    "EMAIL_DISPATCH_TOKEN = os.getenv(\"EMAIL_DISPATCH_TOKEN\", \"\").strip()\n"
    "NOTIFICATION_TIMEZONE = os.getenv(\"NOTIFICATION_TIMEZONE\", \"Asia/Seoul\").strip() or \"Asia/Seoul\"\n",
    "email configuration",
)

helper_code = '''

def value_is_enabled(value):
    return safe_str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def ensure_sheet_header(ws, header_name):
    headers = [safe_str(value).strip() for value in ws.row_values(1)]
    wanted = safe_str(header_name).strip().lower()
    for index, header in enumerate(headers, start=1):
        if header.lower() == wanted:
            return index

    column = len(headers) + 1
    ws.update_cell(1, column, header_name)
    _invalidate_sheet_cache(ws)
    return column


def update_cell_by_header_create(ws, row_index, header_name, value):
    column = ensure_sheet_header(ws, header_name)
    ws.update_cell(row_index, column, value)
    _invalidate_sheet_cache(ws)

'''
insert_before("\ndef compact_date_value(value):", helper_code, "notification sheet helpers")

email_context_code = '''

def build_student_email_message(student, date_value):
    context = build_student_ai_context(student, date_value)
    return build_daily_email(
        student_name=safe_str((student or {}).get("name")).strip() or "학생",
        date_value=context["date"],
        menu_names=context["menu_names"],
        allergy_names=context["student_allergy_names"],
        unsafe_menus=context["unsafe_menus"],
        matched_names=context["matched_allergies"],
    )


def notification_dispatch_authorized():
    if not EMAIL_DISPATCH_TOKEN:
        return False
    authorization = safe_str(request.headers.get("Authorization")).strip()
    supplied = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    if not supplied:
        supplied = safe_str(request.headers.get("X-Notification-Token")).strip()
    return bool(supplied) and hmac.compare_digest(supplied, EMAIL_DISPATCH_TOKEN)

'''
insert_before("# =========================\n# 로그인 / 권한\n# =========================", email_context_code, "email context helpers")

replace_once(
    '''            "role": safe_str(r.get("role")).strip().lower(),
            "trash": trash,
''',
    '''            "role": safe_str(r.get("role")).strip().lower(),
            "email": safe_str(r.get("email")).strip(),
            "email_notifications": value_is_enabled(r.get("email_notifications")),
            "notification_time": safe_str(r.get("notification_time")).strip() or "07:30",
            "trash": trash,
''',
    "login notification fields",
)

old_notification_html = '''      <div class="notification-settings">
        <h3>급식 푸시알림 권한</h3>
        <div class="muted">알림 권한 상태를 확인하고, 상태에 맞는 안내를 제공해.</div>
        <div class="notification-status">
          <span id="notificationStatusDot" class="status-dot"></span>
          <span id="notificationStatusText">확인 중...</span>
        </div>
        <div class="row-actions">
          <button id="notificationPermissionButton" class="btn" type="button" onclick="handleNotificationPermission()">알림 상태 확인</button>
          <button id="notificationTestButton" class="btn btn-primary" type="button" onclick="sendNotificationTest()" style="display:none;">테스트 알림 보내기</button>
        </div>
        <div id="notificationHelp" class="notification-help"></div>
      </div>
'''
new_notification_html = '''      <div class="notification-settings">
        <h3>알림센터 수신 설정</h3>
        <div class="muted">등교 전 급식 비교 결과를 푸시알림이나 이메일로 받을 수 있어.</div>

        <div style="margin-top:18px;font-weight:900;">푸시알림</div>
        <div class="notification-status">
          <span id="notificationStatusDot" class="status-dot"></span>
          <span id="notificationStatusText">확인 중...</span>
        </div>
        <div class="row-actions">
          <button id="notificationPermissionButton" class="btn" type="button" onclick="handleNotificationPermission()">알림 상태 확인</button>
          <button id="notificationTestButton" class="btn btn-primary" type="button" onclick="sendNotificationTest()" style="display:none;">푸시 테스트</button>
        </div>
        <div id="notificationHelp" class="notification-help"></div>

        <div style="height:1px;background:#2a2f37;margin:22px 0;"></div>
        <div style="font-weight:900;margin-bottom:12px;">이메일 알림</div>
        <div class="account-row">
          <div class="account-field" style="flex:2 1 320px;">
            <span class="account-label">받을 이메일</span>
            <input type="email" id="studentNotificationEmail" value="{{ notification_email }}" placeholder="student@example.com" autocomplete="email">
          </div>
          <div class="account-field" style="flex:0 1 180px;">
            <span class="account-label">알림 시간</span>
            <input type="time" id="studentNotificationTime" value="{{ notification_time }}">
          </div>
        </div>
        <label style="display:flex;align-items:center;gap:9px;margin-top:14px;font-weight:800;cursor:pointer;">
          <input type="checkbox" id="studentEmailNotifications" style="width:auto;" {% if email_notifications %}checked{% endif %}>
          설정한 시간에 오늘 급식 이메일 받기
        </label>
        <div class="row-actions">
          <button id="emailTestButton" class="btn btn-primary" type="button" onclick="sendEmailTest()" {% if not email_delivery_configured %}disabled{% endif %}>오늘 급식 테스트 이메일</button>
        </div>
        <div id="emailTestResult" class="notification-help">{% if not email_delivery_configured %}서버에 이메일 API 키와 발신 주소를 설정해야 테스트할 수 있어.{% endif %}</div>
      </div>
'''
replace_once(old_notification_html, new_notification_html, "student notification settings UI")

replace_once(
    '''      const newPw = document.getElementById("studentMyPw")?.value.trim() || "";

      const res = await fetch("/api/student/my-account/update", {
''',
    '''      const newPw = document.getElementById("studentMyPw")?.value.trim() || "";
      const notificationEmail = document.getElementById("studentNotificationEmail")?.value.trim() || "";
      const emailNotifications = Boolean(document.getElementById("studentEmailNotifications")?.checked);
      const notificationTime = document.getElementById("studentNotificationTime")?.value || "07:30";

      const res = await fetch("/api/student/my-account/update", {
''',
    "student notification JS fields",
)

replace_once(
    '''          new_pw: newPw,
          allergy_codes: myAllergies
''',
    '''          new_pw: newPw,
          allergy_codes: myAllergies,
          email: notificationEmail,
          email_notifications: emailNotifications,
          notification_time: notificationTime
''',
    "student notification save payload",
)

email_test_js = '''    async function sendEmailTest() {
      const button = document.getElementById("emailTestButton");
      const result = document.getElementById("emailTestResult");
      const email = document.getElementById("studentNotificationEmail")?.value.trim() || "";

      if (!email || !email.includes("@")) {
        if (result) result.textContent = "받을 이메일 주소를 먼저 입력해줘.";
        return;
      }

      if (button) button.disabled = true;
      if (result) result.textContent = "오늘 급식 비교 결과를 이메일로 보내는 중...";
      try {
        const response = await fetch("/api/student/notification/email-test", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({ email })
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.error || "테스트 이메일 발송에 실패했어.");
        }
        if (result) result.textContent = `테스트 이메일 발송 완료 · 상태: ${data.status || "완료"}`;
      } catch (error) {
        if (result) result.textContent = error.message || "테스트 이메일 발송에 실패했어.";
      } finally {
        if (button) button.disabled = false;
      }
    }

'''
insert_before("    function notificationPermissionState() {", email_test_js, "email test javascript")

replace_once(
    '''    login_id = safe_str(session.get("login_id")).strip()
    my_student = get_student_by_student_number(login_id, include_trash=False)

    today_menus = [x for x in get_all_menu_rows() if x["date"] == today_sheet_str()]
''',
    '''    login_id = safe_str(session.get("login_id")).strip()
    my_student = get_student_by_student_number(login_id, include_trash=False)
    login_settings = get_login_by_id(login_id, include_trash=False) or {}

    today_menus = [x for x in get_all_menu_rows() if x["date"] == today_sheet_str()]
''',
    "student home notification settings",
)

replace_once(
    '''        today_menus=today_menus,
        rfid_dashboard_url=RFID_DASHBOARD_URL,
''',
    '''        today_menus=today_menus,
        notification_email=safe_str(login_settings.get("email")).strip(),
        email_notifications=bool(login_settings.get("email_notifications")),
        notification_time=safe_str(login_settings.get("notification_time")).strip() or "07:30",
        email_delivery_configured=email_delivery_configured(),
        rfid_dashboard_url=RFID_DASHBOARD_URL,
''',
    "student template notification settings",
)

replace_once(
    '''    new_pw = safe_str(data.get("new_pw")).strip()
    allergy_codes = data.get("allergy_codes", [])

    if not new_id or not new_name:
''',
    '''    new_pw = safe_str(data.get("new_pw")).strip()
    allergy_codes = data.get("allergy_codes", [])
    email = safe_str(data.get("email")).strip()
    email_notifications = value_is_enabled(data.get("email_notifications"))
    notification_time = safe_str(data.get("notification_time")).strip() or "07:30"

    if email and not is_valid_email(email):
        return jsonify({"ok": False, "error": "이메일 주소 형식을 확인해줘"}), 400
    if email_notifications and not email:
        return jsonify({"ok": False, "error": "이메일 알림을 켜려면 받을 이메일을 입력해야 해"}), 400
    if not re.fullmatch(r"(?:[01]\\d|2[0-3]):[0-5]\\d", notification_time):
        return jsonify({"ok": False, "error": "알림 시간을 다시 선택해줘"}), 400

    if not new_id or not new_name:
''',
    "student notification validation",
)

replace_once(
    '''    if new_pw:
        update_cell_by_header(id_ws, login_row["row_index"], "pw", hash_password(new_pw))

    update_cell_by_headers(student_ws, student_row["row_index"], ["student_number", "student_no"], new_id)
''',
    '''    if new_pw:
        update_cell_by_header(id_ws, login_row["row_index"], "pw", hash_password(new_pw))
    update_cell_by_header_create(id_ws, login_row["row_index"], "email", email)
    update_cell_by_header_create(id_ws, login_row["row_index"], "email_notifications", "1" if email_notifications else "0")
    update_cell_by_header_create(id_ws, login_row["row_index"], "notification_time", notification_time)

    update_cell_by_headers(student_ws, student_row["row_index"], ["student_number", "student_no"], new_id)
''',
    "student notification sheet save",
)

email_routes = '''@app.post("/api/student/notification/email-test")
def api_student_notification_email_test():
    ok, response = require_student()
    if not ok:
        if isinstance(response, str):
            return jsonify({"ok": False, "error": response}), 403
        return jsonify({"ok": False, "error": "로그인이 필요해"}), 401

    if not email_delivery_configured():
        return jsonify({"ok": False, "error": "서버의 이메일 API 설정이 아직 완료되지 않았어"}), 503

    data = request.get_json(silent=True) or {}
    current_id = safe_str(session.get("login_id")).strip()
    login_row = get_login_by_id(current_id, include_trash=False) or {}
    target_email = safe_str(data.get("email") or login_row.get("email")).strip()
    if not is_valid_email(target_email):
        return jsonify({"ok": False, "error": "받을 이메일 주소를 확인해줘"}), 400

    student = get_student_by_student_number(current_id, include_trash=False)
    if not student:
        return jsonify({"ok": False, "error": "학생 정보를 찾지 못했어"}), 404

    try:
        message = build_student_email_message(student, today_sheet_str())
        email_id = send_email(target_email, message)
    except Exception as exc:
        logger.exception("급식 테스트 이메일 발송 실패")
        return jsonify({"ok": False, "error": safe_str(exc) or "이메일 발송에 실패했어"}), 502

    return jsonify({
        "ok": True,
        "email_id": email_id,
        "status": message.get("status"),
    })


@app.post("/api/notifications/email-dispatch")
def api_notification_email_dispatch():
    if not notification_dispatch_authorized():
        return jsonify({"ok": False, "error": "알림 발송 토큰이 올바르지 않아"}), 401
    if not email_delivery_configured():
        return jsonify({"ok": False, "error": "이메일 API 설정이 완료되지 않았어"}), 503

    data = request.get_json(silent=True) or {}
    try:
        local_now = datetime.now(ZoneInfo(NOTIFICATION_TIMEZONE))
    except Exception:
        logger.warning("알림 시간대 설정을 읽지 못해 Asia/Seoul을 사용해")
        local_now = datetime.now(ZoneInfo("Asia/Seoul"))

    target_time = safe_str(data.get("time")).strip() or local_now.strftime("%H:%M")
    date_value = compact_date_value(data.get("date")) or local_now.strftime("%Y%m%d")
    if not re.fullmatch(r"(?:[01]\\d|2[0-3]):[0-5]\\d", target_time):
        return jsonify({"ok": False, "error": "발송 시간 형식은 HH:MM이어야 해"}), 400

    sent = []
    skipped = []
    failed = []
    for account in get_all_login_rows(include_trash=False):
        if account.get("role") != "s":
            continue
        if not account.get("email_notifications"):
            continue
        if safe_str(account.get("notification_time")).strip() != target_time:
            continue

        recipient = safe_str(account.get("email")).strip()
        if not is_valid_email(recipient):
            skipped.append({"id": account.get("id"), "reason": "이메일 주소 없음 또는 오류"})
            continue

        student = get_student_by_student_number(account.get("id"), include_trash=False)
        if not student:
            skipped.append({"id": account.get("id"), "reason": "학생 정보 없음"})
            continue

        try:
            message = build_student_email_message(student, date_value)
            email_id = send_email(recipient, message)
            sent.append({
                "id": account.get("id"),
                "email": recipient,
                "email_id": email_id,
                "status": message.get("status"),
            })
        except Exception as exc:
            logger.exception("예약 급식 이메일 발송 실패: %s", account.get("id"))
            failed.append({"id": account.get("id"), "email": recipient, "error": safe_str(exc)})

    payload = {
        "ok": not failed,
        "date": date_value,
        "time": target_time,
        "sent_count": len(sent),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "sent": sent,
        "skipped": skipped,
        "failed": failed,
    }
    return jsonify(payload), (207 if failed else 200)


'''
insert_before(
    '@app.post("/api/student/my-account/reset-password")\n',
    email_routes,
    "email notification routes",
)

path.write_text(text, encoding="utf-8")
print("Email notification feature applied")
