from collections import Counter, defaultdict
from datetime import datetime, timedelta
from functools import lru_cache

from flask import render_template, render_template_string, request, session
from markupsafe import Markup

from admin import app_admin as legacy

_TEMPLATE_BY_TAB = {
    "admin_home": "admin/home.html",
    "student_manage": "admin/student_manage.html",
    "menu_manage": "admin/menu_manage.html",
    "lunch_log": "admin/lunch_log.html",
    "meal_ai": "admin/meal_ai.html",
    "ai_tools": "admin/ai_tools.html",
    "trash": "admin/trash.html",
}

@lru_cache(maxsize=1)
def _legacy_admin_tail():
    marker = "  <!-- \ub0b4 \uacc4\uc815\uad00\ub9ac -->"
    source = legacy.BASE_HTML
    start = source.find(marker)
    end = source.rfind("</body>")
    if start < 0 or end < 0 or end <= start:
        return ""
    return source[start:end].replace("let isDarkMode = true;", "let isDarkMode = false;", 1)

def _available_classes(keys):
    items = [{"key": "all", "label": "전체"}]
    for key in keys:
        if key == "unknown":
            continue
        parts = key.split("-")
        if len(parts) == 2:
            try:
                items.append({"key": key, "label": f"{parts[0]}학년 {int(parts[1])}반"})
            except ValueError:
                items.append({"key": key, "label": key})
    return items

def _compact_date(value):
    return legacy.compact_date_value(value)

def _date_label(value):
    text = _compact_date(value)
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}" if len(text) == 8 else (text or "-")

def _pct(part, total):
    return round((part / total) * 100, 1) if total else 0

def _codes(row):
    return sorted(legacy.parse_codes(row.get("allergy_codes")))

def _code_label(code):
    return f"{code}. {legacy.ALLERGY_MAP.get(code, f'알수없음({code})')}"

def _result_bucket(row):
    result = legacy.safe_str(row.get("result")).strip().lower()
    hit_names = legacy.safe_str(row.get("hit_names")).strip()
    hit_codes = legacy.safe_str(row.get("hit_codes")).strip()
    if "ok" in result or result in {"통과", "안전"}:
        return "safe"
    if "경고" in result or "위험" in result or hit_names or hit_codes:
        return "danger"
    if "미등록" in result:
        return "unknown"
    if "오류" in result:
        return "error"
    return "notice"

def _scan_hour(row):
    text = legacy.safe_str(row.get("scanned_at")).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).hour
        except ValueError:
            pass
    if len(text) >= 13 and text[11:13].isdigit():
        return int(text[11:13])
    if len(text) >= 10 and text[8:10].isdigit():
        return int(text[8:10])
    return None

def _week_keys(today):
    base = datetime.strptime(today, "%Y%m%d") if len(today) == 8 else datetime.now()
    return [(base - timedelta(days=i)).strftime("%Y%m%d") for i in range(6, -1, -1)]

def _student_insights(rows):
    total = len(rows)
    allergy = sum(1 for row in rows if _codes(row))
    rfid = sum(1 for row in rows if legacy.safe_str(row.get("rfid_id")).strip())
    class_counts = Counter()
    allergy_counts = Counter()
    for row in rows:
        class_counts[row.get("class_label") or f"{row.get('grade') or '-'}학년 {row.get('class_no') or '-'}반"] += 1
        for code in _codes(row):
            allergy_counts[_code_label(code)] += 1
    return {
        "rfid_rate": _pct(rfid, total),
        "allergy_rate": _pct(allergy, total),
        "class_counts": class_counts.most_common(12),
        "allergy_counts": allergy_counts.most_common(12),
    }

def _menu_insights(rows, today):
    date_counts = Counter()
    allergy_counts = Counter()
    week_risk = Counter()
    today_dt = datetime.strptime(today, "%Y%m%d") if len(today) == 8 else datetime.now()
    week_start = today_dt - timedelta(days=6)
    today_count = risk_count = missing_codes = week_count = 0
    for row in rows:
        date_key = _compact_date(row.get("date"))
        codes = _codes(row)
        if date_key:
            date_counts[_date_label(date_key)] += 1
        if date_key == today:
            today_count += 1
        if codes:
            risk_count += 1
            for code in codes:
                allergy_counts[_code_label(code)] += 1
        else:
            missing_codes += 1
        if len(date_key) == 8:
            try:
                dt = datetime.strptime(date_key, "%Y%m%d")
                if week_start <= dt <= today_dt:
                    week_count += 1
                    week_risk[dt.strftime("%m/%d")] += 1 if codes else 0
            except ValueError:
                pass
    labels = [(today_dt - timedelta(days=i)).strftime("%m/%d") for i in range(6, -1, -1)]
    return {
        "today_count": today_count,
        "week_count": week_count,
        "risk_count": risk_count,
        "missing_codes": missing_codes,
        "date_counts": date_counts.most_common(14),
        "allergy_counts": allergy_counts.most_common(12),
        "week_labels": labels,
        "week_risk_values": [week_risk.get(label, 0) for label in labels],
    }

def _lunch_insights(rows, today):
    today_rows = [row for row in rows if row.get("scan_date") == today]
    buckets = Counter(_result_bucket(row) for row in today_rows)
    allergy_hits = Counter()
    danger_rows = []
    unknown_rows = []
    risky_students = set()
    for row in today_rows:
        bucket = _result_bucket(row)
        if bucket == "danger":
            danger_rows.append(row)
            risky_students.add(row.get("student_number") or row.get("rfid_id") or row.get("name"))
        if bucket == "unknown":
            unknown_rows.append(row)
        for code in legacy.parse_codes(row.get("hit_codes")):
            allergy_hits[_code_label(code)] += 1
    scan_times = [legacy.safe_str(row.get("scanned_at")).strip() for row in today_rows if row.get("scanned_at")]
    return {
        "danger_count": buckets.get("danger", 0),
        "unknown_count": buckets.get("unknown", 0),
        "error_count": buckets.get("error", 0) + buckets.get("notice", 0),
        "first_scan_time": max(scan_times) if scan_times else "-",
        "recent_scan_time": max(scan_times) if scan_times else "-",
        "danger_rows": danger_rows[:6],
        "unknown_rows": unknown_rows[:6],
        "risky_student_count": len([x for x in risky_students if x]),
        "allergy_hits": allergy_hits.most_common(8),
    }

def _meal_preview_summary(preview):
    rows = (preview or {}).get("rows") or []
    dates = {legacy.safe_str(row.get("date")).strip() for row in rows if row.get("date")}
    review = sum(1 for row in rows if row.get("needs_review"))
    low_conf = sum(1 for row in rows if float(row.get("confidence") or 0) < 0.75)
    return {"date_count": len(dates), "menu_count": len(rows), "review_count": review, "low_confidence_count": low_conf}

def _dashboard_data(student_rows, menu_rows, lunch_rows, selected_class, today):
    total = len(student_rows)
    allergy = sum(1 for row in student_rows if _codes(row))
    rfid = sum(1 for row in student_rows if legacy.safe_str(row.get("rfid_id")).strip())
    today_menus = [row for row in menu_rows if _compact_date(row.get("date")) == today]
    risk_menus = [row for row in today_menus if _codes(row)]
    today_logs = [row for row in lunch_rows if row.get("scan_date") == today]
    if selected_class != "all":
        today_logs = [row for row in today_logs if row.get("class_key") == selected_class]
    buckets = Counter(_result_bucket(row) for row in today_logs)
    return {
        "stats": {"total_students": total, "allergy_students": allergy, "rfid_students": rfid, "no_rfid_students": total - rfid, "today_menu_count": len(today_menus), "today_risk_menu_count": len(risk_menus), "today_scan_count": len(today_logs), "today_safe_count": buckets.get("safe", 0), "today_danger_count": buckets.get("danger", 0), "today_unknown_count": buckets.get("unknown", 0), "today_error_count": buckets.get("error", 0) + buckets.get("notice", 0), "rfid_rate": _pct(rfid, total), "allergy_rate": _pct(allergy, total)},
        "today_menus": today_menus,
        "risk_menus": risk_menus,
        "recent_logs": today_logs[:8] if today_logs else lunch_rows[:8],
        "system_status": [{"label": "서버", "value": "정상", "kind": "safe"}, {"label": "데이터 연결", "value": "준비됨", "kind": "info"}, {"label": "AI 기능", "value": "대기", "kind": "ai"}, {"label": "최근 업데이트", "value": datetime.now().strftime("%m/%d %H:%M"), "kind": "muted"}],
    }

def _chart_data(student_rows, menu_rows, lunch_rows, today):
    today_rows = [row for row in lunch_rows if row.get("scan_date") == today]
    hour_counts = [0] * 24
    danger_hour_counts = [0] * 24
    for row in today_rows:
        hour = _scan_hour(row)
        if hour is not None and 0 <= hour <= 23:
            hour_counts[hour] += 1
            if _result_bucket(row) == "danger":
                danger_hour_counts[hour] += 1
    buckets = Counter(_result_bucket(row) for row in today_rows)
    week_keys = _week_keys(today)
    labels = [_date_label(key)[5:] for key in week_keys]
    danger_by_day = defaultdict(int)
    scan_by_day = defaultdict(int)
    for row in lunch_rows:
        if row.get("scan_date"):
            scan_by_day[row.get("scan_date")] += 1
        if row.get("scan_date") and _result_bucket(row) == "danger":
            danger_by_day[row.get("scan_date")] += 1
    allergy = sum(1 for row in student_rows if _codes(row))
    rfid = sum(1 for row in student_rows if legacy.safe_str(row.get("rfid_id")).strip())
    student = _student_insights(student_rows)
    menu = _menu_insights(menu_rows, today)
    lunch = _lunch_insights(lunch_rows, today)
    return {
        "hourly": {"labels": [f"{h:02d}" for h in range(24)], "values": hour_counts},
        "danger_hourly": {"labels": [f"{h:02d}" for h in range(24)], "values": danger_hour_counts},
        "weekly_scans": {"labels": labels, "values": [scan_by_day.get(key, 0) for key in week_keys]},
        "results": {"labels": ["안전", "위험", "미등록", "오류/주의"], "values": [buckets.get("safe", 0), buckets.get("danger", 0), buckets.get("unknown", 0), buckets.get("error", 0) + buckets.get("notice", 0)], "colors": ["#47b881", "#e55353", "#f0ad4e", "#6c7ae0"]},
        "danger_trend": {"labels": labels, "values": [danger_by_day.get(key, 0) for key in week_keys]},
        "student_mix": {"labels": ["알레르기", "일반"], "values": [allergy, max(len(student_rows) - allergy, 0)], "colors": ["#e55353", "#47b881"]},
        "rfid_mix": {"labels": ["RFID 등록", "RFID 미등록"], "values": [rfid, max(len(student_rows) - rfid, 0)], "colors": ["#5b8def", "#f0ad4e"]},
        "class_counts": {"labels": [label for label, _ in student["class_counts"]], "values": [value for _, value in student["class_counts"]]},
        "student_allergy_top": {"labels": [label for label, _ in student["allergy_counts"]], "values": [value for _, value in student["allergy_counts"]]},
        "menu_date_counts": {"labels": [label for label, _ in menu["date_counts"]], "values": [value for _, value in menu["date_counts"]]},
        "menu_allergy_top": {"labels": [label for label, _ in menu["allergy_counts"]], "values": [value for _, value in menu["allergy_counts"]]},
        "menu_week_risk": {"labels": menu["week_labels"], "values": menu["week_risk_values"]},
        "menu_risk_mix": {"labels": ["위험 가능", "코드 없음"], "values": [menu["risk_count"], menu["missing_codes"]], "colors": ["#e55353", "#47b881"]},
        "log_allergy_hits": {"labels": [label for label, _ in lunch["allergy_hits"]], "values": [value for _, value in lunch["allergy_hits"]]},
    }

def _menu_timeline(groups, today):
    current, upcoming, past = [], [], []
    for group in groups:
        date_key = _compact_date(group.get("date"))
        if date_key == today:
            current.append(group)
        elif date_key > today:
            upcoming.append(group)
        else:
            past.append(group)
    return {"today": current, "upcoming": sorted(upcoming, key=lambda item: _compact_date(item.get("date")))[:12], "past": past[:12]}

def _trash_summary(rows):
    students = sum(1 for row in rows if row.get("kind") == "학생")
    menus = sum(1 for row in rows if row.get("kind") == "급식")
    return {"total": len(rows), "students": students, "menus": menus}

def _empty_dashboard():
    return {
        "stats": {
            "total_students": 0,
            "allergy_students": 0,
            "rfid_students": 0,
            "no_rfid_students": 0,
            "today_menu_count": 0,
            "today_risk_menu_count": 0,
            "today_scan_count": 0,
            "today_safe_count": 0,
            "today_danger_count": 0,
            "today_unknown_count": 0,
            "today_error_count": 0,
            "rfid_rate": 0,
            "allergy_rate": 0,
        },
        "today_menus": [],
        "risk_menus": [],
        "recent_logs": [],
        "system_status": [],
    }

def _empty_chart_data():
    hours = [f"{h:02d}" for h in range(24)]
    return {
        "hourly": {"labels": hours, "values": [0] * 24},
        "danger_hourly": {"labels": hours, "values": [0] * 24},
        "weekly_scans": {"labels": [], "values": []},
        "results": {"labels": ["안전", "위험", "미등록", "오류/주의"], "values": [0, 0, 0, 0], "colors": ["#47b881", "#e55353", "#f0ad4e", "#6c7ae0"]},
        "danger_trend": {"labels": [], "values": []},
        "student_mix": {"labels": ["알레르기", "일반"], "values": [0, 0], "colors": ["#e55353", "#47b881"]},
        "rfid_mix": {"labels": ["RFID 등록", "RFID 미등록"], "values": [0, 0], "colors": ["#5b8def", "#f0ad4e"]},
        "class_counts": {"labels": [], "values": []},
        "student_allergy_top": {"labels": [], "values": []},
        "menu_date_counts": {"labels": [], "values": []},
        "menu_allergy_top": {"labels": [], "values": []},
        "menu_week_risk": {"labels": [], "values": []},
        "menu_risk_mix": {"labels": ["위험 가능", "코드 없음"], "values": [0, 0], "colors": ["#e55353", "#47b881"]},
        "log_allergy_hits": {"labels": [], "values": []},
    }

def _notifications(student_rows, menu_rows, lunch_rows):
    items = []
    for row in lunch_rows[:6]:
        name = row.get("name") or row.get("rfid_id") or "미등록 RFID"
        result = row.get("result") or "스캔"
        items.append({
            "icon": "RF",
            "title": f"{name} 학생증 인식",
            "detail": f"{result} 판정 · {row.get('hit_names') or '위험 없음'}",
            "time": row.get("scanned_at") or "-",
            "kind": "danger" if result == "경고" else ("warn" if result == "미등록" else "safe"),
        })
    for row in student_rows[:3]:
        if row.get("created_at"):
            items.append({
                "icon": "ST",
                "title": f"{row.get('name') or '학생'} 등록",
                "detail": row.get("student_number") or "학생 정보가 등록됐습니다.",
                "time": row.get("created_at"),
                "kind": "info",
            })
    for row in menu_rows[:3]:
        label = "메뉴 수정" if row.get("updated_at") else "메뉴 등록"
        items.append({
            "icon": "ME",
            "title": label,
            "detail": row.get("menu_name") or row.get("date") or "급식 메뉴",
            "time": row.get("updated_at") or row.get("created_at") or row.get("date") or "-",
            "kind": "ai",
        })
    if session.get("role") == "s":
        items.insert(0, {"icon": "IN", "title": "학생 로그인", "detail": session.get("login_name", "학생"), "time": "현재 세션", "kind": "info"})
    return items[:10]

def _profile_picture_for_login(login_id):
    login_id = legacy.safe_str(login_id).strip()
    if not login_id:
        return ""
    try:
        records = legacy._cached_get_all_records(legacy.id_ws)
    except Exception:
        records = legacy.id_ws.get_all_records()
    for record in records:
        row = legacy.clean_record_keys(record)
        if legacy.safe_str(row.get("id")).strip() == login_id:
            return legacy.safe_str(row.get("picture")).strip()
    return ""

def _build_context(title, subtitle, active_tab, meal_mode="upload", meal_preview=None, meal_ocr_text="", meal_error="", meal_created_by=None):
    selected_class = legacy.safe_str(request.args.get("class_key", "all")).strip() or "all"
    selected_date = legacy.safe_str(request.args.get("date", "")).replace("-", "").strip()

    needs_students = active_tab in {"admin_home", "student_manage", "lunch_log", "ai_tools"}
    needs_menu = active_tab in {"admin_home", "menu_manage", "meal_ai", "ai_tools"}
    needs_menu_groups = active_tab == "menu_manage"
    needs_lunch = active_tab in {"admin_home", "lunch_log"}

    student_rows = legacy.get_all_student_rows() if needs_students else []
    menu_rows = legacy.get_all_menu_rows() if needs_menu else []
    menu_groups = legacy.get_menu_groups() if needs_menu_groups else []
    lunch_rows = legacy.get_all_lunch_log_rows() if needs_lunch else []

    class_keys = legacy.get_available_class_keys(student_rows=student_rows, lunch_log_rows=lunch_rows)
    filtered_students = [row for row in student_rows if selected_class == "all" or row.get("class_key") == selected_class]
    student_summary = {"total": len(filtered_students), "allergy": sum(1 for row in filtered_students if _codes(row)), "rfid": sum(1 for row in filtered_students if legacy.safe_str(row.get("rfid_id")).strip()), "no_rfid": sum(1 for row in filtered_students if not legacy.safe_str(row.get("rfid_id")).strip())}
    filtered_lunch = [row for row in lunch_rows if (not selected_date or row.get("scan_date") == selected_date)]
    if selected_class != "all":
        filtered_lunch = [row for row in filtered_lunch if row.get("class_key") == selected_class]
    today = legacy.today_sheet_str()
    active_lunch_date = selected_date or today
    today_rows = [row for row in lunch_rows if row.get("scan_date") == today]
    attendance_rows = [row for row in lunch_rows if row.get("scan_date") == active_lunch_date]
    selected_date_input = f"{active_lunch_date[:4]}-{active_lunch_date[4:6]}-{active_lunch_date[6:8]}" if len(active_lunch_date) == 8 else ""
    ai_dates = sorted({_compact_date(row.get("date")) for row in menu_rows if _compact_date(row.get("date"))}, reverse=True)
    if today not in ai_dates:
        ai_dates.insert(0, today)
    trash_rows = legacy.get_trash_rows() if active_tab == "trash" else []
    preview = meal_preview or {"rows": [], "warnings": [], "warning_count": 0}
    today_dt = datetime.strptime(today, "%Y%m%d") if len(today) == 8 else datetime.now()
    profile_picture = _profile_picture_for_login(session.get("login_id", ""))
    dashboard = _dashboard_data(student_rows, menu_rows, lunch_rows, selected_class, today) if active_tab in {"admin_home", "ai_tools"} else _empty_dashboard()
    student_insights = _student_insights(student_rows) if active_tab in {"admin_home", "student_manage"} else {"rfid_rate": 0, "allergy_rate": 0, "class_counts": [], "allergy_counts": []}
    menu_insights = _menu_insights(menu_rows, today) if active_tab in {"menu_manage", "ai_tools"} else {"today_count": 0, "week_count": 0, "risk_count": 0, "missing_codes": 0, "date_counts": [], "allergy_counts": [], "week_labels": [], "week_risk_values": []}
    lunch_insights = _lunch_insights(lunch_rows, today) if active_tab == "lunch_log" else _lunch_insights([], today)
    chart_data = _chart_data(student_rows, menu_rows, lunch_rows, today) if active_tab in {"admin_home", "student_manage", "menu_manage", "lunch_log", "ai_tools"} else _empty_chart_data()

    return {"page_title": title, "title": title, "subtitle": subtitle, "active_tab": active_tab, "menu_rows": menu_rows, "menu_groups": menu_groups, "menu_timeline": _menu_timeline(menu_groups, today), "student_rows": filtered_students, "all_student_rows": student_rows, "student_summary": student_summary, "student_class_groups": legacy.build_class_groups(filtered_students), "lunch_log_rows": filtered_lunch, "lunch_log_class_groups": legacy.build_class_groups(filtered_lunch), "trash_rows": trash_rows, "trash_summary": _trash_summary(trash_rows), "allergy_map": legacy.ALLERGY_MAP, "default_admin_name": legacy.DEFAULT_ADMIN_NAME, "default_student_password": legacy.DEFAULT_STUDENT_PASSWORD, "rfid_dashboard_url": legacy.RFID_DASHBOARD_URL, "logged_in": legacy.is_logged_in(), "login_name": session.get("login_name", "관리자"), "login_id": session.get("login_id", ""), "profile_picture": profile_picture, "notifications": _notifications(filtered_students, menu_rows, lunch_rows), "available_classes": _available_classes(class_keys), "selected_class": selected_class, "selected_date": selected_date, "selected_date_input": selected_date_input, "lunch_log_date_options": sorted(list({row["scan_date"] for row in lunch_rows if row.get("scan_date")}), reverse=True), "today_stats": legacy.build_lunch_log_stats(today_rows, all_students=student_rows), "attendance_summary": legacy.build_not_eaten_students(student_rows, attendance_rows, selected_class=selected_class), "active_lunch_date": active_lunch_date, "today_sheet": today, "today_label": _date_label(today), "today_weekday": ["월", "화", "수", "목", "금", "토", "일"][today_dt.weekday()], "ai_date_options": ai_dates[:80], "meal_mode": meal_mode, "meal_preview": preview, "meal_preview_summary": _meal_preview_summary(preview), "meal_ocr_text": meal_ocr_text, "meal_error": meal_error, "meal_created_by": meal_created_by or session.get("login_name", legacy.DEFAULT_ADMIN_NAME), "next_class_no": max([int(key.split("-")[1]) for key in class_keys if key != "unknown"] + [1]) + 1, "public_base_url": legacy.load_public_base_url(), "dashboard": dashboard, "student_insights": student_insights, "menu_insights": menu_insights, "lunch_insights": lunch_insights, "chart_data": chart_data}

def render_admin_page_v5(title, subtitle, active_tab, meal_mode="upload", meal_preview=None, meal_ocr_text="", meal_error="", meal_created_by=None):
    context = _build_context(title, subtitle, active_tab, meal_mode, meal_preview, meal_ocr_text, meal_error, meal_created_by)
    context["legacy_admin_tail"] = Markup(render_template_string(_legacy_admin_tail(), **context))
    return render_template(_TEMPLATE_BY_TAB.get(active_tab, "admin/home.html"), **context)
