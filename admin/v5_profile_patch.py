import base64
import binascii
import io
import os
import re
import time
from pathlib import Path

from flask import Response, abort, jsonify, request, send_file, session

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
            image = image.resize((192, 192), Image.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=88, optimize=True)
            return output.getvalue()
    except Exception as exc:
        raise ValueError("이미지를 처리하지 못했어. 다른 사진으로 다시 시도해줘.") from exc


def _ensure_header(ws, header_name):
    headers = [legacy.safe_str(item).strip() for item in ws.row_values(1)]
    if header_name in headers:
        return True
    ws.update_cell(1, len(headers) + 1, header_name)
    try:
        legacy._invalidate_sheet_cache(ws)
    except Exception:
        pass
    return True


def _update_login_cell(row_index, header_name, value):
    try:
        legacy.update_cell_by_header(legacy.id_ws, row_index, header_name, value)
        return True
    except ValueError:
        _ensure_header(legacy.id_ws, header_name)
        legacy.update_cell_by_header(legacy.id_ws, row_index, header_name, value)
        return True


def _picture_blob_for_filename(filename):
    target = Path(filename).name
    try:
        records = legacy._cached_get_all_records(legacy.id_ws)
    except Exception:
        records = legacy.id_ws.get_all_records()
    for record in records:
        row = legacy.clean_record_keys(record)
        login_id = legacy.safe_str(row.get("id")).strip()
        if _profile_filename(login_id) != target:
            continue
        blob = legacy.safe_str(row.get("picture_blob")).strip()
        if blob:
            return blob
    return ""


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

    picture_url = f"/profile-pictures/{filename}?v={int(time.time())}"
    try:
        _update_login_cell(login_row["row_index"], "picture", picture_url)
        _update_login_cell(login_row["row_index"], "picture_blob", base64.b64encode(image_bytes).decode("ascii"))
    except ValueError:
        return jsonify({"ok": False, "error": "id 시트에 picture 헤더가 필요해."}), 400

    return jsonify({"ok": True, "picture": picture_url})


@app.get("/profile-pictures/<path:filename>")
def profile_picture_file(filename):
    safe_name = Path(filename).name
    output_path = _PROFILE_DIR / safe_name
    if output_path.exists() and output_path.is_file():
        return send_file(output_path, mimetype="image/jpeg", max_age=3600)
    blob = _picture_blob_for_filename(safe_name)
    if not blob:
        abort(404)
    try:
        return Response(base64.b64decode(blob), mimetype="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})
    except Exception:
        abort(404)


@app.after_request
def _inject_profile_assets(response):
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type or request.path.startswith(("/kiosk", "/api")):
        return response
    try:
        html = response.get_data(as_text=True)
    except Exception:
        return response

    changed = False
    if "</head>" in html and "admin_v5_ui_cleanup.css" not in html:
        html = html.replace("</head>", '<link rel="stylesheet" href="/static/admin/admin_v5_ui_cleanup.css"></head>')
        changed = True
    if "</body>" in html and "admin_v5_ui_cleanup.js" not in html:
        html = html.replace("</body>", '<script src="/static/admin/admin_v5_ui_cleanup.js"></script></body>')
        changed = True
    if "</body>" in html and "admin_v5_profile.js" not in html:
        html = html.replace("</body>", '<script src="/static/admin/admin_v5_profile.js"></script></body>')
        changed = True

    if changed:
        response.set_data(html)
        response.headers["Content-Length"] = str(len(response.get_data()))
    return response


app.view_functions["api_my_account_picture"] = api_my_account_picture_v5
