import threading
import time
import uuid

from flask import jsonify, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from admin import app_admin as legacy
from admin import v5_admin_renderer
from admin.app_admin import app


_AI_MEAL_JOBS = {}
_AI_MEAL_LOCK = threading.Lock()
_ADMIN_EVENTS = []
_ADMIN_EVENTS_LOCK = threading.Lock()
_AI_JOB_TTL_SECONDS = 60 * 60 * 6


@app.after_request
def _inject_v5_notification_assets(response):
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type or request.path.startswith(("/kiosk", "/api")):
        return response
    try:
        html = response.get_data(as_text=True)
    except Exception:
        return response
    marker = "admin_v5_notifications.js"
    if "</body>" not in html or marker in html:
        return response
    html = html.replace("</body>", '<script src="/static/admin/admin_v5_notifications.js"></script></body>')
    response.set_data(html)
    response.headers["Content-Length"] = str(len(response.get_data()))
    return response


def _add_admin_event(item):
    if not item or not item.get("id"):
        return
    with _ADMIN_EVENTS_LOCK:
        _ADMIN_EVENTS.insert(0, dict(item))
        del _ADMIN_EVENTS[40:]


def _admin_events():
    with _ADMIN_EVENTS_LOCK:
        return [dict(item) for item in _ADMIN_EVENTS]


def _cleanup_ai_jobs():
    now = time.time()
    with _AI_MEAL_LOCK:
        old_ids = [
            job_id
            for job_id, job in _AI_MEAL_JOBS.items()
            if now - float(job.get("created_ts") or now) > _AI_JOB_TTL_SECONDS
        ]
        for job_id in old_ids:
            _AI_MEAL_JOBS.pop(job_id, None)


def _set_ai_job(job_id, **updates):
    with _AI_MEAL_LOCK:
        job = _AI_MEAL_JOBS.get(job_id)
        if not job:
            return None
        job.update(updates)
        return dict(job)


def _get_ai_job(job_id):
    with _AI_MEAL_LOCK:
        job = _AI_MEAL_JOBS.get(job_id)
        return dict(job) if job else None


def _event_time():
    return time.strftime("%m/%d %H:%M")


def _notification_from_log(row):
    result = row.get("result") or "스캔"
    return {
        "id": f"log:{row.get('scanned_at') or ''}:{row.get('rfid_id') or ''}:{result}",
        "target": "lunch_log",
        "path": "/lunch-log",
        "icon": "RF",
        "title": f"{row.get('name') or row.get('rfid_id') or '미등록 RFID'} 학생증 인식",
        "detail": f"{result} 판정 · {row.get('hit_names') or '위험 없음'}",
        "time": row.get("scanned_at") or "-",
        "kind": "danger" if result == "경고" else ("warn" if result == "미등록" else "safe"),
    }


def _build_notifications():
    items = []
    try:
        items.extend(_admin_events())
        for row in legacy.get_all_lunch_log_rows()[:8]:
            items.append(_notification_from_log(row))
        for row in legacy.get_all_student_rows()[:5]:
            if row.get("created_at"):
                items.append({
                    "id": f"student:{row.get('student_number') or row.get('row_index') or row.get('name')}:{row.get('created_at')}",
                    "target": "student_manage",
                    "path": "/student-manage",
                    "icon": "ST",
                    "title": f"{row.get('name') or '학생'} 등록",
                    "detail": row.get("student_number") or "학생 정보가 등록됐습니다.",
                    "time": row.get("created_at"),
                    "kind": "info",
                })
        for row in legacy.get_all_menu_rows()[:5]:
            items.append({
                "id": f"menu:{row.get('date') or ''}:{row.get('menu_name') or row.get('row_index') or ''}:{row.get('updated_at') or row.get('created_at') or ''}",
                "target": "menu_manage",
                "path": "/menu-manage",
                "icon": "ME",
                "title": "메뉴 수정" if row.get("updated_at") else "메뉴 등록",
                "detail": row.get("menu_name") or row.get("date") or "급식 메뉴",
                "time": row.get("updated_at") or row.get("created_at") or row.get("date") or "-",
                "kind": "ai",
            })
    except Exception:
        return _admin_events()
    seen = set()
    deduped = []
    for item in items:
        item_id = item.get("id")
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        deduped.append(item)
    return deduped[:30]


def _run_meal_analysis_job(job_id, saved_path, filename, created_by, ocr_hint):
    _set_ai_job(job_id, status="running", message="급식표를 읽고 있어.")
    try:
        if legacy.is_spreadsheet_meal_upload(filename):
            ocr_text = legacy.extract_meal_spreadsheet_text(saved_path)
            source_label = "스프레드시트"
        else:
            ocr_text = legacy.extract_text(saved_path)
            source_label = "OCR"

        analysis_input = ocr_text
        if ocr_hint:
            analysis_input = f"{ocr_text}\n\n[관리자 메모]\n{ocr_hint}"
        analysis_input = f"[입력 방식: {source_label}]\n{analysis_input}"
        analysis = legacy.analyze_meal_ocr_text(analysis_input, legacy.AI_ALLERGY_DICT)
        preview = legacy.build_meal_preview_context(analysis)
        _set_ai_job(job_id, status="done", message="AI 급식표 분석이 완료됐어.", preview=preview, ocr_text=ocr_text)
        _add_admin_event({
            "id": f"ai-meal:{job_id}",
            "target": "meal_ai",
            "path": f"/admin/meal/analyze/result/{job_id}",
            "icon": "AI",
            "title": "AI 급식표 분석 완료",
            "detail": "분석 결과를 검토할 수 있어.",
            "time": _event_time(),
            "kind": "ai",
        })
    except Exception as exc:
        error = legacy.safe_str(exc) or "AI 급식표 분석에 실패했어."
        _set_ai_job(job_id, status="error", message=error, error=error)
        _add_admin_event({
            "id": f"ai-meal-error:{job_id}",
            "target": "meal_ai",
            "path": "/admin/meal/upload",
            "icon": "AI",
            "title": "AI 급식표 분석 실패",
            "detail": error,
            "time": _event_time(),
            "kind": "danger",
        })


@app.get("/notifications")
@app.get("/admin/notifications")
def notifications_page():
    ok, response = legacy.require_admin()
    if not ok:
        return response
    context = v5_admin_renderer._build_context("알림센터", "RFID 인식, 학생/메뉴 변경, AI 작업 완료 알림을 한곳에서 확인해.", "admin_home")
    context["active_tab"] = "notifications"
    context["notifications"] = _build_notifications()
    return render_template("admin/notifications.html", **context)


@app.get("/api/admin/notifications")
def api_admin_notifications():
    ok, response = legacy.require_admin_api()
    if not ok:
        return response
    return jsonify({"ok": True, "notifications": _build_notifications()})


@app.post("/api/meal/analyze-async")
def api_meal_analyze_async():
    ok, response = legacy.require_admin_api()
    if not ok:
        return response

    created_by = legacy.safe_str(request.form.get("created_by")).strip() or session.get("login_name", legacy.DEFAULT_ADMIN_NAME)
    ocr_hint = legacy.safe_str(request.form.get("ocr_hint")).strip()
    upload = request.files.get("meal_file") or request.files.get("meal_image")
    if not upload or not legacy.safe_str(upload.filename).strip():
        return jsonify({"ok": False, "error": "급식표 이미지나 스프레드시트 파일을 먼저 선택해줘."}), 400
    if not legacy.is_allowed_meal_upload(upload.filename):
        return jsonify({"ok": False, "error": "PNG, JPG, JPEG, WEBP, BMP, XLSX, CSV, TSV 파일만 업로드할 수 있어."}), 400

    _cleanup_ai_jobs()
    safe_name = secure_filename(upload.filename) or "meal_upload"
    saved_path = legacy.MEAL_UPLOAD_DIR / f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{safe_name}"
    upload.save(saved_path)
    job_id = uuid.uuid4().hex
    with _AI_MEAL_LOCK:
        _AI_MEAL_JOBS[job_id] = {"id": job_id, "status": "queued", "message": "AI 급식표 분석 대기 중이야.", "created_by": created_by, "created_ts": time.time(), "filename": safe_name}
    threading.Thread(target=_run_meal_analysis_job, args=(job_id, saved_path, upload.filename, created_by, ocr_hint), daemon=True).start()
    return jsonify({"ok": True, "job_id": job_id, "status": "queued", "message": "분석 작업을 시작했어. 다른 기능을 사용해도 돼.", "status_url": url_for("api_meal_analyze_job", job_id=job_id)})


@app.get("/api/meal/analyze-jobs/<job_id>")
def api_meal_analyze_job(job_id):
    ok, response = legacy.require_admin_api()
    if not ok:
        return response
    job = _get_ai_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "분석 작업을 찾지 못했어. 서버가 재시작됐을 수 있어."}), 404
    payload = {"ok": True, "job_id": job_id, "status": job.get("status"), "message": job.get("message") or "", "filename": job.get("filename") or ""}
    if job.get("status") == "done":
        payload["redirect"] = url_for("meal_analyze_result_page", job_id=job_id)
        payload["notification"] = {"id": f"ai-meal:{job_id}", "target": "meal_ai", "kind": "ai", "icon": "AI", "title": "AI 급식표 분석 완료", "detail": f"{job.get('filename') or '급식표'} 분석 결과를 검토할 수 있어.", "time": _event_time(), "path": url_for("meal_analyze_result_page", job_id=job_id)}
    if job.get("status") == "error":
        payload["error"] = job.get("error") or job.get("message") or "분석 실패"
        payload["notification"] = {"id": f"ai-meal-error:{job_id}", "target": "meal_ai", "kind": "danger", "icon": "AI", "title": "AI 급식표 분석 실패", "detail": payload["error"], "time": _event_time(), "path": url_for("meal_upload_page")}
    return jsonify(payload)


@app.get("/admin/meal/analyze/result/<job_id>")
def meal_analyze_result_page(job_id):
    ok, response = legacy.require_admin()
    if not ok:
        return response
    job = _get_ai_job(job_id)
    if not job or job.get("status") != "done":
        return legacy.render_admin_page("AI급식추가", "급식표 이미지와 스프레드시트를 AI로 분석하고 저장 전 검토할 수 있어.", "meal_ai", meal_mode="upload", meal_error="분석 결과가 아직 준비되지 않았거나 서버가 재시작됐어.", meal_created_by=session.get("login_name", legacy.DEFAULT_ADMIN_NAME)), 404
    return legacy.render_admin_page("AI급식추가", "AI 분석 결과를 확인하고 food_menu 저장 형식으로 수정할 수 있어.", "meal_ai", meal_mode="preview", meal_preview=job.get("preview") or {"rows": [], "warnings": [], "warning_count": 0}, meal_ocr_text=job.get("ocr_text") or "", meal_error="", meal_created_by=job.get("created_by") or session.get("login_name", legacy.DEFAULT_ADMIN_NAME))
