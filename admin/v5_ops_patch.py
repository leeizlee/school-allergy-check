import json
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import jsonify, render_template, request, session

from admin import app_admin as legacy
from admin import v5_admin_renderer
from admin import v5_runtime_patch as realtime
from admin.app_admin import app


_AUDIT_LOGS = []
_AUDIT_LOCK = threading.Lock()
_AUDIT_PATH = Path(os.getenv("ADMIN_AUDIT_LOG_PATH", "runtime/admin_audit.jsonl"))
_STARTED_AT = time.time()

_AUDIT_ACTIONS = {
    "login_page": ("로그인", "계정", "관리자/사용자 로그인 시도"),
    "api_add_student": ("학생 추가", "학생관리", "학생 단건 등록"),
    "api_student_sheet_confirm": ("학생 대량 추가", "학생관리", "시트 미리보기 확정"),
    "api_student_update": ("학생 수정", "학생관리", "학생 정보 수정"),
    "api_student_reset_password": ("학생 비밀번호 초기화", "학생관리", "학생 비밀번호 재설정"),
    "api_delete_selected_students": ("학생 삭제", "학생관리", "선택 학생 휴지통 이동"),
    "api_add_menu": ("급식 추가", "급식관리", "급식 메뉴 등록"),
    "api_menu_group_update": ("급식 수정", "급식관리", "날짜별 급식 메뉴 수정"),
    "api_delete_selected_menus": ("급식 삭제", "급식관리", "선택 급식 휴지통 이동"),
    "meal_save_page": ("AI 급식 저장", "AI", "AI 분석 급식표 저장"),
    "api_meal_analyze_async": ("AI 급식 분석", "AI", "급식표 백그라운드 분석 시작"),
    "api_ai_safety_plan": ("학생 안전계획 생성", "AI", "학생별 AI 안전계획 생성"),
    "api_ai_daily_brief": ("오늘 위험 브리핑", "AI", "AI 당일 위험 브리핑 생성"),
    "api_ai_menu_review": ("메뉴 코드 점검", "AI", "AI 메뉴 알레르기 코드 점검"),
    "api_trash_menu_restore": ("급식 복구", "휴지통", "삭제 급식 복구"),
    "api_trash_student_restore": ("학생 복구", "휴지통", "삭제 학생 복구"),
    "api_trash_menu_hard_delete": ("급식 완전삭제", "휴지통", "급식 데이터 완전삭제"),
    "api_trash_student_hard_delete": ("학생 완전삭제", "휴지통", "학생 데이터 완전삭제"),
    "api_my_account_update": ("계정정보 수정", "설정", "관리자 계정 정보 수정"),
    "api_my_account_reset_password": ("비밀번호 변경", "설정", "관리자 비밀번호 변경"),
}


@app.after_request
def _inject_ops_assets(response):
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type or request.path.startswith(("/kiosk", "/api")):
        return response
    try:
        html = response.get_data(as_text=True)
    except Exception:
        return response
    marker = "admin_v5_ops.js"
    if "</body>" not in html or marker in html:
        return response
    html = html.replace("</body>", '<script src="/static/admin/admin_v5_ops.js"></script></body>')
    response.set_data(html)
    response.headers["Content-Length"] = str(len(response.get_data()))
    return response


@app.after_request
def _capture_admin_audit(response):
    if request.method != "POST" or request.endpoint not in _AUDIT_ACTIONS:
        return response
    if request.path.startswith("/api/kiosk"):
        return response
    action, category, detail = _AUDIT_ACTIONS[request.endpoint]
    status = "success" if response.status_code < 400 else "failed"
    _record_audit(action, category, detail, status=status, status_code=response.status_code)
    return response


def _actor():
    return {
        "id": legacy.safe_str(session.get("login_id")).strip() or "-",
        "name": legacy.safe_str(session.get("login_name")).strip() or "알 수 없음",
        "role": legacy.safe_str(session.get("role")).strip() or "-",
    }


def _record_audit(action, category, detail="", status="success", status_code=200):
    item = {
        "id": f"audit:{int(time.time() * 1000)}:{uuid.uuid4().hex[:6]}",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "category": category,
        "detail": detail,
        "status": status,
        "status_code": status_code,
        "path": request.path,
        "method": request.method,
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr or "-").split(",")[0].strip(),
        "actor": _actor(),
    }
    with _AUDIT_LOCK:
        _AUDIT_LOGS.insert(0, item)
        del _AUDIT_LOGS[120:]
    try:
        _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _AUDIT_PATH.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(item, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _audit_logs(limit=120):
    items = []
    if _AUDIT_PATH.exists():
        try:
            lines = _AUDIT_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
            for line in reversed(lines):
                try:
                    items.append(json.loads(line))
                except Exception:
                    pass
        except Exception:
            pass
    with _AUDIT_LOCK:
        items = [dict(item) for item in _AUDIT_LOGS] + items
    seen = set()
    result = []
    for item in items:
        item_id = item.get("id")
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        result.append(item)
    return result[:limit]


def _status_item(name, value, state="safe", detail="", icon="OK"):
    return {"name": name, "value": value, "state": state, "detail": detail, "icon": icon}


def _sheet_status_items():
    items = []
    all_ok = True
    sheet_map = [
        ("급식 시트", getattr(legacy, "menu_ws", None)),
        ("학생 시트", getattr(legacy, "student_ws", None)),
        ("계정 시트", getattr(legacy, "id_ws", None)),
        ("로그 시트", getattr(legacy, "logs_ws", None)),
    ]
    for label, ws in sheet_map:
        try:
            header = ws.row_values(1) if ws else []
            ok = bool(header)
            items.append(_status_item(label, "정상" if ok else "확인 필요", "safe" if ok else "warn", f"헤더 {len(header)}개 확인", "GS"))
            all_ok = all_ok and ok
        except Exception as exc:
            all_ok = False
            items.append(_status_item(label, "오류", "danger", legacy.safe_str(exc)[:120], "GS"))
    return all_ok, items


def _system_status_payload():
    uptime_seconds = max(0, int(time.time() - _STARTED_AT))
    uptime_label = f"{uptime_seconds // 3600}시간 {(uptime_seconds % 3600) // 60}분"
    sheet_ok, sheet_items = _sheet_status_items()
    openai_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
    ai_dict_size = len(getattr(legacy, "AI_ALLERGY_DICT", {}) or {})

    ai_jobs = []
    with realtime._AI_MEAL_LOCK:
        for job in sorted(realtime._AI_MEAL_JOBS.values(), key=lambda item: item.get("created_ts", 0), reverse=True)[:8]:
            ai_jobs.append({
                "id": job.get("id"),
                "filename": job.get("filename") or "-",
                "status": job.get("status") or "-",
                "message": job.get("message") or "",
                "created_at": datetime.fromtimestamp(job.get("created_ts") or time.time()).strftime("%m/%d %H:%M"),
            })

    last_scan = legacy.safe_str(getattr(legacy, "LATEST_SCANNED_RFID_AT", "")).strip()
    rfid_url = legacy.safe_str(getattr(legacy, "RFID_DASHBOARD_URL", "")).strip()
    audit_items = _audit_logs(30)
    recent_errors = [item for item in audit_items if item.get("status") == "failed"][:6]
    danger_events = [item for item in realtime._admin_events() if item.get("kind") == "danger"][:6]

    cards = [
        _status_item("서버 상태", "정상", "safe", f"업타임 {uptime_label}", "SV"),
        _status_item("Google Sheets", "정상" if sheet_ok else "확인 필요", "safe" if sheet_ok else "warn", "급식/학생/계정/로그 시트 연결 점검", "GS"),
        _status_item("AI 상태", "사용 가능" if openai_key else "Fallback", "safe" if openai_key else "warn", f"사전 항목 {ai_dict_size}개 · API Key {'설정됨' if openai_key else '미설정'}", "AI"),
        _status_item("RFID 연결", "최근 인식 있음" if last_scan else "대기", "safe" if last_scan else "warn", last_scan or rfid_url or "최근 RFID 인식 기록 없음", "RF"),
    ]
    return {
        "cards": cards,
        "sheet_items": sheet_items,
        "ai_jobs": ai_jobs,
        "recent_errors": recent_errors,
        "danger_events": danger_events,
        "audit_items": audit_items[:8],
        "server": {
            "started_at": datetime.fromtimestamp(_STARTED_AT).strftime("%Y-%m-%d %H:%M:%S"),
            "uptime": uptime_label,
            "python": os.sys.version.split()[0],
            "render": "Render" if os.getenv("RENDER") else "Local/Unknown",
        },
    }


def _audit_summary(items):
    total = len(items)
    failed = sum(1 for item in items if item.get("status") == "failed")
    ai = sum(1 for item in items if item.get("category") == "AI")
    data = sum(1 for item in items if item.get("category") in {"학생관리", "급식관리"})
    return {"total": total, "failed": failed, "ai": ai, "data": data}


@app.get("/system-status")
def system_status_page():
    ok, response = legacy.require_admin()
    if not ok:
        return response
    context = v5_admin_renderer._build_context("시스템 상태", "서버, Google Sheets, AI, RFID 연결 상태를 한눈에 확인하는 운영센터입니다.", "admin_home")
    context["active_tab"] = "system_status"
    context["system_status"] = _system_status_payload()
    return render_template("admin/system_status.html", **context)


@app.get("/audit-log")
def audit_log_page():
    ok, response = legacy.require_admin()
    if not ok:
        return response
    logs = _audit_logs(160)
    category = legacy.safe_str(request.args.get("category")).strip()
    status = legacy.safe_str(request.args.get("status")).strip()
    if category:
        logs = [item for item in logs if item.get("category") == category]
    if status:
        logs = [item for item in logs if item.get("status") == status]
    context = v5_admin_renderer._build_context("감사 로그", "학생, 급식, AI, 설정 변경 이력을 관리자 기준으로 추적합니다.", "admin_home")
    context["active_tab"] = "audit_log"
    context["audit_logs"] = logs
    context["audit_summary"] = _audit_summary(logs)
    context["audit_category"] = category
    context["audit_status"] = status
    context["audit_categories"] = sorted({item.get("category") for item in _audit_logs(160) if item.get("category")})
    return render_template("admin/audit_log.html", **context)


@app.get("/api/admin/system-status")
def api_admin_system_status():
    ok, response = legacy.require_admin_api()
    if not ok:
        return response
    return jsonify({"ok": True, "status": _system_status_payload()})


@app.get("/api/admin/audit-log")
def api_admin_audit_log():
    ok, response = legacy.require_admin_api()
    if not ok:
        return response
    logs = _audit_logs(160)
    return jsonify({"ok": True, "logs": logs, "summary": _audit_summary(logs)})
