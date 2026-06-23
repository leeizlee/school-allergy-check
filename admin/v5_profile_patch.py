import base64
import binascii
import io
import hashlib
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


def _update_cells(ws, row_index, values):
    headers = [legacy.safe_str(item).strip() for item in ws.row_values(1)]
    changed_headers = False
    for header_name in values:
        if header_name not in headers:
            headers.append(header_name)
            ws.update_cell(1, len(headers), header_name)
            changed_headers = True
    header_map = {header: index for index, header in enumerate(headers, start=1)}
    for header_name, value in values.items():
        ws.update_cell(row_index, header_map[header_name], value)
    try:
        legacy._invalidate_sheet_cache(ws)
    except Exception:
        pass
    return changed_headers


def _raw_login_row(login_id):
    try:
        records = legacy._cached_get_all_records(legacy.id_ws)
    except Exception:
        records = legacy.id_ws.get_all_records()
    target = legacy.safe_str(login_id).strip()
    for row_index, record in enumerate(records, start=2):
        row = legacy.clean_record_keys(record)
        if legacy.safe_str(row.get("id")).strip() == target:
            row["row_index"] = row_index
            return row
    return None


def _decode_picture_value(row, blob_key="picture_blob", picture_key="picture"):
    blob = legacy.safe_str((row or {}).get(blob_key)).strip()
    if blob:
        try:
            return base64.b64decode(blob, validate=True)
        except Exception:
            return b""
    picture = legacy.safe_str((row or {}).get(picture_key)).strip()
    if _DATA_URL_RE.match(picture):
        try:
            return base64.b64decode(_DATA_URL_RE.sub("", picture), validate=True)
        except Exception:
            return b""
    return b""


def _picture_version(image_bytes):
    return hashlib.sha256(image_bytes).hexdigest()[:12] if image_bytes else ""


def _profile_url(login_id, image_bytes, previous=False):
    if not image_bytes:
        return ""
    filename = _profile_filename(login_id)
    prefix = "/profile-pictures/previous" if previous else "/profile-pictures"
    return f"{prefix}/{filename}?v={_picture_version(image_bytes)}"


def _store_profile_image(login_id, row_index, image_bytes, remember_previous=True):
    current_row = _raw_login_row(login_id) or {}
    current_bytes = _decode_picture_value(current_row)
    values = {}
    if remember_previous and current_bytes and current_bytes != image_bytes:
        values.update({
            "picture_previous": _profile_url(login_id, current_bytes, previous=True),
            "picture_blob_previous": base64.b64encode(current_bytes).decode("ascii"),
        })

    filename = _profile_filename(login_id)
    _PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    (_PROFILE_DIR / filename).write_bytes(image_bytes)
    picture_url = _profile_url(login_id, image_bytes)
    values.update({
        "picture": picture_url,
        "picture_blob": base64.b64encode(image_bytes).decode("ascii"),
        "picture_updated_at": legacy.now_time_str(),
    })
    _update_cells(legacy.id_ws, row_index, values)
    return picture_url


def _picture_blob_for_filename(filename, previous=False):
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
        image_bytes = _decode_picture_value(
            row,
            "picture_blob_previous" if previous else "picture_blob",
            "picture_previous" if previous else "picture",
        )
        if image_bytes:
            return base64.b64encode(image_bytes).decode("ascii")
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

    try:
        picture_url = _store_profile_image(login_id, login_row["row_index"], image_bytes)
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


@app.get("/profile-pictures/previous/<path:filename>")
def previous_profile_picture_file(filename):
    if not legacy.is_logged_in():
        abort(404)
    blob = _picture_blob_for_filename(Path(filename).name, previous=True)
    if not blob:
        abort(404)
    try:
        return Response(base64.b64decode(blob), mimetype="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})
    except Exception:
        abort(404)


@app.get("/api/my-account/picture/history")
def api_my_account_picture_history():
    if not legacy.is_logged_in():
        return jsonify({"ok": False, "error": "로그인이 필요해."}), 401
    login_id = legacy.safe_str(session.get("login_id")).strip()
    row = _raw_login_row(login_id)
    if not row:
        return jsonify({"ok": False, "error": "계정을 찾지 못했어."}), 404
    current_bytes = _decode_picture_value(row)
    previous_bytes = _decode_picture_value(row, "picture_blob_previous", "picture_previous")
    return jsonify({
        "ok": True,
        "current": _profile_url(login_id, current_bytes),
        "previous": _profile_url(login_id, previous_bytes, previous=True),
    })


_original_get_all_student_rows = legacy.get_all_student_rows


def _get_all_student_rows_with_pictures(include_trash=False):
    rows = _original_get_all_student_rows(include_trash=include_trash)
    try:
        login_records = legacy._cached_get_all_records(legacy.id_ws)
    except Exception:
        login_records = legacy.id_ws.get_all_records()
    login_map = {}
    for record in login_records:
        login_row = legacy.clean_record_keys(record)
        login_id = legacy.safe_str(login_row.get("id")).strip()
        if login_id:
            login_map[login_id] = login_row
    for row in rows:
        login_id = legacy.safe_str(row.get("student_number")).strip()
        image_bytes = _decode_picture_value(login_map.get(login_id) or {})
        row["picture"] = _profile_url(login_id, image_bytes) if image_bytes else ""
    return rows


legacy.get_all_student_rows = _get_all_student_rows_with_pictures


@app.post("/api/admin/student/<int:row_index>/picture")
def api_admin_student_picture(row_index):
    ok, response = legacy.require_admin_api()
    if not ok:
        return response
    target = next(
        (row for row in _original_get_all_student_rows(include_trash=True) if row.get("row_index") == row_index),
        None,
    )
    if not target:
        return jsonify({"ok": False, "error": "학생을 찾지 못했어."}), 404
    login_id = legacy.safe_str(target.get("student_number")).strip()
    login_row = legacy.get_login_by_id(login_id, include_trash=True)
    if not login_row:
        return jsonify({"ok": False, "error": "학생 로그인 계정을 찾지 못했어."}), 404
    try:
        raw = _read_picture_bytes()
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    max_mb = _int_env("PROFILE_IMAGE_MAX_MB", 3, min_value=1, max_value=8)
    if len(raw) > max_mb * 1024 * 1024:
        return jsonify({"ok": False, "error": f"학생 프로필 사진은 {max_mb}MB 이하로 올려줘."}), 413
    try:
        image_bytes = _normalize_profile_image(raw)
        picture_url = _store_profile_image(login_id, login_row["row_index"], image_bytes)
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
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
    if "</body>" in html and "admin_v5_student_profile.js" not in html:
        html = html.replace("</body>", '<script src="/static/admin/admin_v5_student_profile.js"></script></body>')
        changed = True

    if changed:
        response.set_data(html)
        response.headers["Content-Length"] = str(len(response.get_data()))
    return response


app.view_functions["api_my_account_picture"] = api_my_account_picture_v5
