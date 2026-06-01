import os
import threading
import time
import uuid
from datetime import datetime

from flask import jsonify, request, session, url_for

from admin import app_admin as legacy
from admin import v5_runtime_patch as realtime
from admin.app_admin import app


_JOBS = {}
_JOBS_LOCK = threading.Lock()
_JOB_TTL_SECONDS = int(os.getenv("ADMIN_BACKGROUND_JOB_TTL_SECONDS", str(60 * 60 * 8)))
_MAX_ATTEMPTS = int(os.getenv("ADMIN_BACKGROUND_JOB_MAX_ATTEMPTS", "8"))
_RETRY_BASE_SECONDS = int(os.getenv("ADMIN_BACKGROUND_JOB_RETRY_BASE_SECONDS", "75"))
_RETRY_MAX_SECONDS = int(os.getenv("ADMIN_BACKGROUND_JOB_RETRY_MAX_SECONDS", "900"))

_RETRYABLE_MARKERS = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "quota",
    "rate limit",
    "rate_limit",
    "resource_exhausted",
    "too many requests",
    "limit exceeded",
    "user rate limit",
    "temporarily unavailable",
    "deadline exceeded",
    "timeout",
    "timed out",
    "try again",
    "backend error",
    "internal error",
    "할당량",
    "사용량",
    "제한",
    "잠시 후",
)
_MEAL_SAVE_ROLES = {"a", "admin", "super", "superadmin", "n", "nutritionist", "dietitian", "영양사"}


def _now_label():
    return datetime.now().strftime("%m/%d %H:%M")


def _now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_text(value, default=""):
    text = legacy.safe_str(value).strip()
    return text if text else default


def _role_key():
    return legacy.safe_str(session.get("role")).strip().lower()


def _is_retryable_error(exc):
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in _RETRYABLE_MARKERS)


def _retry_delay(attempt):
    delay = _RETRY_BASE_SECONDS * max(1, attempt)
    return max(5, min(delay, _RETRY_MAX_SECONDS))


def _public_job(job):
    hidden = {"worker", "notification", "success_detail"}
    return {key: value for key, value in (job or {}).items() if key not in hidden}


def _set_job(job_id, **updates):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        job.update(updates)
        job["updated_at"] = _now_iso()
        return _public_job(job)


def _get_job(job_id):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def _cleanup_jobs():
    now = time.time()
    with _JOBS_LOCK:
        old_ids = [
            job_id
            for job_id, job in _JOBS.items()
            if now - float(job.get("created_ts") or now) > _JOB_TTL_SECONDS
        ]
        for job_id in old_ids:
            _JOBS.pop(job_id, None)


def _notify(job, status, detail=None, kind=None):
    target = job.get("target") or "notifications"
    path = job.get("path") or "/notifications"
    title = job.get("success_title") if status == "done" else job.get("failure_title")
    if not title:
        title = job.get("title") or "작업 알림"
    event_id = f"job:{job['id']}:{status}"
    realtime._add_admin_event(
        {
            "id": event_id,
            "target": target,
            "path": path,
            "icon": job.get("icon") or "AI",
            "title": title,
            "detail": detail or job.get("message") or "",
            "time": _now_label(),
            "kind": kind or ("danger" if status == "error" else "ai"),
        }
    )
    return {
        "id": event_id,
        "target": target,
        "path": path,
        "icon": job.get("icon") or "AI",
        "title": title,
        "detail": detail or job.get("message") or "",
        "time": _now_label(),
        "kind": kind or ("danger" if status == "error" else "ai"),
    }


def _run_background_job(job_id):
    while True:
        job = _get_job(job_id)
        if not job:
            return

        attempt = int(job.get("attempts") or 0) + 1
        _set_job(job_id, status="running", attempts=attempt, message=f"작업을 실행하고 있어. ({attempt}/{job.get('max_attempts')})")

        try:
            result = job["worker"]()
            detail = job.get("success_detail")
            if callable(detail):
                detail = detail(result)
            detail = detail or "작업이 완료됐어."
            notification = _notify(job, "done", detail=detail, kind=job.get("kind") or "ai")
            _set_job(job_id, status="done", message=detail, result=result or {}, notification=notification)
            return
        except Exception as exc:
            retryable = _is_retryable_error(exc)
            error = _safe_text(exc, "작업 처리 중 오류가 발생했어.")
            if retryable and attempt < int(job.get("max_attempts") or _MAX_ATTEMPTS):
                delay = _retry_delay(attempt)
                retry_at = time.time() + delay
                _set_job(
                    job_id,
                    status="waiting",
                    message=f"Google Sheets 사용량 제한으로 잠시 대기 중이야. 약 {delay}초 뒤 자동 재시도할게.",
                    error=error,
                    retry_at=retry_at,
                )
                time.sleep(delay)
                continue

            detail = f"{error} 다시 시도해줘." if not retryable else f"{error} 자동 재시도 한도를 넘었어."
            notification = _notify(job, "error", detail=detail, kind="danger")
            _set_job(job_id, status="error", message=detail, error=error, notification=notification)
            return


def _start_job(kind, title, target, path, worker, success_title=None, failure_title=None, success_detail=None, icon="AI"):
    _cleanup_jobs()
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "kind": kind,
        "title": title,
        "target": target,
        "path": path,
        "icon": icon,
        "status": "queued",
        "message": "작업을 대기열에 등록했어.",
        "attempts": 0,
        "max_attempts": _MAX_ATTEMPTS,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "created_ts": time.time(),
        "success_title": success_title or title,
        "failure_title": failure_title or f"{title} 실패",
        "success_detail": success_detail,
        "worker": worker,
    }
    with _JOBS_LOCK:
        _JOBS[job_id] = job
    threading.Thread(target=_run_background_job, args=(job_id,), daemon=True).start()
    return _public_job(job)


def _existing_active_students():
    students = legacy.get_all_student_rows(include_trash=True)
    return {
        "rfid": {row.get("rfid_id") for row in students if row.get("trash") == "0" and row.get("rfid_id")},
        "number": {row.get("student_number") for row in students if row.get("trash") == "0" and row.get("student_number")},
    }


def _existing_active_logins():
    logins = legacy.get_all_login_rows(include_trash=True)
    return {row.get("id") for row in logins if row.get("trash") == "0" and row.get("id")}


def _append_students_idempotently(rows, created_by):
    student_existing = _existing_active_students()
    login_existing = _existing_active_logins()
    created_at = legacy.now_time_str()
    student_rows = []
    login_rows = []
    added = []
    skipped = []

    for index, row in enumerate(rows or [], start=1):
        rfid_id = _safe_text((row or {}).get("rfid_id"))
        name = _safe_text((row or {}).get("name"))
        student_number = "".join(ch for ch in _safe_text((row or {}).get("student_number")) if ch.isdigit())
        allergy_codes = sorted(legacy.parse_codes((row or {}).get("allergy_codes", [])))
        parts = legacy.student_number_to_parts(student_number)

        reason = ""
        if not name or not student_number:
            reason = "이름 또는 학번이 비어 있어."
        elif parts["class_key"] == "unknown":
            reason = "학번 형식이 올바르지 않아."
        elif rfid_id and rfid_id in student_existing["rfid"]:
            reason = "이미 등록된 RFID야."

        if reason:
            skipped.append({"index": index, "name": name, "student_number": student_number, "reason": reason})
            continue

        needs_student = student_number not in student_existing["number"]
        needs_login = student_number not in login_existing
        if not needs_student and not needs_login:
            skipped.append({"index": index, "name": name, "student_number": student_number, "reason": "이미 등록된 학번이야."})
            continue

        if needs_student:
            student_rows.append(
                {
                    "rfid_id": rfid_id,
                    "name": name,
                    "allergy_codes": ",".join(str(code) for code in allergy_codes),
                    "student_number": student_number,
                    "student_no": student_number,
                    "created_by": created_by,
                    "created_at": created_at,
                    "trash": "0",
                }
            )
            if rfid_id:
                student_existing["rfid"].add(rfid_id)
            student_existing["number"].add(student_number)

        if needs_login:
            login_rows.append(
                {
                    "id": student_number,
                    "name": name,
                    "pw": legacy.hash_password(legacy.DEFAULT_STUDENT_PASSWORD),
                    "role": "s",
                    "trash": "0",
                }
            )
            login_existing.add(student_number)

        added.append({"name": name, "student_number": student_number})

    if student_rows:
        legacy.append_rows_by_headers(legacy.student_ws, student_rows)
    if login_rows:
        legacy.append_rows_by_headers(legacy.id_ws, login_rows)
    return {"added_count": len(added), "skipped_count": len(skipped), "added": added, "skipped": skipped}


def _append_menus_idempotently(analysis, created_by):
    existing = set()
    for row in legacy.get_all_menu_rows(include_trash=True):
        existing.add(
            (
                legacy.compact_date_value(row.get("date")),
                _safe_text(row.get("menu_name")),
                tuple(sorted(legacy.parse_codes(row.get("allergy_codes")))),
                "1" if _safe_text(row.get("trash")) == "1" else "0",
            )
        )

    saved = []
    for row in legacy.merge_duplicate_menu_rows(analysis.get("rows", [])):
        date_value = legacy.compact_date_value(row.get("date"))
        menu_name = _safe_text(row.get("menu_name"))
        if not date_value or not menu_name:
            continue
        allergy_codes = sorted(legacy.parse_codes(row.get("allergy_codes", [])))
        trash = "1" if _safe_text(row.get("trash", "0")) == "1" else "0"
        key = (date_value, menu_name, tuple(allergy_codes), trash)
        if key in existing:
            continue

        row_created_by = _safe_text(row.get("created_by"), created_by)
        legacy.append_row_by_headers(
            legacy.menu_ws,
            {
                "date": date_value,
                "menu_name": menu_name,
                "allergy_codes": ",".join(str(code) for code in allergy_codes),
                "created_by": row_created_by,
                "created_at": legacy.now_time_str(),
                "trash": trash,
            },
        )
        existing.add(key)
        saved.append({"date": date_value, "menu_name": menu_name, "allergy_codes": allergy_codes, "created_by": row_created_by, "trash": trash})
    return {"saved_count": len(saved), "saved_rows": saved}


@app.after_request
def _inject_background_job_assets(response):
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type or request.path.startswith(("/kiosk", "/api")):
        return response
    try:
        html = response.get_data(as_text=True)
    except Exception:
        return response
    if "admin_v5_workflow.js" not in html and "</body>" in html:
        html = html.replace("</body>", '<script defer src="/static/admin/admin_v5_workflow.js"></script></body>')
    if "admin_v5_typography.css" not in html and "</head>" in html:
        html = html.replace("</head>", '<link rel="stylesheet" href="/static/admin/admin_v5_typography.css"></head>')
    response.set_data(html)
    response.headers["Content-Length"] = str(len(response.get_data()))
    return response


@app.post("/api/meal/save-async")
def api_meal_save_async():
    ok, response = legacy.require_admin_api()
    if not ok:
        return response
    if _role_key() not in _MEAL_SAVE_ROLES:
        return jsonify({"ok": False, "error": "현재 계정 권한으로는 급식 저장 작업을 실행할 수 없어."}), 403
    created_by = _safe_text(request.form.get("created_by"), session.get("login_name", legacy.DEFAULT_ADMIN_NAME))
    try:
        analysis = legacy.parse_preview_form(request.form)
        if not analysis.get("rows"):
            return jsonify({"ok": False, "error": "저장할 급식 행이 없어. 날짜와 메뉴를 1개 이상 입력해줘."}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": _safe_text(exc, "급식 저장 데이터를 읽지 못했어.")}), 400

    def worker():
        return _append_menus_idempotently(analysis, created_by)

    job = _start_job(
        "meal_save",
        "AI급식추가 - 저장 작업",
        "menu_manage",
        url_for("menu_manage_page"),
        worker,
        success_title="급식관리 - AI급식 저장 완료",
        failure_title="급식관리 - AI급식 저장 실패",
        success_detail=lambda result: f"{result.get('saved_count', 0)}개 급식 메뉴를 Google Sheets에 저장했어.",
        icon="ME",
    )
    return jsonify({"ok": True, "pending": True, "job": job, "job_id": job["id"], "status_url": url_for("api_admin_background_job", job_id=job["id"])}), 202


@app.get("/api/admin/background-jobs")
def api_admin_background_jobs():
    ok, response = legacy.require_admin_api()
    if not ok:
        return response
    _cleanup_jobs()
    with _JOBS_LOCK:
        jobs = [_public_job(job) for job in sorted(_JOBS.values(), key=lambda item: item.get("created_ts", 0), reverse=True)]
    return jsonify({"ok": True, "jobs": jobs[:40]})


@app.get("/api/admin/background-jobs/<job_id>")
def api_admin_background_job(job_id):
    ok, response = legacy.require_admin_api()
    if not ok:
        return response
    job = _get_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "작업을 찾지 못했어. 서버가 재시작됐을 수 있어."}), 404
    return jsonify({"ok": True, "job": _public_job(job)})


_original_student_sheet_confirm = app.view_functions.get("api_student_sheet_confirm")


def _quota_safe_student_sheet_confirm():
    try:
        return _original_student_sheet_confirm()
    except Exception as exc:
        if not _is_retryable_error(exc):
            raise
        data = request.get_json(force=True) or {}
        rows = data.get("rows", [])
        if not rows:
            return jsonify({"ok": False, "error": "추가할 학생 데이터가 없어."}), 400
        created_by = session.get("login_name", legacy.DEFAULT_ADMIN_NAME)

        def worker():
            return _append_students_idempotently(rows, created_by)

        job = _start_job(
            "student_import",
            "학생관리 - 시트 대량 등록",
            "student_manage",
            url_for("student_manage_page"),
            worker,
            success_title="학생관리 - 시트 대량 등록 완료",
            failure_title="학생관리 - 시트 대량 등록 실패",
            success_detail=lambda result: f"{result.get('added_count', 0)}명 학생 등록을 완료했어.",
            icon="ST",
        )
        return jsonify(
            {
                "ok": True,
                "pending": True,
                "job": job,
                "job_id": job["id"],
                "status_url": url_for("api_admin_background_job", job_id=job["id"]),
                "message": "Google Sheets 사용량 제한으로 작업을 백그라운드 재시도 대기열에 넣었어.",
            }
        ), 202


if _original_student_sheet_confirm is not None:
    app.view_functions["api_student_sheet_confirm"] = _quota_safe_student_sheet_confirm
