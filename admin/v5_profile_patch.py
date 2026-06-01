import base64
import binascii
import io
import os
import re
import time
from pathlib import Path

from flask import jsonify, request, session

from admin import app_admin as legacy
from admin.app_admin import app


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PROFILE_DIR = _PROJECT_ROOT / "static" / "profile_pictures"
_DATA_URL_RE = re.compile(r"^data:image/(?:png|jpe?g|webp);base64,", re.IGNORECASE)


def _int_env(name, default, min_value=1, max_value=None):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    value = max(value, min_value)
    if max_value is not None:
        value = min(value, max_value)
    return value


def _profile_filename(login_id):
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", legacy.safe_str(login_id).strip())
    value = value.strip("._") or "profile"
    return f"{value[:80]}.jpg"


def _read_picture_bytes():
    data_url = request.form.get("picture_data", "").strip()
    if data_url:
        if not _DATA_URL_RE.match(data_url):
            raise ValueError("지원하지 않는 이미지 데이터야.")
        try:
            return base64.b64decode(_DATA_URL_RE.sub("", data_url), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("이미지 데이터를 읽지 못했어.") from exc

    upload = request.files.get("picture")
    if not upload or not upload.filename:
        raise ValueError("프로필 사진 파일을 선택해줘.")
    if upload.mimetype and not upload.mimetype.startswith("image/"):
        raise ValueError("이미지 파일만 업로드할 수 있어.")
    return upload.read()


def _normalize_profile_image(raw):
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("프로필 사진 처리를 위해 Pillow 설치가 필요해.") from exc

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            width, height = image.size
            side = min(width, height)
            left = (width - side) // 2
            top = (height - side) // 2
            image = image.crop((left, top, left + side, top + side))
            image = image.resize((320, 320), Image.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=88, optimize=True)
            return output.getvalue()
    except Exception as exc:
        raise ValueError("이미지를 처리하지 못했어. 다른 사진으로 다시 시도해줘.") from exc


def api_my_account_picture_v5():
    if not legacy.is_logged_in():
        return jsonify({"ok": False, "error": "로그인이 필요해."}), 401

    try:
        raw = _read_picture_bytes()
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    max_bytes = _int_env("PROFILE_IMAGE_MAX_MB", 3, min_value=1, max_value=8) * 1024 * 1024
    if len(raw) > max_bytes:
        return jsonify({"ok": False, "error": "프로필 사진은 3MB 이하로 올려줘."}), 413

    login_id = legacy.safe_str(session.get("login_id")).strip()
    login_row = legacy.get_login_by_id(login_id, include_trash=True)
    if not login_row:
        return jsonify({"ok": False, "error": "계정을 찾지 못했어."}), 404

    try:
        image_bytes = _normalize_profile_image(raw)
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    filename = _profile_filename(login_id)
    _PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = _PROFILE_DIR / filename
    output_path.write_bytes(image_bytes)

    picture_url = f"/static/profile_pictures/{filename}?v={int(time.time())}"
    try:
        legacy.update_cell_by_header(legacy.id_ws, login_row["row_index"], "picture", picture_url)
    except ValueError:
        return jsonify({"ok": False, "error": "id 시트에 picture 헤더가 필요해."}), 400

    return jsonify({"ok": True, "picture": picture_url})


@app.after_request
def _inject_profile_assets(response):
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type or request.path.startswith(("/kiosk", "/api")):
        return response
    try:
        html = response.get_data(as_text=True)
    except Exception:
        return response
    marker = "admin_v5_profile.js"
    if "</body>" not in html or marker in html:
        return response
    html = html.replace("</body>", '<script src="/static/admin/admin_v5_profile.js"></script></body>')
    response.set_data(html)
    response.headers["Content-Length"] = str(len(response.get_data()))
    return response


app.view_functions["api_my_account_picture"] = api_my_account_picture_v5
