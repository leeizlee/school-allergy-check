import hmac
import logging
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import jsonify, request, session

from admin import app_admin as legacy
from admin import v5_issue3_patch as targeted_menus
from admin.app_admin import app
from services.gmail_service import (
    build_daily_email,
    gmail_delivery_configured,
    is_valid_email,
    send_email,
)


logger = logging.getLogger(__name__)
EMAIL_DISPATCH_TOKEN = os.getenv("EMAIL_DISPATCH_TOKEN", "").strip()
NOTIFICATION_TIMEZONE = os.getenv("NOTIFICATION_TIMEZONE", "Asia/Seoul").strip() or "Asia/Seoul"
DEFAULT_NOTIFICATION_TIME = "07:30"
TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
SETTING_HEADERS = (
    "notifications_enabled",
    "email",
    "email_notifications",
    "notification_time",
    "email_last_sent_date",
)

_HEADER_LOCK = threading.RLock()
_DISPATCH_LOCK = threading.Lock()


def _safe(value):
    return legacy.safe_str(value).strip()


def _enabled(value):
    if isinstance(value, bool):
        return value
    return _safe(value).lower() in {"1", "true", "yes", "on", "enabled", "y"}


_original_get_all_login_rows = legacy.get_all_login_rows


def _get_all_login_rows_with_notifications(include_trash=False):
    records = legacy.id_ws.get_all_records()
    rows = []
    for row_index, raw in enumerate(records, start=2):
        row = legacy.clean_record_keys(raw)
        trash = legacy.normalize_trash(row.get("trash", 0))
        if not include_trash and trash == "1":
            continue
        rows.append(
            {
                "row_index": row_index,
                "id": _safe(row.get("id")),
                "name": _safe(row.get("name")),
                "pw": _safe(row.get("pw")),
                "role": _safe(row.get("role")).lower(),
                "notifications_enabled": _enabled(row.get("notifications_enabled")),
                "email": _safe(row.get("email")),
                "email_notifications": _enabled(row.get("email_notifications")),
                "notification_time": _safe(row.get("notification_time")) or DEFAULT_NOTIFICATION_TIME,
                "email_last_sent_date": _safe(row.get("email_last_sent_date")),
                "trash": trash,
            }
        )
    return rows


legacy.get_all_login_rows = _get_all_login_rows_with_notifications


def _ensure_headers(ws, headers):
    with _HEADER_LOCK:
        header_row = [_safe(value) for value in ws.row_values(1)]
        mapping = {value: index for index, value in enumerate(header_row, start=1) if value}
        next_column = len(header_row) + 1
        for header in headers:
            if header in mapping:
                continue
            ws.update_cell(1, next_column, header)
            mapping[header] = next_column
            next_column += 1
        legacy._invalidate_sheet_cache(ws)
        return mapping


def _update_settings(row_index, values):
    with _HEADER_LOCK:
        mapping = _ensure_headers(legacy.id_ws, SETTING_HEADERS)
        for header, value in values.items():
            legacy.id_ws.update_cell(row_index, mapping[header], value)
        legacy._invalidate_sheet_cache(legacy.id_ws)


def get_student_notification_settings(student_number):
    account = legacy.get_login_by_id(student_number, include_trash=False) or {}
    return {
        "notifications_enabled": bool(account.get("notifications_enabled")),
        "email": _safe(account.get("email")),
        "email_notifications": bool(account.get("email_notifications")),
        "notification_time": _safe(account.get("notification_time")) or DEFAULT_NOTIFICATION_TIME,
        "email_last_sent_date": _safe(account.get("email_last_sent_date")),
        "gmail_configured": gmail_delivery_configured(),
    }


legacy.get_student_notification_settings = get_student_notification_settings
legacy.gmail_delivery_configured = gmail_delivery_configured


def _student_email_context(student, student_number, date_value):
    date_value = legacy.compact_date_value(date_value) or legacy.today_sheet_str()
    menus = targeted_menus._menus_for_student(date_value, student_number)
    student_codes = legacy.parse_codes((student or {}).get("allergy_codes"))
    details = legacy.get_menu_hit_details(student_codes, menus)
    hit_codes = sorted({code for item in details for code in item.get("hit_codes", [])})
    menu_names = [
        _safe(menu.get("menu_name"))
        for menu in menus
        if _safe(menu.get("menu_name"))
    ]
    unsafe_menus = [
        _safe(item.get("menu_name"))
        for item in details
        if _safe(item.get("menu_name"))
    ]
    return {
        "date": date_value,
        "menu_names": menu_names,
        "allergy_names": legacy.codes_to_names(sorted(student_codes)),
        "unsafe_menus": unsafe_menus,
        "matched_names": legacy.codes_to_names(hit_codes),
    }


def _student_email_message(student, student_number, date_value):
    context = _student_email_context(student, student_number, date_value)
    return build_daily_email(
        student_name=_safe((student or {}).get("name")) or "학생",
        date_value=context["date"],
        menu_names=context["menu_names"],
        allergy_names=context["allergy_names"],
        unsafe_menus=context["unsafe_menus"],
        matched_names=context["matched_names"],
    )


def _dispatch_authorized():
    if not EMAIL_DISPATCH_TOKEN:
        return False
    authorization = _safe(request.headers.get("Authorization"))
    supplied = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    if not supplied:
        supplied = _safe(request.headers.get("X-Notification-Token"))
    return bool(supplied) and hmac.compare_digest(supplied, EMAIL_DISPATCH_TOKEN)


def _student_api_guard():
    ok, response = legacy.require_student()
    if ok:
        return None
    if isinstance(response, str):
        return jsonify({"ok": False, "error": response}), 403
    return jsonify({"ok": False, "error": "로그인이 필요해요."}), 401


@app.get("/api/student/notification-settings")
def api_student_notification_settings():
    denied = _student_api_guard()
    if denied:
        return denied
    student_number = _safe(session.get("login_id"))
    return jsonify({"ok": True, "settings": get_student_notification_settings(student_number)})


@app.post("/api/student/notification-settings")
def api_student_notification_settings_update():
    denied = _student_api_guard()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    email = _safe(payload.get("email"))
    notification_time = _safe(payload.get("notification_time")) or DEFAULT_NOTIFICATION_TIME
    notifications_enabled = _enabled(payload.get("notifications_enabled"))
    email_notifications = _enabled(payload.get("email_notifications"))

    if email and not is_valid_email(email):
        return jsonify({"ok": False, "error": "이메일 주소 형식을 확인해 주세요."}), 400
    if notifications_enabled and email_notifications and not email:
        return jsonify({"ok": False, "error": "이메일 알림을 사용하려면 받을 주소를 입력해 주세요."}), 400
    if not TIME_PATTERN.fullmatch(notification_time):
        return jsonify({"ok": False, "error": "알림 시간 형식이 올바르지 않습니다."}), 400

    account = legacy.get_login_by_id(_safe(session.get("login_id")), include_trash=False)
    if not account:
        return jsonify({"ok": False, "error": "학생 계정을 찾지 못했습니다."}), 404

    _update_settings(
        account["row_index"],
        {
            "notifications_enabled": "1" if notifications_enabled else "0",
            "email": email,
            "email_notifications": "1" if email_notifications else "0",
            "notification_time": notification_time,
        },
    )
    logger.info(
        "학생 알림 설정 저장: student=%s enabled=%s email_enabled=%s time=%s",
        account.get("id"), notifications_enabled, email_notifications, notification_time,
    )
    return jsonify({"ok": True, "settings": get_student_notification_settings(account["id"])})


@app.post("/api/student/notifications/email-test")
def api_student_notification_email_test():
    denied = _student_api_guard()
    if denied:
        return denied
    if not gmail_delivery_configured():
        return jsonify({"ok": False, "error": "서버의 Gmail OAuth 설정이 아직 완료되지 않았습니다."}), 503

    payload = request.get_json(silent=True) or {}
    student_number = _safe(session.get("login_id"))
    account = legacy.get_login_by_id(student_number, include_trash=False) or {}
    recipient = _safe(payload.get("email")) or _safe(account.get("email"))
    if not is_valid_email(recipient):
        return jsonify({"ok": False, "error": "테스트 이메일을 받을 주소를 확인해 주세요."}), 400
    student = legacy.get_student_by_student_number(student_number, include_trash=False)
    if not student:
        return jsonify({"ok": False, "error": "학생 정보를 찾지 못했습니다."}), 404

    try:
        message = _student_email_message(student, student_number, legacy.today_sheet_str())
        gmail_message_id = send_email(recipient, message)
    except Exception as exc:
        logger.exception("학생 테스트 Gmail 발송 실패: %s", student_number)
        return jsonify({"ok": False, "error": _safe(exc) or "테스트 이메일 발송에 실패했습니다."}), 502
    return jsonify({"ok": True, "message_id": gmail_message_id, "status": message.get("status")})


@app.post("/api/notifications/email-dispatch")
def api_notification_email_dispatch():
    if not _dispatch_authorized():
        return jsonify({"ok": False, "error": "알림 발송 토큰이 올바르지 않습니다."}), 401
    if not gmail_delivery_configured():
        return jsonify({"ok": False, "error": "서버의 Gmail OAuth 설정이 아직 완료되지 않았습니다."}), 503
    if not _DISPATCH_LOCK.acquire(blocking=False):
        return jsonify({"ok": False, "error": "이전 알림 발송 작업이 아직 진행 중입니다."}), 409

    try:
        payload = request.get_json(silent=True) or {}
        try:
            local_now = datetime.now(ZoneInfo(NOTIFICATION_TIMEZONE))
        except Exception:
            logger.warning("알림 시간대 설정 오류로 UTC+09:00을 사용합니다.")
            local_now = datetime.now(timezone(timedelta(hours=9)))

        requested_time = _safe(payload.get("time"))
        if requested_time and not TIME_PATTERN.fullmatch(requested_time):
            return jsonify({"ok": False, "error": "발송 시간은 HH:MM 형식이어야 합니다."}), 400
        date_value = legacy.compact_date_value(payload.get("date")) or local_now.strftime("%Y%m%d")
        try:
            window_minutes = max(1, min(int(payload.get("window_minutes", 6)), 15))
        except (TypeError, ValueError):
            window_minutes = 6
        current_minutes = local_now.hour * 60 + local_now.minute

        def is_due(account):
            configured_time = _safe(account.get("notification_time"))
            if not TIME_PATTERN.fullmatch(configured_time):
                return False
            if requested_time:
                return configured_time == requested_time
            hour, minute = (int(part) for part in configured_time.split(":", 1))
            elapsed = current_minutes - (hour * 60 + minute)
            return 0 <= elapsed < window_minutes

        sent, skipped, failed = [], [], []
        accounts = legacy.get_all_login_rows(include_trash=False)
        for account in accounts:
            if account.get("role") != "s" or not account.get("notifications_enabled"):
                continue
            if not account.get("email_notifications") or not is_due(account):
                continue
            if _safe(account.get("email_last_sent_date")) == date_value:
                skipped.append({"id": account.get("id"), "reason": "오늘 이미 발송됨"})
                continue
            recipient = _safe(account.get("email"))
            if not is_valid_email(recipient):
                skipped.append({"id": account.get("id"), "reason": "이메일 주소 오류"})
                continue
            student_number = _safe(account.get("id"))
            student = legacy.get_student_by_student_number(student_number, include_trash=False)
            if not student:
                skipped.append({"id": student_number, "reason": "학생 정보 없음"})
                continue

            try:
                message = _student_email_message(student, student_number, date_value)
                gmail_message_id = send_email(recipient, message)
                _update_settings(account["row_index"], {"email_last_sent_date": date_value})
                sent.append({"id": student_number, "message_id": gmail_message_id, "status": message.get("status")})
            except Exception as exc:
                logger.exception("예약 Gmail 발송 실패: %s", student_number)
                failed.append({"id": student_number, "error": _safe(exc)})

        result = {
            "ok": not failed,
            "date": date_value,
            "time": requested_time or local_now.strftime("%H:%M"),
            "window_minutes": window_minutes,
            "eligible_count": len(sent) + len(skipped) + len(failed),
            "sent_count": len(sent),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
            "sent": sent,
            "skipped": skipped,
            "failed": failed,
        }
        logger.info(
            "급식 이메일 예약 발송: date=%s eligible=%d sent=%d skipped=%d failed=%d",
            date_value, result["eligible_count"], len(sent), len(skipped), len(failed),
        )
        return jsonify(result), (207 if failed else 200)
    finally:
        _DISPATCH_LOCK.release()
