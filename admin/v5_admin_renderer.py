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


def _available_classes(available_class_keys):
    classes = [{"key": "all", "label": "\uc804\uccb4"}]
    for key in available_class_keys:
        if key == "unknown":
            continue
        parts = key.split("-")
        if len(parts) != 2:
            continue
        try:
            classes.append({"key": key, "label": f"{parts[0]}\ud559\ub144 {int(parts[1])}\ubc18"})
        except ValueError:
            classes.append({"key": key, "label": key})
    return classes


def _compact_date(value):
    return legacy.compact_date_value(value)


def _date_label(value):
    text = _compact_date(value)
    if len(text) == 8:
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text or "-"


def _result_bucket(row):
    result = legacy.safe_str(row.get("result")).strip().lower()
    hit_names = legacy.safe_str(row.get("hit_names")).strip()
    hit_codes = legacy.safe_str(row.get("hit_codes")).strip()
    if "ok" in result or result in {"\ud1b5\uacfc", "\uc548\uc804"}:
        return "safe"
    if "\uacbd\uace0" in result or "\uc704\ud5d8" in result or hit_names or hit_codes:
        return "danger"
    if "\ubbf8\ub4f1\ub85d" in result:
        return "unknown"
    if "\uc624\ub958" in result:
        return "error"
    return "notice"


def _scan_hour(row):
    scanned_at = legacy.safe_str(row.get("scanned_at")).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(scanned_at, fmt).hour
        except ValueError:
            pass
    if len(scanned_at) >= 13 and scanned_at[11:13].isdigit():
        return int(scanned_at[11:13])
    if len(scanned_at) >= 10 and scanned_at[8:10].isdigit():
        return int(scanned_at[8:10])
    return None


def _dashboard_data(student_rows, menu_rows, lunch_log_rows, selected_class, today_sheet):
    total_students = len(student_rows)
    allergy_students = sum(1 for row in student_rows if legacy.parse_codes(row.get("allergy_codes")))
    rfid_students = sum(1 for row in student_rows if legacy.safe_str(row.get("rfid_id")).strip())
    no_rfid_students = total_students - rfid_students

    today_menus = [row for row in menu_rows if _compact_date(row.get("date")) == today_sheet]
    today_logs = [row for row in lunch_log_rows if row.get("scan_date") == today_sheet]
    if selected_class != "all":
        today_logs = [row for row in today_logs if row.get("class_key") == selected_class]

    buckets = Counter(_result_bucket(row) for row in today_logs)
    risk_menus = []
    for row in today_menus:
        if legacy.parse_codes(row.get("allergy_codes")):
            risk_menus.append(row)

    return {
        "stats": {
            "total_students": total_students,
            "allergy_students": allergy_students,
            "rfid_students": rfid_students,
            "no_rfid_students": no_rfid_students,
            "today_scan_count": len(today_logs),
            "today_safe_count": buckets.get("safe", 0),
            "today_danger_count": buckets.get("danger", 0),
            "today_unknown_count": buckets.get("unknown", 0),
        },
        "today_menus": today_menus,
        "risk_menus": risk_menus,
        "recent_logs": today_logs[:8] if today_logs else lunch_log_rows[:8],
    }


def _chart_data(student_rows, lunch_log_rows, today_sheet):
    today_rows = [row for row in lunch_log_rows if row.get("scan_date") == today_sheet]
    hour_counts = [0] * 24
    for row in today_rows:
        hour = _scan_hour(row)
        if hour is not None and 0 <= hour <= 23:
            hour_counts[hour] += 1

    result_counts = Counter(_result_bucket(row) for row in today_rows)
    today_dt = datetime.strptime(today_sheet, "%Y%m%d") if len(today_sheet) == 8 else datetime.now()
    trend_labels = []
    trend_values = []
    by_day = defaultdict(int)
    for row in lunch_log_rows:
        if _result_bucket(row) == "danger" and row.get("scan_date"):
            by_day[row.get("scan_date")] += 1
    for offset in range(6, -1, -1):
        day = today_dt - timedelta(days=offset)
        key = day.strftime("%Y%m%d")
        trend_labels.append(day.strftime("%m/%d"))
        trend_values.append(by_day.get(key, 0))

    allergy_count = sum(1 for row in student_rows if legacy.parse_codes(row.get("allergy_codes")))
    rfid_count = sum(1 for row in student_rows if legacy.safe_str(row.get("rfid_id")).strip())
    return {
        "hourly": {
            "labels": [f"{hour:02d}" for hour in range(24)],
            "values": hour_counts,
        },
        "results": {
            "labels": ["\uc548\uc804", "\uc704\ud5d8", "\ubbf8\ub4f1\ub85d", "\uc624\ub958/\uc8fc\uc758"],
            "values": [
                result_counts.get("safe", 0),
                result_counts.get("danger", 0),
                result_counts.get("unknown", 0),
                result_counts.get("error", 0) + result_counts.get("notice", 0),
            ],
            "colors": ["#47b881", "#e55353", "#f0ad4e", "#6c7ae0"],
        },
        "danger_trend": {
            "labels": trend_labels,
            "values": trend_values,
        },
        "student_mix": {
            "labels": ["\uc54c\ub808\ub974\uae30", "\uc77c\ubc18"],
            "values": [allergy_count, max(len(student_rows) - allergy_count, 0)],
            "colors": ["#e55353", "#47b881"],
        },
        "rfid_mix": {
            "labels": ["RFID \ub4f1\ub85d", "RFID \ubbf8\ub4f1\ub85d"],
            "values": [rfid_count, max(len(student_rows) - rfid_count, 0)],
            "colors": ["#5b8def", "#f0ad4e"],
        },
    }


def _menu_timeline(menu_groups, today_sheet):
    today = []
    upcoming = []
    past = []
    for group in menu_groups:
        date_key = _compact_date(group.get("date"))
        if date_key == today_sheet:
            today.append(group)
        elif date_key > today_sheet:
            upcoming.append(group)
        else:
            past.append(group)
    return {
        "today": today,
        "upcoming": sorted(upcoming, key=lambda item: _compact_date(item.get("date")))[:12],
        "past": past[:12],
    }


def _trash_summary(trash_rows):
    students = sum(1 for row in trash_rows if row.get("kind") == "\ud559\uc0dd")
    menus = sum(1 for row in trash_rows if row.get("kind") == "\uae09\uc2dd")
    return {"total": len(trash_rows), "students": students, "menus": menus}


def _build_context(
    title,
    subtitle,
    active_tab,
    meal_mode="upload",
    meal_preview=None,
    meal_ocr_text="",
    meal_error="",
    meal_created_by=None,
):
    selected_class = legacy.safe_str(request.args.get("class_key", "all")).strip() or "all"
    selected_date = legacy.safe_str(request.args.get("date", "")).replace("-", "").strip()

    student_rows = legacy.get_all_student_rows()
    menu_rows = legacy.get_all_menu_rows()
    menu_groups = legacy.get_menu_groups()
    lunch_log_rows = legacy.get_all_lunch_log_rows()
    available_class_keys = legacy.get_available_class_keys(
        student_rows=student_rows,
        lunch_log_rows=lunch_log_rows,
    )
    available_classes = _available_classes(available_class_keys)

    if selected_class != "all":
        filtered_student_rows = [x for x in student_rows if x.get("class_key") == selected_class]
    else:
        filtered_student_rows = list(student_rows)

    student_summary = {
        "total": len(filtered_student_rows),
        "allergy": sum(1 for row in filtered_student_rows if legacy.parse_codes(row.get("allergy_codes"))),
        "rfid": sum(1 for row in filtered_student_rows if legacy.safe_str(row.get("rfid_id")).strip()),
        "no_rfid": sum(1 for row in filtered_student_rows if not legacy.safe_str(row.get("rfid_id")).strip()),
    }

    if selected_date:
        filtered_lunch_rows = [x for x in lunch_log_rows if x.get("scan_date") == selected_date]
    else:
        filtered_lunch_rows = list(lunch_log_rows)
    if selected_class != "all":
        filtered_lunch_rows = [x for x in filtered_lunch_rows if x.get("class_key") == selected_class]

    lunch_log_date_options = sorted(
        list({x["scan_date"] for x in lunch_log_rows if x.get("scan_date")}),
        reverse=True,
    )
    active_lunch_date = selected_date or legacy.today_sheet_str()
    today_rows = [x for x in lunch_log_rows if x.get("scan_date") == legacy.today_sheet_str()]
    date_rows_for_attendance = [x for x in lunch_log_rows if x.get("scan_date") == active_lunch_date]
    today_stats = legacy.build_lunch_log_stats(today_rows, all_students=student_rows)
    attendance_summary = legacy.build_not_eaten_students(
        student_rows,
        date_rows_for_attendance,
        selected_class=selected_class,
    )

    selected_date_input = ""
    if selected_date and len(selected_date) == 8:
        selected_date_input = f"{selected_date[:4]}-{selected_date[4:6]}-{selected_date[6:8]}"
    elif not selected_date and len(active_lunch_date) == 8:
        selected_date_input = f"{active_lunch_date[:4]}-{active_lunch_date[4:6]}-{active_lunch_date[6:8]}"

    today_sheet = legacy.today_sheet_str()
    ai_date_options = sorted(
        {
            _compact_date(row.get("date"))
            for row in menu_rows
            if _compact_date(row.get("date"))
        },
        reverse=True,
    )
    if today_sheet not in ai_date_options:
        ai_date_options.insert(0, today_sheet)

    trash_rows = legacy.get_trash_rows()

    return {
        "page_title": title,
        "title": title,
        "subtitle": subtitle,
        "active_tab": active_tab,
        "menu_rows": menu_rows,
        "menu_groups": menu_groups,
        "menu_timeline": _menu_timeline(menu_groups, today_sheet),
        "student_rows": filtered_student_rows,
        "all_student_rows": student_rows,
        "student_summary": student_summary,
        "student_class_groups": legacy.build_class_groups(filtered_student_rows),
        "lunch_log_rows": filtered_lunch_rows,
        "lunch_log_class_groups": legacy.build_class_groups(filtered_lunch_rows),
        "trash_rows": trash_rows,
        "trash_summary": _trash_summary(trash_rows),
        "allergy_map": legacy.ALLERGY_MAP,
        "default_admin_name": legacy.DEFAULT_ADMIN_NAME,
        "default_student_password": legacy.DEFAULT_STUDENT_PASSWORD,
        "rfid_dashboard_url": legacy.RFID_DASHBOARD_URL,
        "logged_in": legacy.is_logged_in(),
        "login_name": session.get("login_name", "\uad00\ub9ac\uc790"),
        "login_id": session.get("login_id", ""),
        "available_classes": available_classes,
        "selected_class": selected_class,
        "selected_date": selected_date,
        "selected_date_input": selected_date_input,
        "lunch_log_date_options": lunch_log_date_options,
        "today_stats": today_stats,
        "attendance_summary": attendance_summary,
        "active_lunch_date": active_lunch_date,
        "today_sheet": today_sheet,
        "today_label": _date_label(today_sheet),
        "ai_date_options": ai_date_options[:80],
        "meal_mode": meal_mode,
        "meal_preview": meal_preview or {"rows": [], "warnings": [], "warning_count": 0},
        "meal_ocr_text": meal_ocr_text,
        "meal_error": meal_error,
        "meal_created_by": meal_created_by or session.get("login_name", legacy.DEFAULT_ADMIN_NAME),
        "next_class_no": max([int(key.split("-")[1]) for key in available_class_keys if key != "unknown"] + [1]) + 1,
        "public_base_url": legacy.load_public_base_url(),
        "dashboard": _dashboard_data(student_rows, menu_rows, lunch_log_rows, selected_class, today_sheet),
        "chart_data": _chart_data(student_rows, lunch_log_rows, today_sheet),
    }


def render_admin_page_v5(
    title,
    subtitle,
    active_tab,
    meal_mode="upload",
    meal_preview=None,
    meal_ocr_text="",
    meal_error="",
    meal_created_by=None,
):
    context = _build_context(
        title=title,
        subtitle=subtitle,
        active_tab=active_tab,
        meal_mode=meal_mode,
        meal_preview=meal_preview,
        meal_ocr_text=meal_ocr_text,
        meal_error=meal_error,
        meal_created_by=meal_created_by,
    )
    template_name = _TEMPLATE_BY_TAB.get(active_tab, "admin/home.html")
    context["legacy_admin_tail"] = Markup(render_template_string(_legacy_admin_tail(), **context))
    return render_template(template_name, **context)
