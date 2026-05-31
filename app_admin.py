import os
import hmac
import base64
import io
import threading
import time
from pathlib import Path

from flask import jsonify, make_response, redirect, render_template_string, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from admin import app_admin as admin_app_module
from admin.app_admin import app
from admin.v5_admin_renderer import render_admin_page_v5


app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
admin_app_module.render_admin_page = render_admin_page_v5


def _int_env(name, default, min_value=1, max_value=None):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    value = max(value, min_value)
    if max_value is not None:
        value = min(value, max_value)
    return value


app.config["MAX_CONTENT_LENGTH"] = _int_env("MAX_UPLOAD_MB", 16, min_value=1, max_value=64) * 1024 * 1024
if admin_app_module.IS_PRODUCTION:
    app.config["SESSION_COOKIE_NAME"] = os.getenv("SESSION_COOKIE_NAME", "__Host-school_allergy_session")
app.config.setdefault("SESSION_REFRESH_EACH_REQUEST", False)


def _v5_admin_home():
    if admin_app_module.is_logged_in():
        if admin_app_module.is_admin():
            return admin_app_module.render_admin_page(
                "관리자 홈",
                "오늘 급식 안전 상태와 운영 지표를 한눈에 확인해.",
                "admin_home",
            )
        if admin_app_module.is_student():
            return redirect(url_for("student_home_page"))
    return redirect(url_for("login_page"))


app.view_functions["home"] = _v5_admin_home


def _v5_ai_tools_page():
    ok, response = admin_app_module.require_admin()
    if not ok:
        return response
    return admin_app_module.render_admin_page(
        "AI 안전상황실",
        "오늘 급식 위험 브리핑, 학생별 안전계획, 메뉴 코드 점검을 나눠서 확인해.",
        "ai_tools",
    )


app.view_functions["ai_tools_page"] = _v5_ai_tools_page


@app.get("/admin/ai-tools/daily-brief")
def ai_tools_daily_brief_page():
    ok, response = admin_app_module.require_admin()
    if not ok:
        return response
    return admin_app_module.render_admin_page(
        "오늘 위험 브리핑",
        "오늘 급식 메뉴와 주의 학생을 AI 보조 분석으로 빠르게 점검해.",
        "ai_tools",
    )


@app.get("/admin/ai-tools/student-plan")
def ai_tools_student_plan_page():
    ok, response = admin_app_module.require_admin()
    if not ok:
        return response
    return admin_app_module.render_admin_page(
        "학생별 안전계획",
        "학생 알레르기와 오늘 식단을 바탕으로 대체급식과 전달 메시지를 정리해.",
        "ai_tools",
    )


@app.get("/admin/ai-tools/menu-review")
def ai_tools_menu_review_page():
    ok, response = admin_app_module.require_admin()
    if not ok:
        return response
    return admin_app_module.render_admin_page(
        "메뉴 코드 점검",
        "급식 메뉴의 알레르기 코드 누락 가능성을 AI 보조 분석으로 확인해.",
        "ai_tools",
    )


_PROJECT_ROOT = Path(__file__).resolve().parent
app.static_folder = str(_PROJECT_ROOT / "static")
app.template_folder = str(_PROJECT_ROOT / "templates")

_LOGIN_TEMPLATE_PATH = _PROJECT_ROOT / "templates" / "login.html"
if _LOGIN_TEMPLATE_PATH.exists():
    admin_app_module.LOGIN_HTML = _LOGIN_TEMPLATE_PATH.read_text(encoding="utf-8")


_LOGIN_RATE_LIMIT = _int_env("LOGIN_RATE_LIMIT_ATTEMPTS", 8, min_value=3, max_value=30)
_LOGIN_RATE_WINDOW_SECONDS = _int_env("LOGIN_RATE_LIMIT_WINDOW_SECONDS", 600, min_value=60, max_value=3600)
_LOGIN_ATTEMPTS = {}
_LOGIN_RATE_LOCK = threading.Lock()


def _login_key():
    forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    client_ip = forwarded_for or request.remote_addr or "unknown"
    login_id = (request.form.get("login_id") or "").strip().lower()[:80]
    return f"{client_ip}:{login_id}"


def _login_limited(key):
    now = time.monotonic()
    with _LOGIN_RATE_LOCK:
        attempts = [ts for ts in _LOGIN_ATTEMPTS.get(key, []) if now - ts < _LOGIN_RATE_WINDOW_SECONDS]
        _LOGIN_ATTEMPTS[key] = attempts
        if len(attempts) >= _LOGIN_RATE_LIMIT:
            retry_after = int(_LOGIN_RATE_WINDOW_SECONDS - (now - attempts[0]))
            return True, max(retry_after, 1)
    return False, 0


def _record_login_failure(key):
    now = time.monotonic()
    with _LOGIN_RATE_LOCK:
        attempts = [ts for ts in _LOGIN_ATTEMPTS.get(key, []) if now - ts < _LOGIN_RATE_WINDOW_SECONDS]
        attempts.append(now)
        _LOGIN_ATTEMPTS[key] = attempts


def _clear_login_failures(key):
    with _LOGIN_RATE_LOCK:
        _LOGIN_ATTEMPTS.pop(key, None)


_original_login_page = app.view_functions.get("login_page")


def _hardened_login_page():
    if request.method != "POST":
        return _original_login_page()

    key = _login_key()
    limited, retry_after = _login_limited(key)
    if limited:
        response = make_response(
            render_template_string(
                admin_app_module.LOGIN_HTML,
                error=f"로그인 시도가 너무 많아. {max(1, retry_after // 60 + 1)}분 뒤 다시 시도해줘.",
            ),
            429,
        )
        response.headers["Retry-After"] = str(retry_after)
        return response

    session.clear()
    response = make_response(_original_login_page())
    if 300 <= response.status_code < 400:
        _clear_login_failures(key)
    else:
        _record_login_failure(key)
    return response


if _original_login_page is not None:
    app.view_functions["login_page"] = _hardened_login_page


@app.post("/api/my-account/picture")
def api_my_account_picture():
    if not admin_app_module.is_logged_in():
        return jsonify({"ok": False, "error": "로그인이 필요해"}), 401

    upload = request.files.get("picture")
    if not upload or not upload.filename:
        return jsonify({"ok": False, "error": "프로필 사진 파일을 선택해줘"}), 400
    if upload.mimetype and not upload.mimetype.startswith("image/"):
        return jsonify({"ok": False, "error": "이미지 파일만 업로드할 수 있어"}), 400

    raw = upload.read()
    max_bytes = _int_env("PROFILE_IMAGE_MAX_MB", 3, min_value=1, max_value=8) * 1024 * 1024
    if len(raw) > max_bytes:
        return jsonify({"ok": False, "error": "프로필 사진은 3MB 이하로 올려줘"}), 413

    login_id = admin_app_module.safe_str(session.get("login_id")).strip()
    login_row = admin_app_module.get_login_by_id(login_id, include_trash=True)
    if not login_row:
        return jsonify({"ok": False, "error": "계정을 찾지 못했어"}), 404

    try:
        from PIL import Image, ImageOps

        with Image.open(io.BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            width, height = image.size
            side = min(width, height)
            left = (width - side) // 2
            top = (height - side) // 2
            image = image.crop((left, top, left + side, top + side)).resize((192, 192), Image.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=86, optimize=True)
    except ImportError:
        return jsonify({"ok": False, "error": "프로필 사진 처리를 위해 Pillow 설치가 필요해"}), 500
    except Exception:
        return jsonify({"ok": False, "error": "이미지를 읽지 못했어. 다른 사진으로 시도해줘"}), 400

    picture = "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    try:
        admin_app_module.update_cell_by_header(admin_app_module.id_ws, login_row["row_index"], "picture", picture)
    except ValueError:
        return jsonify({"ok": False, "error": "id 시트에 picture 헤더가 필요해"}), 400

    return jsonify({"ok": True, "picture": picture})


@app.before_request
def _security_preflight():
    if request.path == "/api/kiosk/scan" and admin_app_module.KIOSK_SCAN_API_TOKEN:
        data = request.get_json(silent=True) or {}
        token = str(data.get("token") or "").strip()
        expected = str(admin_app_module.KIOSK_SCAN_API_TOKEN).strip()
        if not hmac.compare_digest(token, expected):
            return jsonify({"ok": False, "error": "인증 토큰이 올바르지 않아"}), 403
    return None


@app.after_request
def _add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "font-src 'self' data:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'",
    )
    if admin_app_module.IS_PRODUCTION:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

    sensitive_path = (
        request.path == "/"
        or request.path == "/login"
        or request.path.startswith(("/admin", "/api", "/student", "/menu", "/lunch", "/trash"))
    )
    if sensitive_path:
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")), debug=False)
