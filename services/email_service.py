import html
import os
import re

import requests


RESEND_API_URL = "https://api.resend.com/emails"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _env(name, default=""):
    return os.getenv(name, default).strip()


def email_delivery_configured():
    return bool(_env("RESEND_API_KEY") and _env("EMAIL_FROM"))


def is_valid_email(value):
    return bool(EMAIL_PATTERN.fullmatch(str(value or "").strip()))


def _display_date(value):
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) == 8:
        return f"{digits[:4]}년 {digits[4:6]}월 {digits[6:8]}일"
    return str(value or "").strip() or "오늘"


def _join(values, empty="없음"):
    cleaned = [str(value).strip() for value in (values or []) if str(value).strip()]
    return ", ".join(cleaned) if cleaned else empty


def build_daily_email(
    *,
    student_name,
    date_value,
    menu_names,
    allergy_names,
    unsafe_menus,
    matched_names,
):
    display_date = _display_date(date_value)
    menu_text = _join(menu_names, "등록된 급식 메뉴가 없습니다")
    allergy_text = _join(allergy_names, "등록된 알레르기 없음")
    unsafe_text = _join(unsafe_menus, "해당 없음")
    matched_text = _join(matched_names, "해당 없음")

    if not menu_names:
        status = "unavailable"
        status_label = "급식 정보 확인 필요"
        subject = f"[급식 안전 알림] {display_date} 급식 정보가 아직 없습니다"
        summary = "오늘 급식 메뉴가 아직 등록되지 않아 알레르기 비교를 완료하지 못했습니다."
        accent = "#d97706"
        background = "#fffbeb"
    elif unsafe_menus:
        status = "warning"
        status_label = "알레르기 주의"
        subject = f"[급식 안전 주의] {display_date} 확인이 필요한 메뉴가 있습니다"
        summary = "등록된 알레르기 정보와 오늘 급식 메뉴에서 겹치는 항목을 확인했습니다."
        accent = "#dc2626"
        background = "#fef2f2"
    else:
        status = "safe"
        status_label = "비교 결과 안전"
        subject = f"[급식 안전 알림] {display_date} 알레르기 비교 결과"
        summary = "등록된 알레르기 정보와 오늘 급식 메뉴를 비교한 결과, 확인된 위험 메뉴가 없습니다."
        accent = "#15803d"
        background = "#f0fdf4"

    student_label = str(student_name or "학생").strip() or "학생"
    text_body = (
        f"{student_label} 학생의 {display_date} 급식 안전 알림입니다.\n\n"
        f"상태: {status_label}\n"
        f"오늘 급식: {menu_text}\n"
        f"등록 알레르기: {allergy_text}\n"
        f"주의 메뉴: {unsafe_text}\n"
        f"일치 알레르기: {matched_text}\n\n"
        f"{summary}\n"
        "급식 정보가 변경될 수 있으므로 실제 배식 전에도 학교 안내를 확인해 주세요."
    )

    html_body = f"""
<!doctype html>
<html lang="ko">
  <body style="margin:0;background:#f3f4f6;font-family:Arial,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#111827;">
    <div style="max-width:620px;margin:0 auto;padding:24px;">
      <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:18px;overflow:hidden;">
        <div style="padding:22px 24px;background:{background};border-bottom:1px solid #e5e7eb;">
          <div style="font-size:13px;font-weight:700;color:{accent};">급식 안전 알림센터</div>
          <h1 style="margin:8px 0 0;font-size:24px;line-height:1.35;">{html.escape(status_label)}</h1>
        </div>
        <div style="padding:24px;">
          <p style="margin:0 0 18px;line-height:1.7;">{html.escape(student_label)} 학생의 <strong>{html.escape(display_date)}</strong> 급식 비교 결과입니다.</p>
          <div style="padding:16px;border-left:5px solid {accent};background:{background};border-radius:10px;line-height:1.7;">{html.escape(summary)}</div>
          <table role="presentation" style="width:100%;border-collapse:collapse;margin-top:20px;font-size:14px;">
            <tr><td style="padding:11px;border-bottom:1px solid #e5e7eb;font-weight:700;width:130px;">오늘 급식</td><td style="padding:11px;border-bottom:1px solid #e5e7eb;">{html.escape(menu_text)}</td></tr>
            <tr><td style="padding:11px;border-bottom:1px solid #e5e7eb;font-weight:700;">등록 알레르기</td><td style="padding:11px;border-bottom:1px solid #e5e7eb;">{html.escape(allergy_text)}</td></tr>
            <tr><td style="padding:11px;border-bottom:1px solid #e5e7eb;font-weight:700;">주의 메뉴</td><td style="padding:11px;border-bottom:1px solid #e5e7eb;color:{accent};font-weight:700;">{html.escape(unsafe_text)}</td></tr>
            <tr><td style="padding:11px;font-weight:700;">일치 알레르기</td><td style="padding:11px;">{html.escape(matched_text)}</td></tr>
          </table>
          <p style="margin:22px 0 0;color:#6b7280;font-size:12px;line-height:1.6;">급식 정보가 변경될 수 있으므로 실제 배식 전에도 학교 안내를 확인해 주세요.</p>
        </div>
      </div>
    </div>
  </body>
</html>
""".strip()

    return {
        "status": status,
        "subject": subject,
        "text": text_body,
        "html": html_body,
    }


def send_email(to_email, message):
    recipient = str(to_email or "").strip()
    if not is_valid_email(recipient):
        raise ValueError("받는 이메일 주소가 올바르지 않습니다.")

    api_key = _env("RESEND_API_KEY")
    from_email = _env("EMAIL_FROM")
    if not api_key or not from_email:
        raise RuntimeError("RESEND_API_KEY와 EMAIL_FROM 환경변수를 설정해야 합니다.")

    payload = {
        "from": from_email,
        "to": [recipient],
        "subject": str(message.get("subject") or "급식 안전 알림"),
        "text": str(message.get("text") or ""),
        "html": str(message.get("html") or ""),
    }
    reply_to = _env("EMAIL_REPLY_TO")
    if reply_to:
        payload["reply_to"] = reply_to

    response = requests.post(
        RESEND_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )
    if not response.ok:
        detail = response.text.strip()
        raise RuntimeError(f"이메일 발송에 실패했습니다 ({response.status_code}): {detail[:300]}")

    data = response.json() if response.content else {}
    return str(data.get("id") or "")
