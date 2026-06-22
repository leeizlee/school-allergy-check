import json
import os
import re
import threading
import time
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import jsonify, render_template, request, session, url_for

from admin import app_admin as legacy
from admin import v5_admin_renderer
from admin import v5_enterprise_patch as enterprise
from admin import v5_ops_patch as ops
from admin import v5_runtime_patch as realtime
from admin.app_admin import app
from core.admin_sheet_utils import _invalidate_sheet_cache, append_row_by_headers
from services.ai_service import infer_allergies_from_menu_name


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_AI_HISTORY_PATH = Path(os.getenv("AI_JOB_HISTORY_PATH", str(_PROJECT_ROOT / "data" / "ai_job_history.json")))
_AI_HISTORY_LOCK = threading.RLock()
_AI_HISTORY_LIMIT = max(50, min(int(os.getenv("AI_JOB_HISTORY_MAX_ITEMS", "500")), 2000))
_REVIEW_HEADERS = [
    "id", "kind", "status", "title", "target", "date", "info", "result",
    "created_by", "created_at", "reviewed_by", "reviewed_at", "etc",
]
_REVIEW_LOCK = threading.RLock()
_RUNTIME_HISTORY_IDS = {}
_MENU_TARGET_CACHE = {"ts": 0.0, "items": {}}
_MENU_TARGET_LOCK = threading.Lock()

_KIND_LABELS = {
    "meal_analysis": "급식 분석",
    "daily_brief": "위험 브리핑",
    "student_plan": "학생별 안전계획",
    "menu_review": "메뉴 점검",
    "alternative_meal": "대체급식 추천",
}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_text(value, limit=2000):
    text = legacy.safe_str(value).strip()
    return text[:limit]


def _mask_student_number(value):
    digits = "".join(ch for ch in _safe_text(value, 32) if ch.isdigit())
    if not digits:
        return ""
    return "*" * max(0, len(digits) - 2) + digits[-2:]


def _privacy_safe(value, key=""):
    key = _safe_text(key, 80).lower()
    if key in {"name", "student_name", "rfid_id", "uid"}:
        return "[보호됨]" if value else ""
    if key in {"student_number", "student_no"}:
        return _mask_student_number(value)
    if isinstance(value, dict):
        return {str(k)[:80]: _privacy_safe(v, str(k)) for k, v in list(value.items())[:80]}
    if isinstance(value, (list, tuple)):
        return [_privacy_safe(item) for item in list(value)[:80]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return _safe_text(value, 4000) if isinstance(value, str) else value
    return _safe_text(value, 4000)


def _history_document():
    with _AI_HISTORY_LOCK:
        try:
            data = json.loads(_AI_HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {"version": 1, "items": []}
        if not isinstance(data, dict):
            data = {"version": 1, "items": []}
        items = data.get("items")
        if not isinstance(items, list):
            items = []
        return {"version": 1, "items": items[:_AI_HISTORY_LIMIT]}


def _write_history(data):
    with _AI_HISTORY_LOCK:
        _AI_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "items": list(data.get("items") or [])[:_AI_HISTORY_LIMIT]}
        temp_path = _AI_HISTORY_PATH.with_suffix(_AI_HISTORY_PATH.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, _AI_HISTORY_PATH)


def _create_history(kind, status, title, summary="", input_data=None, output_data=None, linked_review_id="", created_by=""):
    item = {
        "id": f"ai:{uuid.uuid4().hex}",
        "kind": kind,
        "status": status,
        "title": _safe_text(title, 180) or _KIND_LABELS.get(kind, "AI 작업"),
        "created_at": _now(),
        "created_by": _safe_text(created_by or session.get("login_name") or session.get("login_id") or "관리자", 80),
        "summary": _safe_text(summary, 600),
        "input": _privacy_safe(input_data or {}),
        "output": _privacy_safe(output_data or {}),
        "linked_review_id": _safe_text(linked_review_id, 120),
    }
    with _AI_HISTORY_LOCK:
        data = _history_document()
        data["items"].insert(0, item)
        _write_history(data)
    return dict(item)


def _update_history(item_id, **updates):
    if not item_id:
        return None
    with _AI_HISTORY_LOCK:
        data = _history_document()
        found = None
        for item in data["items"]:
            if item.get("id") != item_id:
                continue
            for key, value in updates.items():
                item[key] = _privacy_safe(value, key) if key in {"input", "output"} else _safe_text(value, 2000)
            found = dict(item)
            break
        if found:
            _write_history(data)
        return found


def _history_items(kind="", status=""):
    items = _history_document()["items"]
    if kind:
        items = [item for item in items if item.get("kind") == kind]
    if status:
        items = [item for item in items if item.get("status") == status]
    return [dict(item) for item in items]


def _review_worksheet():
    sheet_id = os.getenv("REVIEW_QUEUE_SHEET_ID", "").strip()
    if sheet_id:
        base_ws = getattr(legacy, "menu_ws", None)
        book = getattr(base_ws, "spreadsheet", None)
        client = getattr(book, "client", None)
        if not client:
            raise RuntimeError("review_queue 문서에 연결할 Google Sheets 클라이언트를 찾지 못했어.")
        target_book = client.open_by_key(sheet_id)
        try:
            ws = target_book.worksheet("review_queue")
        except Exception:
            ws = target_book.sheet1
    else:
        ws = enterprise._ensure_ops_sheet("review_queue", _REVIEW_HEADERS)
    if not ws:
        raise RuntimeError("review_queue 시트를 찾지 못했어.")
    headers = [_safe_text(value, 80) for value in ws.row_values(1)]
    for index, header in enumerate(_REVIEW_HEADERS, start=1):
        if len(headers) < index or headers[index - 1] != header:
            ws.update_cell(1, index, header)
    return ws


def _json_field(value):
    if isinstance(value, (dict, list)):
        return value
    text = _safe_text(value, 12000)
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {"text": text}


def _review_items(status="", kind=""):
    with _REVIEW_LOCK:
        ws = _review_worksheet()
        records = ws.get_all_records()
    items = []
    for row_index, raw in enumerate(records, start=2):
        row = legacy.clean_record_keys(raw)
        item = {header: _safe_text(row.get(header), 12000) for header in _REVIEW_HEADERS}
        if not item["id"]:
            continue
        item["row_index"] = row_index
        item["info_data"] = _json_field(item["info"])
        item["result_data"] = _json_field(item["result"])
        item["etc_data"] = _json_field(item["etc"])
        if status and item["status"] != status:
            continue
        if kind and item["kind"] != kind:
            continue
        items.append(item)
    items.sort(key=lambda item: (item.get("created_at", ""), item.get("id", "")), reverse=True)
    return items


def _review_item(item_id):
    for item in _review_items():
        if item.get("id") == item_id:
            return item
    return None


def _append_review(item):
    row = {header: _safe_text(item.get(header), 12000) for header in _REVIEW_HEADERS}
    with _REVIEW_LOCK:
        ws = _review_worksheet()
        ws.append_row([row.get(header, "") for header in _REVIEW_HEADERS], value_input_option="USER_ENTERED")
        _invalidate_sheet_cache(ws)
    return row


def _update_review(item, **updates):
    with _REVIEW_LOCK:
        ws = _review_worksheet()
        headers = [_safe_text(value, 80) for value in ws.row_values(1)]
        header_map = {header: index for index, header in enumerate(headers, start=1)}
        for key, value in updates.items():
            if key not in header_map:
                continue
            ws.update_cell(item["row_index"], header_map[key], _safe_text(value, 12000))
        _invalidate_sheet_cache(ws)


def _normalize_date(value):
    digits = "".join(ch for ch in _safe_text(value, 32) if ch.isdigit())
    if len(digits) != 8:
        raise ValueError("날짜는 YYYYMMDD 형식이어야 해.")
    return digits


def _normalize_target(value):
    target = re.sub(r"\s+", "", _safe_text(value, 32)).upper()
    if target in {"A", "ALL"}:
        return "A"
    if re.fullmatch(r"\d{5}", target):
        return target
    raise ValueError("적용 대상은 A/ALL 또는 5자리 학년·반·학생 코드여야 해.")


def _target_matches(target, student_number):
    target = _safe_text(target, 32).upper()
    student_number = "".join(ch for ch in _safe_text(student_number, 32) if ch.isdigit())
    if not target or target in {"A", "ALL"}:
        return True
    if not re.fullmatch(r"\d{5}", target) or len(student_number) != 5:
        return False
    if target[1:] == "0000":
        return student_number[0] == target[0]
    if target[-2:] == "00":
        return student_number[:3] == target[:3]
    return student_number == target


def _menu_targets():
    now = time.monotonic()
    with _MENU_TARGET_LOCK:
        if now - _MENU_TARGET_CACHE["ts"] < 6:
            return dict(_MENU_TARGET_CACHE["items"])
    try:
        records = legacy.get_sheet_records_raw(legacy.menu_ws)
        items = {}
        for row_index, raw in enumerate(records, start=2):
            row = legacy.clean_record_keys(raw)
            items[row_index] = _safe_text(row.get("for") or row.get("target") or row.get("g"), 32).upper()
    except Exception:
        items = {}
    with _MENU_TARGET_LOCK:
        _MENU_TARGET_CACHE["ts"] = now
        _MENU_TARGET_CACHE["items"] = dict(items)
    return items


_original_get_all_menu_rows = legacy.get_all_menu_rows


def _get_all_menu_rows_with_targets(include_trash=False):
    rows = _original_get_all_menu_rows(include_trash=include_trash)
    targets = _menu_targets()
    for row in rows:
        target = targets.get(row.get("row_index"), "")
        row["for"] = target
        row["target"] = target
        row["is_alternative"] = bool(target and target not in {"A", "ALL"})
    return rows


legacy.get_all_menu_rows = _get_all_menu_rows_with_targets


def _menus_for_student(date_value, student_number):
    rows = [row for row in legacy.get_all_menu_rows(include_trash=False) if row.get("date") == date_value]
    return [row for row in rows if _target_matches(row.get("for"), student_number)]


def _alternative_rows(rows):
    return [
        {
            "menu_name": row.get("menu_name") or "-",
            "target": row.get("for") or "",
            "allergy_names": row.get("allergy_names") or "알레르기 코드 없음",
        }
        for row in rows
        if row.get("for") and row.get("for") not in {"A", "ALL"}
    ]


def _process_scan_with_alternatives(uid):
    uid = legacy.safe_str(uid).strip()
    today = legacy.today_sheet_str()
    if not uid:
        return {"ok": False, "error": "uid missing", "scan": {"uid": None, "name": None, "status": "오류", "reason": "uid가 비어있음", "menu_date": today, "menu_name": None, "student_allergy_names": "", "hit_codes": "", "hit_names": "", "unsafe_menus": [], "matched_allergies": [], "risk_explanation": "", "alternative_recommendation": "", "alternative_meals": [], "needs_staff_review": False}}

    student = legacy.get_student_by_rfid_id(uid, include_trash=False)
    if not student:
        legacy.write_scan_log(uid, None, "미등록", [], today)
        return {"ok": True, "scan": {"uid": uid, "name": None, "student_number": "", "status": "미등록", "reason": "학생DB(rfid)에 UID가 없음", "menu_date": today, "menu_name": None, "student_allergy_names": "", "hit_codes": "", "hit_names": "", "unsafe_menus": [], "matched_allergies": [], "risk_explanation": "", "alternative_recommendation": "", "alternative_meals": [], "needs_staff_review": False}}

    student_number = legacy.safe_str(student.get("student_number")).strip()
    menus = _menus_for_student(today, student_number)
    alternatives = _alternative_rows(menus)
    if not menus:
        legacy.write_scan_log(uid, student.get("name"), "메뉴없음", [], today)
        return {"ok": True, "scan": {"uid": uid, "name": student.get("name"), "student_number": student_number, "status": "메뉴없음", "reason": f"점심DB(food_menu)에 {today} 날짜 적용 메뉴가 없음", "menu_date": today, "menu_name": None, "student_allergy_names": legacy.code_string_to_names(student.get("allergy_codes"), empty_text="없음"), "hit_codes": "", "hit_names": "", "unsafe_menus": [], "matched_allergies": [], "risk_explanation": "", "alternative_recommendation": "", "alternative_meals": alternatives, "needs_staff_review": False}}

    student_name = legacy.safe_str(student.get("name"))
    student_codes = legacy.parse_codes(student.get("allergy_codes"))
    student_allergy_text = legacy.code_string_to_names(student.get("allergy_codes"), empty_text="없음")
    student_allergy_names = legacy.codes_to_names(sorted(student_codes))
    merged_menu_codes, menu_names = legacy.merge_menu_allergies(menus)
    merged_menu_names = ", ".join(menu_names)
    hit = sorted(list(student_codes & set(merged_menu_codes)))
    hit_names = legacy.codes_to_names(hit)
    alternative_message = ""
    if alternatives:
        alternative_message = "승인된 대체급식 있음: " + ", ".join(item["menu_name"] for item in alternatives) + ". 담당자가 최종 확인해줘."

    if hit:
        details = legacy.get_menu_hit_details(student_codes, menus)
        unsafe_menus = [item["menu_name"] for item in details if legacy.safe_str(item.get("menu_name")).strip()]
        detail_text = "\n".join(f"{item['menu_name']} → {', '.join(item['hit_names'])}" for item in details)
        ai_assist = legacy.generate_risk_assistance(student_name=student_name, student_allergies=student_allergy_names, unsafe_menus=unsafe_menus, matched_allergies=hit_names, all_menus=menu_names)
        legacy.write_scan_log(uid, student_name, "경고", hit, today)
        reason = f"겹치는 알러지: {', '.join(hit_names)}\n\n메뉴별 주의 항목:\n{detail_text}"
        if alternative_message:
            reason += "\n\n" + alternative_message
        return {"ok": True, "scan": {"uid": uid, "name": student_name, "student_number": student_number, "status": "경고", "reason": reason, "menu_date": today, "menu_name": merged_menu_names, "student_allergy_names": student_allergy_text, "hit_codes": ",".join(str(value) for value in hit), "hit_names": ", ".join(hit_names), "unsafe_menus": unsafe_menus, "matched_allergies": ai_assist.get("matched_allergies", hit_names), "risk_explanation": ai_assist.get("risk_explanation", ""), "alternative_recommendation": alternative_message or ai_assist.get("alternative_recommendation", ""), "alternative_meals": alternatives, "needs_staff_review": bool(ai_assist.get("needs_staff_review", True) or alternatives)}}

    legacy.write_scan_log(uid, student_name, "OK", [], today)
    reason = f"문제 없음\n오늘 메뉴: {merged_menu_names}"
    if alternative_message:
        reason += "\n" + alternative_message
    return {"ok": True, "scan": {"uid": uid, "name": student_name, "student_number": student_number, "status": "OK", "reason": reason, "menu_date": today, "menu_name": merged_menu_names, "student_allergy_names": student_allergy_text, "hit_codes": "", "hit_names": "", "unsafe_menus": [], "matched_allergies": [], "risk_explanation": "", "alternative_recommendation": alternative_message, "alternative_meals": alternatives, "needs_staff_review": bool(alternatives)}}


legacy.process_scan = _process_scan_with_alternatives

_original_update_scan_state = legacy.update_last_scan_state_from_result


def _update_scan_state_with_alternatives(result):
    _original_update_scan_state(result)
    scan = (result or {}).get("scan") or {}
    if isinstance(legacy.LAST_SCAN_STATE, dict):
        legacy.LAST_SCAN_STATE["alternative_meals"] = scan.get("alternative_meals") or []
        if scan.get("alternative_recommendation"):
            legacy.LAST_SCAN_STATE["alternative_recommendation"] = scan.get("alternative_recommendation")


legacy.update_last_scan_state_from_result = _update_scan_state_with_alternatives


@app.get("/admin/ai-tools/history")
def ai_job_history_page():
    ok, response = legacy.require_admin()
    if not ok:
        return response
    kind = _safe_text(request.args.get("kind"), 40)
    status = _safe_text(request.args.get("status"), 40)
    items = _history_items(kind, status)
    context = v5_admin_renderer._build_context("AI 작업 기록", "AI 분석의 실행 시각, 상태, 요약과 검토 작업 연결을 확인합니다.", "ai_tools")
    context.update({"active_tab": "ai_history", "ai_history": items, "ai_history_kind": kind, "ai_history_status": status, "ai_kind_labels": _KIND_LABELS})
    return render_template("admin/ai_history.html", **context)


@app.get("/api/admin/ai-history")
def api_ai_job_history():
    ok, response = legacy.require_admin_api()
    if not ok:
        return response
    return jsonify({"ok": True, "items": _history_items(_safe_text(request.args.get("kind"), 40), _safe_text(request.args.get("status"), 40))})


@app.get("/admin/review-queue")
def review_queue_page():
    ok, response = legacy.require_admin()
    if not ok:
        return response
    raw_status = _safe_text(request.args.get("status"), 40)
    status = "" if raw_status == "all" else (raw_status or "pending")
    kind = _safe_text(request.args.get("kind"), 40)
    try:
        items = _review_items(status, kind)
        error = ""
    except Exception as exc:
        items = []
        error = _safe_text(exc, 300)
    context = v5_admin_renderer._build_context("검토 대기함", "AI 대체급식 추천을 승인, 수정 후 승인, 반려하는 작업 공간입니다.", "ai_tools")
    context.update({"active_tab": "review_queue", "review_items": items, "review_status": status, "review_kind": kind, "review_error": error})
    return render_template("admin/review_queue.html", **context)


@app.get("/api/admin/review-queue")
def api_review_queue():
    ok, response = legacy.require_admin_api()
    if not ok:
        return response
    try:
        return jsonify({"ok": True, "items": _review_items(_safe_text(request.args.get("status"), 40), _safe_text(request.args.get("kind"), 40))})
    except Exception as exc:
        return jsonify({"ok": False, "error": _safe_text(exc, 300)}), 503


@app.post("/api/ai/alternative-meal")
def api_ai_alternative_meal():
    ok, response = legacy.require_admin_api()
    if not ok:
        return response
    data = request.get_json(silent=True) or {}
    student_number = _safe_text(data.get("student_number"), 32)
    date_value = _normalize_date(data.get("date") or legacy.today_sheet_str())
    target = _normalize_target(data.get("target") or student_number)
    note = _safe_text(data.get("context"), 800)
    student = legacy.get_student_by_student_number(student_number, include_trash=False)
    if not student:
        return jsonify({"ok": False, "error": "학생 정보를 찾지 못했어."}), 404
    student_context = legacy.build_student_ai_context(student, date_value)
    if not student_context.get("menus"):
        return jsonify({"ok": False, "error": f"{date_value} 날짜 급식 메뉴가 없어."}), 400
    plan = legacy.generate_allergy_safety_plan(
        student_name=_safe_text(student.get("name"), 80),
        student_number=student_number,
        student_allergies=student_context["student_allergy_names"],
        unsafe_menus=student_context["unsafe_menus"],
        matched_allergies=student_context["matched_allergies"],
        all_menus=student_context["menu_names"],
        context=note,
    )
    alternatives = plan.get("alternative_meals") or []
    if not alternatives:
        return jsonify({"ok": False, "error": "AI 결과에서 대체급식 후보를 찾지 못했어."}), 422
    alternative = alternatives[0]
    source_text = f"{alternative.get('name', '')} {alternative.get('components', '')}"
    allergy_codes = infer_allergies_from_menu_name(source_text, legacy.AI_ALLERGY_DICT)
    review_id = f"review:{uuid.uuid4().hex}"
    history = _create_history(
        "alternative_meal", "pending", f"{date_value} 대체급식 추천", "관리자 검토 대기함에 추천안을 등록했습니다.",
        {"date": date_value, "student_number": student_number, "target": target, "context": note},
        {"risk_level": plan.get("risk_level"), "risk_summary": plan.get("risk_summary"), "alternative": alternative},
        linked_review_id=review_id,
    )
    result = {"menu_name": _safe_text(alternative.get("name"), 180), "allergy_codes": allergy_codes, "components": _safe_text(alternative.get("components"), 800), "preparation_notes": _safe_text(alternative.get("preparation_notes"), 1200), "avoids": alternative.get("avoids") or [], "reason": _safe_text(alternative.get("reason"), 1200), "staff_check": _safe_text(alternative.get("staff_check"), 1200)}
    review = {
        "id": review_id, "kind": "alternative_meal", "status": "pending", "title": f"{date_value} 대체급식 추천",
        "target": target, "date": date_value,
        "info": json.dumps({"unsafe_menus": student_context.get("unsafe_menus") or [], "matched_allergies": student_context.get("matched_allergies") or [], "note": note}, ensure_ascii=False),
        "result": json.dumps(result, ensure_ascii=False), "created_by": history["created_by"], "created_at": _now(),
        "reviewed_by": "", "reviewed_at": "", "etc": json.dumps({"ai_history_id": history["id"]}, ensure_ascii=False),
    }
    try:
        _append_review(review)
    except Exception as exc:
        _update_history(history["id"], status="error", summary=f"review_queue 저장 실패: {_safe_text(exc, 240)}")
        return jsonify({"ok": False, "error": f"검토 대기함 저장에 실패했어: {_safe_text(exc, 240)}"}), 503
    realtime._add_admin_event({"id": f"review:{review_id}", "target": "review_queue", "path": url_for("review_queue_page"), "icon": "RV", "title": "대체급식 추천 - 검토 필요", "detail": result["menu_name"] or "대체급식 추천안", "time": datetime.now().strftime("%m/%d %H:%M"), "kind": "ai"})
    return jsonify({"ok": True, "review_id": review_id, "history_id": history["id"], "status": "pending", "result": result, "review_url": url_for("review_queue_page")})


@app.post("/api/admin/review-queue/<path:item_id>/approve")
def api_review_queue_approve(item_id):
    ok, response = legacy.require_admin_api()
    if not ok:
        return response
    item = _review_item(item_id)
    if not item:
        return jsonify({"ok": False, "error": "검토 항목을 찾지 못했어."}), 404
    if item.get("status") != "pending":
        return jsonify({"ok": False, "error": "이미 처리된 검토 항목이야."}), 409
    data = request.get_json(silent=True) or {}
    result = item.get("result_data") or {}
    try:
        date_value = _normalize_date(data.get("date") or item.get("date"))
        target = _normalize_target(data.get("target") or item.get("target"))
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    menu_name = _safe_text(data.get("menu_name") or result.get("menu_name") or item.get("title"), 180)
    if not menu_name:
        return jsonify({"ok": False, "error": "승인할 대체급식 메뉴명을 입력해줘."}), 400
    allergy_codes = sorted(legacy.parse_codes(data.get("allergy_codes", result.get("allergy_codes", []))))
    created_by = _safe_text(session.get("login_name") or session.get("login_id") or "관리자", 80)
    try:
        append_row_by_headers(legacy.menu_ws, {"date": date_value, "menu_name": menu_name, "allergy_codes": ",".join(str(code) for code in allergy_codes), "created_by": created_by, "created_at": legacy.now_time_str(), "trash": "0", "for": target})
        approved_result = dict(result)
        approved_result.update({"menu_name": menu_name, "allergy_codes": allergy_codes, "target": target, "date": date_value})
        _update_review(item, status="approved", date=date_value, target=target, result=json.dumps(approved_result, ensure_ascii=False), reviewed_by=created_by, reviewed_at=_now())
    except Exception as exc:
        return jsonify({"ok": False, "error": f"food_menu 반영에 실패했어: {_safe_text(exc, 240)}"}), 503
    history_id = _safe_text((item.get("etc_data") or {}).get("ai_history_id"), 120)
    _update_history(history_id, status="approved", summary=f"{menu_name} 대체급식이 승인되어 food_menu에 반영됐습니다.")
    realtime._add_admin_event({"id": f"review-approved:{item_id}", "target": "menu_manage", "path": "/menu-manage", "icon": "OK", "title": "대체급식 - 승인 완료", "detail": menu_name, "time": datetime.now().strftime("%m/%d %H:%M"), "kind": "safe"})
    return jsonify({"ok": True, "status": "approved", "menu_name": menu_name, "target": target})


@app.post("/api/admin/review-queue/<path:item_id>/reject")
def api_review_queue_reject(item_id):
    ok, response = legacy.require_admin_api()
    if not ok:
        return response
    item = _review_item(item_id)
    if not item:
        return jsonify({"ok": False, "error": "검토 항목을 찾지 못했어."}), 404
    if item.get("status") != "pending":
        return jsonify({"ok": False, "error": "이미 처리된 검토 항목이야."}), 409
    data = request.get_json(silent=True) or {}
    reviewer = _safe_text(session.get("login_name") or session.get("login_id") or "관리자", 80)
    reason = _safe_text(data.get("reason") or "관리자 반려", 500)
    etc_data = item.get("etc_data") or {}
    etc_data["reject_reason"] = reason
    _update_review(item, status="rejected", reviewed_by=reviewer, reviewed_at=_now(), etc=json.dumps(etc_data, ensure_ascii=False))
    _update_history(_safe_text(etc_data.get("ai_history_id"), 120), status="rejected", summary=f"대체급식 추천이 반려됐습니다: {reason}")
    return jsonify({"ok": True, "status": "rejected"})


def _wrap_json_ai_endpoint(endpoint, kind, title):
    original = app.view_functions.get(endpoint)
    if not original or getattr(original, "_issue3_history_wrapped", False):
        return

    @wraps(original)
    def wrapped(*args, **kwargs):
        input_data = request.get_json(silent=True) or {}
        response = app.make_response(original(*args, **kwargs))
        payload = response.get_json(silent=True) if response.is_json else {}
        ok = response.status_code < 400 and (not isinstance(payload, dict) or payload.get("ok", True))
        summary = _safe_text((payload or {}).get("error") if isinstance(payload, dict) and not ok else (payload or {}).get("brief") if isinstance((payload or {}).get("brief"), str) else "작업이 완료됐습니다." if ok else "작업에 실패했습니다.", 600)
        _create_history(kind, "done" if ok else "error", title, summary, input_data, payload or {})
        return response

    wrapped._issue3_history_wrapped = True
    app.view_functions[endpoint] = wrapped


def _wrap_async_meal_endpoint():
    endpoint = "api_meal_analyze_async"
    original = app.view_functions.get(endpoint)
    if not original or getattr(original, "_issue3_history_wrapped", False):
        return

    @wraps(original)
    def wrapped(*args, **kwargs):
        filename = ""
        upload = request.files.get("meal_file") or request.files.get("meal_image")
        if upload:
            filename = _safe_text(upload.filename, 180)
        response = app.make_response(original(*args, **kwargs))
        payload = response.get_json(silent=True) or {}
        if response.status_code < 400 and payload.get("job_id"):
            history = _create_history("meal_analysis", "queued", f"급식표 분석: {filename or '업로드 파일'}", "백그라운드 분석을 시작했습니다.", {"filename": filename}, {})
            job_id = payload["job_id"]
            _RUNTIME_HISTORY_IDS[job_id] = history["id"]
            current = realtime._get_ai_job(job_id)
            if current:
                _update_history(history["id"], status=current.get("status") or "queued", summary=current.get("message") or "분석 대기 중")
        return response

    wrapped._issue3_history_wrapped = True
    app.view_functions[endpoint] = wrapped


def _wrap_html_meal_endpoint():
    endpoint = "meal_analyze_page"
    original = app.view_functions.get(endpoint)
    if not original or getattr(original, "_issue3_history_wrapped", False):
        return

    @wraps(original)
    def wrapped(*args, **kwargs):
        upload = request.files.get("meal_file") or request.files.get("meal_image")
        filename = _safe_text(upload.filename if upload else "", 180)
        response = app.make_response(original(*args, **kwargs))
        ok = response.status_code < 400
        _create_history(
            "meal_analysis",
            "done" if ok else "error",
            f"급식표 분석: {filename or '업로드 파일'}",
            "분석 결과 미리보기를 생성했습니다." if ok else "급식표 분석에 실패했습니다.",
            {"filename": filename},
            {},
        )
        return response

    wrapped._issue3_history_wrapped = True
    app.view_functions[endpoint] = wrapped


_original_runtime_set_job = realtime._set_ai_job


def _runtime_set_job_with_history(job_id, **updates):
    job = _original_runtime_set_job(job_id, **updates)
    history_id = _RUNTIME_HISTORY_IDS.get(job_id)
    if history_id and job:
        status = job.get("status") or "running"
        mapped = "done" if status == "done" else ("error" if status == "error" else status)
        _update_history(history_id, status=mapped, summary=job.get("message") or "", output=job.get("preview") or {})
    return job


realtime._set_ai_job = _runtime_set_job_with_history

_wrap_json_ai_endpoint("api_ai_safety_plan", "student_plan", "학생별 안전계획")
_wrap_json_ai_endpoint("api_ai_daily_brief", "daily_brief", "오늘 위험 브리핑")
_wrap_json_ai_endpoint("api_ai_menu_review", "menu_review", "메뉴 정보 점검")
_wrap_async_meal_endpoint()
_wrap_html_meal_endpoint()

ops._AUDIT_ACTIONS.update({
    "api_ai_alternative_meal": ("대체급식 추천", "AI", "대체급식 추천 및 검토 대기 등록"),
    "api_review_queue_approve": ("대체급식 승인", "급식관리", "검토 대기 대체급식 승인"),
    "api_review_queue_reject": ("대체급식 반려", "급식관리", "검토 대기 대체급식 반려"),
})


@app.after_request
def _inject_issue3_assets(response):
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type or request.path.startswith("/api"):
        return response
    try:
        html = response.get_data(as_text=True)
    except Exception:
        return response
    changed = False
    if "admin_v5_issue3.css" not in html and "</head>" in html:
        html = html.replace("</head>", '<link rel="stylesheet" href="/static/admin/admin_v5_issue3.css"></head>')
        changed = True
    if "admin_v5_issue3.js" not in html and "</body>" in html:
        html = html.replace("</body>", '<script src="/static/admin/admin_v5_issue3.js"></script></body>')
        changed = True
    if changed:
        response.set_data(html)
        response.headers["Content-Length"] = str(len(response.get_data()))
    return response
