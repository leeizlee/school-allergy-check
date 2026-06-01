import threading
import time
from collections import Counter
from datetime import datetime

from flask import jsonify, redirect, request, session, url_for

from admin import app_admin as legacy
from admin import v5_admin_renderer
from admin import v5_ops_patch as ops
from admin import v5_runtime_patch as realtime
from admin.app_admin import app


_OPS_SHEET_CACHE = {}
_OPS_SHEET_LOCK = threading.Lock()
_NOTIFICATION_HEADERS = ["id", "target", "path", "icon", "title", "detail", "time", "kind", "created_at"]
_AUDIT_HEADERS = ["id", "time", "action", "category", "detail", "status", "status_code", "path", "method", "ip", "actor_id", "actor_name", "role"]

_ROLE_LABELS = {
    "a": "최고관리자", "admin": "최고관리자", "super": "최고관리자", "superadmin": "최고관리자",
    "n": "영양사", "nutritionist": "영양사", "dietitian": "영양사", "영양사": "영양사",
    "h": "담임교사", "homeroom": "담임교사", "담임": "담임교사",
    "t": "일반교사", "teacher": "일반교사", "교사": "일반교사",
}
_ADMIN_ROLES = set(_ROLE_LABELS)
_FULL_ROLES = {"a", "admin", "super", "superadmin"}
_NUTRITION_ROLES = {"n", "nutritionist", "dietitian", "영양사"}
_TEACHER_ROLES = {"h", "homeroom", "담임", "t", "teacher", "교사"}

_PAGE_PERMISSIONS = {
    "student_manage_page": _FULL_ROLES | _TEACHER_ROLES,
    "menu_manage_page": _FULL_ROLES | _NUTRITION_ROLES,
    "lunch_log_page": _ADMIN_ROLES,
    "meal_upload_page": _FULL_ROLES | _NUTRITION_ROLES,
    "ai_tools_page": _ADMIN_ROLES,
    "ai_tools_daily_brief_page": _ADMIN_ROLES,
    "ai_tools_student_plan_page": _ADMIN_ROLES,
    "ai_tools_menu_review_page": _ADMIN_ROLES,
    "trash_page": _FULL_ROLES,
    "system_status_page": _ADMIN_ROLES,
    "audit_log_page": _FULL_ROLES,
    "notifications_page": _ADMIN_ROLES,
}

_WRITE_PERMISSIONS = {
    "api_add_student": _FULL_ROLES,
    "api_student_sheet_add": _FULL_ROLES,
    "api_student_sheet_confirm": _FULL_ROLES,
    "api_student_update": _FULL_ROLES | {"h", "homeroom", "담임"},
    "api_student_reset_password": _FULL_ROLES,
    "api_delete_selected_students": _FULL_ROLES,
    "api_add_menu": _FULL_ROLES | _NUTRITION_ROLES,
    "api_menu_group_update": _FULL_ROLES | _NUTRITION_ROLES,
    "api_delete_selected_menus": _FULL_ROLES | _NUTRITION_ROLES,
    "meal_analyze_page": _FULL_ROLES | _NUTRITION_ROLES,
    "meal_save_page": _FULL_ROLES | _NUTRITION_ROLES,
    "api_meal_analyze_async": _FULL_ROLES | _NUTRITION_ROLES,
    "api_ai_safety_plan": _ADMIN_ROLES,
    "api_ai_daily_brief": _ADMIN_ROLES,
    "api_ai_menu_review": _ADMIN_ROLES,
    "api_my_account_update": _ADMIN_ROLES,
    "api_my_account_reset_password": _ADMIN_ROLES,
    "api_my_account_picture": _ADMIN_ROLES,
    "api_trash_menu_restore": _FULL_ROLES,
    "api_trash_student_restore": _FULL_ROLES,
    "api_trash_menu_hard_delete": _FULL_ROLES,
    "api_trash_student_hard_delete": _FULL_ROLES,
}


def _role_key():
    return legacy.safe_str(session.get("role")).strip().lower()


def _role_label(role=None):
    return _ROLE_LABELS.get(role or _role_key(), "관리자")


def _is_admin_role():
    return legacy.is_logged_in() and _role_key() in _ADMIN_ROLES


legacy.is_admin = _is_admin_role


def _forbidden(message="현재 계정 권한으로는 실행할 수 없어."):
    if request.path.startswith("/api/") or "application/json" in request.headers.get("Accept", ""):
        return jsonify({"ok": False, "error": message}), 403
    return message, 403


@app.before_request
def _v5_role_guard():
    if request.path.startswith(("/kiosk", "/api/kiosk", "/static", "/profile-pictures")):
        return None
    if not legacy.is_logged_in() or legacy.is_student():
        return None
    role = _role_key()
    if role in _FULL_ROLES:
        return None
    endpoint = request.endpoint or ""
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        allowed = _WRITE_PERMISSIONS.get(endpoint)
        if allowed is not None and role not in allowed:
            return _forbidden(f"{_role_label(role)} 권한으로는 이 변경 작업을 실행할 수 없어.")
    allowed_pages = _PAGE_PERMISSIONS.get(endpoint)
    if allowed_pages is not None and role not in allowed_pages:
        return redirect(url_for("home"))
    return None


def _spreadsheet():
    for ws in (getattr(legacy, "logs_ws", None), getattr(legacy, "id_ws", None), getattr(legacy, "menu_ws", None)):
        if not ws:
            continue
        book = getattr(ws, "spreadsheet", None) or getattr(ws, "_spreadsheet", None)
        if book:
            return book
    return None


def _ensure_ops_sheet(title, headers):
    with _OPS_SHEET_LOCK:
        if title in _OPS_SHEET_CACHE:
            return _OPS_SHEET_CACHE[title]
        book = _spreadsheet()
        if not book:
            return None
        try:
            ws = book.worksheet(title)
        except Exception:
            ws = book.add_worksheet(title, 2000, max(len(headers), 8))
        current = [legacy.safe_str(item).strip() for item in ws.row_values(1)]
        for index, header in enumerate(headers, start=1):
            if len(current) < index or current[index - 1] != header:
                ws.update_cell(1, index, header)
        _OPS_SHEET_CACHE[title] = ws
        return ws


def _append_ops_row(title, headers, item):
    try:
        ws = _ensure_ops_sheet(title, headers)
        if not ws:
            return False
        ws.append_row([item.get(header, "") for header in headers], value_input_option="USER_ENTERED")
        return True
    except Exception:
        return False


def _read_ops_rows(title, headers, limit=120):
    try:
        ws = _ensure_ops_sheet(title, headers)
        if not ws:
            return []
        return [legacy.clean_record_keys(row) for row in ws.get_all_records()][-limit:]
    except Exception:
        return []


_original_add_admin_event = realtime._add_admin_event
_original_admin_events = realtime._admin_events


def _persistent_add_admin_event(item):
    _original_add_admin_event(item)
    if not item or not item.get("id"):
        return
    row = {header: legacy.safe_str(item.get(header)).strip() for header in _NOTIFICATION_HEADERS}
    row["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _append_ops_row("admin_notifications", _NOTIFICATION_HEADERS, row)


def _persistent_admin_events():
    memory = _original_admin_events()
    sheet_items = []
    for row in reversed(_read_ops_rows("admin_notifications", _NOTIFICATION_HEADERS, 60)):
        sheet_items.append({
            "id": legacy.safe_str(row.get("id")).strip(),
            "target": legacy.safe_str(row.get("target")).strip(),
            "path": legacy.safe_str(row.get("path")).strip(),
            "icon": legacy.safe_str(row.get("icon")).strip() or "N",
            "title": legacy.safe_str(row.get("title")).strip() or "알림",
            "detail": legacy.safe_str(row.get("detail")).strip(),
            "time": legacy.safe_str(row.get("time")).strip() or legacy.safe_str(row.get("created_at")).strip(),
            "kind": legacy.safe_str(row.get("kind")).strip() or "info",
        })
    seen = set()
    result = []
    for item in memory + sheet_items:
        item_id = item.get("id")
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        result.append(item)
    return result[:60]


realtime._add_admin_event = _persistent_add_admin_event
realtime._admin_events = _persistent_admin_events

_original_record_audit = ops._record_audit
_original_audit_logs = ops._audit_logs


def _persistent_record_audit(action, category, detail="", status="success", status_code=200):
    _original_record_audit(action, category, detail, status=status, status_code=status_code)
    try:
        with ops._AUDIT_LOCK:
            item = dict(ops._AUDIT_LOGS[0]) if ops._AUDIT_LOGS else {}
    except Exception:
        item = {}
    actor = item.get("actor") or {}
    row = {
        "id": item.get("id") or f"audit:{int(time.time() * 1000)}",
        "time": item.get("time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "category": category,
        "detail": detail,
        "status": status,
        "status_code": status_code,
        "path": item.get("path") or request.path,
        "method": item.get("method") or request.method,
        "ip": item.get("ip") or "-",
        "actor_id": actor.get("id") or legacy.safe_str(session.get("login_id")).strip(),
        "actor_name": actor.get("name") or legacy.safe_str(session.get("login_name")).strip(),
        "role": actor.get("role") or _role_key(),
    }
    _append_ops_row("admin_audit", _AUDIT_HEADERS, row)


def _persistent_audit_logs(limit=120):
    original = _original_audit_logs(limit)
    sheet_items = []
    for row in reversed(_read_ops_rows("admin_audit", _AUDIT_HEADERS, limit)):
        sheet_items.append({
            "id": legacy.safe_str(row.get("id")).strip(),
            "time": legacy.safe_str(row.get("time")).strip(),
            "action": legacy.safe_str(row.get("action")).strip(),
            "category": legacy.safe_str(row.get("category")).strip(),
            "detail": legacy.safe_str(row.get("detail")).strip(),
            "status": legacy.safe_str(row.get("status")).strip() or "success",
            "status_code": legacy.safe_str(row.get("status_code")).strip(),
            "path": legacy.safe_str(row.get("path")).strip(),
            "method": legacy.safe_str(row.get("method")).strip(),
            "ip": legacy.safe_str(row.get("ip")).strip(),
            "actor": {"id": legacy.safe_str(row.get("actor_id")).strip(), "name": legacy.safe_str(row.get("actor_name")).strip(), "role": legacy.safe_str(row.get("role")).strip()},
        })
    seen = set()
    result = []
    for item in original + sheet_items:
        item_id = item.get("id")
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        result.append(item)
    return result[:limit]


ops._record_audit = _persistent_record_audit
ops._audit_logs = _persistent_audit_logs

_original_system_status_payload = ops._system_status_payload


def _enhanced_system_status_payload():
    payload = _original_system_status_payload()
    notification_ws = _ensure_ops_sheet("admin_notifications", _NOTIFICATION_HEADERS)
    audit_ws = _ensure_ops_sheet("admin_audit", _AUDIT_HEADERS)
    storage_items = [
        ops._status_item("알림 저장소", "정상" if notification_ws else "확인 필요", "safe" if notification_ws else "warn", "Google Sheets admin_notifications", "NT"),
        ops._status_item("감사 로그 저장소", "정상" if audit_ws else "확인 필요", "safe" if audit_ws else "warn", "Google Sheets admin_audit", "AU"),
    ]
    payload.setdefault("sheet_items", []).extend(storage_items)
    payload.setdefault("cards", []).append(ops._status_item("운영 기록", "영구 저장" if notification_ws and audit_ws else "부분 저장", "safe" if notification_ws and audit_ws else "warn", "알림/감사로그 Google Sheets 백업", "LG"))
    return payload


ops._system_status_payload = _enhanced_system_status_payload


def _codes(row):
    return sorted(legacy.parse_codes(row.get("allergy_codes")))


def _code_label(code):
    return f"{code}. {legacy.ALLERGY_MAP.get(code, f'알수없음({code})')}"


def _ai_room_payload(context):
    students = context.get("all_student_rows") or context.get("student_rows") or []
    today = context.get("today_sheet")
    menus = [row for row in context.get("menu_rows", []) if legacy.compact_date_value(row.get("date")) == today]
    menu_codes = Counter()
    for menu in menus:
        for code in _codes(menu):
            menu_codes[code] += 1

    risky_students = []
    for student in students:
        student_codes = set(_codes(student))
        if not student_codes:
            continue
        risk_menus = []
        for menu in menus:
            hits = sorted(student_codes & set(_codes(menu)))
            if hits:
                risk_menus.append({"menu": menu.get("menu_name") or "-", "codes": [_code_label(code) for code in hits]})
        if risk_menus:
            risky_students.append({
                "name": student.get("name") or "-",
                "student_number": student.get("student_number") or "-",
                "class_label": student.get("class_label") or "-",
                "allergies": student.get("allergy_names") or ", ".join(_code_label(code) for code in student_codes),
                "risk_count": len(risk_menus),
                "risk_menus": risk_menus[:4],
            })
    risky_students.sort(key=lambda item: item["risk_count"], reverse=True)

    menu_risks = []
    for menu in menus:
        codes = set(_codes(menu))
        if not codes:
            continue
        matched = [student for student in students if codes & set(_codes(student))]
        if matched:
            menu_risks.append({
                "menu": menu.get("menu_name") or "-",
                "codes": [_code_label(code) for code in sorted(codes)],
                "student_count": len(matched),
                "students": [student.get("name") or "-" for student in matched[:5]],
            })
    menu_risks.sort(key=lambda item: item["student_count"], reverse=True)

    allergy_focus = []
    for code, menu_count in menu_codes.most_common(8):
        student_count = sum(1 for student in students if code in set(_codes(student)))
        allergy_focus.append({"code": _code_label(code), "menu_count": menu_count, "student_count": student_count})

    recommendations = []
    if risky_students:
        recommendations.append(f"위험 가능 학생 {len(risky_students)}명은 배식 전 대체식 또는 제외 메뉴를 먼저 확인해줘.")
    if menu_risks:
        recommendations.append(f"가장 위험도가 높은 메뉴는 {menu_risks[0]['menu']}이며 관련 학생 {menu_risks[0]['student_count']}명을 먼저 점검해줘.")
    if allergy_focus:
        recommendations.append(f"오늘 집중 확인 알레르기 코드는 {allergy_focus[0]['code']}입니다.")
    if not recommendations:
        recommendations.append("오늘 등록된 식단 기준으로 즉시 확인할 고위험 조합은 없습니다.")

    return {
        "summary": {"risky_student_count": len(risky_students), "risky_menu_count": len(menu_risks), "allergy_code_count": len(menu_codes), "risk_level": "주의" if risky_students else "안정"},
        "risky_students": risky_students[:5],
        "risky_menus": menu_risks[:5],
        "allergy_focus": allergy_focus[:8],
        "recommendations": recommendations,
    }


_original_build_context = v5_admin_renderer._build_context


def _build_context_with_enterprise(*args, **kwargs):
    context = _original_build_context(*args, **kwargs)
    role = _role_key()
    context["current_role"] = role
    context["role_label"] = _role_label(role)
    context["role_permissions"] = {
        "can_manage_students": role in _FULL_ROLES or role in {"h", "homeroom", "담임"},
        "can_manage_menus": role in _FULL_ROLES or role in _NUTRITION_ROLES,
        "can_view_audit": role in _FULL_ROLES,
    }
    context["ai_room"] = _ai_room_payload(context) if context.get("active_tab") == "ai_tools" else {"summary": {}, "risky_students": [], "risky_menus": [], "allergy_focus": [], "recommendations": []}
    return context


v5_admin_renderer._build_context = _build_context_with_enterprise
