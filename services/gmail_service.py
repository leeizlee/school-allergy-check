import base64
import html
import os
import random
import re
import threading
import time
from email.message import EmailMessage

import requests


GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_TOKEN_LOCK = threading.Lock()
_TOKEN_CACHE = {"access_token": "", "expires_at": 0.0}


def _env(name, default=""):
    return os.getenv(name, default).strip()


def is_valid_email(value):
    return bool(EMAIL_PATTERN.fullmatch(str(value or "").strip()))


def gmail_delivery_configured():
    return all(
        _env(name)
        for name in (
            "GMAIL_CLIENT_ID",
            "GMAIL_CLIENT_SECRET",
            "GMAIL_REFRESH_TOKEN",
            "GMAIL_SENDER_EMAIL",
        )
    )


def _invalidate_access_token():
    with _TOKEN_LOCK:
        _TOKEN_CACHE.update({"access_token": "", "expires_at": 0.0})


def _access_token(force_refresh=False):
    with _TOKEN_LOCK:
        now = time.time()
        if not force_refresh and _TOKEN_CACHE["access_token"] and now < _TOKEN_CACHE["expires_at"] - 60:
            return _TOKEN_CACHE["access_token"]

        if not gmail_delivery_configured():
            raise RuntimeError("Gmail OAuth 환경변수가 아직 설정되지 않았습니다.")

        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": _env("GMAIL_CLIENT_ID"),
                "client_secret": _env("GMAIL_CLIENT_SECRET"),
                "refresh_token": _env("GMAIL_REFRESH_TOKEN"),
                "grant_type": "refresh_token",
            },
            timeout=20,
        )
        if not response.ok:
            detail = response.text.strip()
            raise RuntimeError(f"Gmail OAuth 토큰 갱신에 실패했습니다 ({response.status_code}): {detail[:300]}")

        payload = response.json()
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("Gmail OAuth 응답에 access_token이 없습니다.")
        expires_in = max(int(payload.get("expires_in") or 3600), 60)
        _TOKEN_CACHE.update({"access_token": token, "expires_at": now + expires_in})
        return token


def _display_date(value):
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) == 8:
        return f"{digits[:4]}년 {digits[4:6]}월 {digits[6:8]}일"
    return str(value or "").strip() or "오늘"


def _join(values, empty="없음"):
    cleaned = [str(value).strip() for value in (values or []) if str(value).strip()]
    return ", ".join(cleaned) if cleaned else empty


def build_daily_email(*, student_name, date_value, menu_names, allergy_names, unsafe_menus, matched_names):
    display_date = _display_date(date_value)
    menu_text = _join(menu_names, "등록된 급식 메뉴가 없습니다")
    allergy_text = _join(allergy_names, "등록된 알레르기 없음")
    unsafe_text = _join(unsafe_menus, "해당 없음")
    matched_text = _join(matched_names, "해당 없음")

    if not menu_names:
        status = "unavailable"
        status_label = "급식 정보 확인 필요"
        subject = "[급식 안전 알림] 오늘 급식 정보가 아직 없습니다"
        summary = "오늘 급식 메뉴가 아직 등록되지 않아 알레르기 비교를 완료하지 못했습니다."
        accent = "#9a6500"
        background = "#fff7e6"
    elif unsafe_menus:
        status = "warning"
        status_label = "주의가 필요합니다"
        subject = "[급식 안전 알림] 오늘 급식에 주의가 필요합니다"
        summary = "오늘 급식에 등록된 알레르기와 겹치는 메뉴가 있습니다. 급식 전 다시 확인해 주세요."
        accent = "#b42318"
        background = "#fff5f5"
    else:
        status = "safe"
        status_label = "등록 정보 기준 안전"
        subject = "[급식 안전 알림] 오늘 급식은 안전합니다"
        summary = "오늘 급식과 등록된 알레르기 정보를 비교한 결과, 현재 등록 정보 기준으로 겹치는 항목이 없습니다."
        accent = "#247a54"
        background = "#eaf8f1"

    student_label = str(student_name or "학생").strip() or "학생"
    text_body = (
        f"{student_label} 학생의 {display_date} 급식 안전 알림입니다.\n\n"
        f"오늘 급식: {menu_text}\n"
        f"등록 알레르기: {allergy_text}\n"
        f"주의 메뉴: {unsafe_text}\n"
        f"확인된 알레르기: {matched_text}\n\n"
        f"{summary}\n\n"
        "메뉴와 원재료는 변경될 수 있으므로 실제 배식 전 학교 안내와 RFID 현장 확인을 함께 이용해 주세요."
    )
    html_body = f"""
<!doctype html>
<html lang="ko"><body style="margin:0;background:#f4f6fa;font-family:Arial,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#111827;">
  <div style="max-width:620px;margin:0 auto;padding:24px;">
    <div style="overflow:hidden;border:1px solid #dfe5ee;border-radius:18px;background:#fff;">
      <div style="padding:22px 24px;border-bottom:1px solid #dfe5ee;background:{background};">
        <div style="font-size:13px;font-weight:700;color:{accent};">AllergySafe · 급식 안전 알림</div>
        <h1 style="margin:8px 0 0;font-size:24px;line-height:1.35;">{html.escape(status_label)}</h1>
      </div>
      <div style="padding:24px;">
        <p style="margin:0 0 18px;line-height:1.7;">{html.escape(student_label)} 학생의 <strong>{html.escape(display_date)}</strong> 급식 비교 결과입니다.</p>
        <div style="padding:16px;border-left:5px solid {accent};border-radius:10px;background:{background};line-height:1.7;">{html.escape(summary)}</div>
        <table role="presentation" style="width:100%;margin-top:20px;border-collapse:collapse;font-size:14px;">
          <tr><td style="width:130px;padding:11px;border-bottom:1px solid #e5e7eb;font-weight:700;">오늘 급식</td><td style="padding:11px;border-bottom:1px solid #e5e7eb;">{html.escape(menu_text)}</td></tr>
          <tr><td style="padding:11px;border-bottom:1px solid #e5e7eb;font-weight:700;">등록 알레르기</td><td style="padding:11px;border-bottom:1px solid #e5e7eb;">{html.escape(allergy_text)}</td></tr>
          <tr><td style="padding:11px;border-bottom:1px solid #e5e7eb;font-weight:700;">주의 메뉴</td><td style="padding:11px;border-bottom:1px solid #e5e7eb;color:{accent};font-weight:700;">{html.escape(unsafe_text)}</td></tr>
          <tr><td style="padding:11px;font-weight:700;">확인된 알레르기</td><td style="padding:11px;">{html.escape(matched_text)}</td></tr>
        </table>
        <p style="margin:22px 0 0;color:#667085;font-size:12px;line-height:1.6;">메뉴와 원재료는 변경될 수 있으므로 실제 배식 전 학교 안내와 RFID 현장 확인을 함께 이용해 주세요.</p>
      </div>
    </div>
  </div>
</body></html>
""".strip()
    return {"status": status, "subject": subject, "text": text_body, "html": html_body}


def _raw_message(to_email, message):
    email_message = EmailMessage()
    email_message["To"] = to_email
    email_message["From"] = _env("GMAIL_SENDER_EMAIL")
    email_message["Subject"] = str(message.get("subject") or "급식 안전 알림")
    email_message.set_content(str(message.get("text") or ""))
    email_message.add_alternative(str(message.get("html") or ""), subtype="html")
    return base64.urlsafe_b64encode(email_message.as_bytes()).decode("ascii")


def send_email(to_email, message, max_attempts=4):
    recipient = str(to_email or "").strip()
    if not is_valid_email(recipient):
        raise ValueError("받는 이메일 주소가 올바르지 않습니다.")
    if not gmail_delivery_configured():
        raise RuntimeError("Gmail OAuth 환경변수가 아직 설정되지 않았습니다.")

    raw = _raw_message(recipient, message)
    last_error = None
    for attempt in range(max(1, max_attempts)):
        token = _access_token(force_refresh=attempt > 0 and getattr(last_error, "status_code", 0) == 401)
        try:
            response = requests.post(
                GMAIL_SEND_URL,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"raw": raw},
                timeout=25,
            )
            if response.ok:
                payload = response.json() if response.content else {}
                return str(payload.get("id") or "")
            error = RuntimeError(f"Gmail API 발송에 실패했습니다 ({response.status_code}): {response.text.strip()[:300]}")
            error.status_code = response.status_code
            last_error = error
            if response.status_code == 401:
                _invalidate_access_token()
            if response.status_code not in {401, 429, 500, 502, 503, 504}:
                raise error
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc

        if attempt + 1 < max_attempts:
            time.sleep((2 ** attempt) + random.uniform(0, 0.35))

    raise last_error or RuntimeError("Gmail API 발송에 실패했습니다.")
