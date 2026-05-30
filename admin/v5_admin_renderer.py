import base64
import gzip
from functools import lru_cache
from pathlib import Path

from flask import render_template_string, request, session

from admin import app_admin as legacy


_ASSET_DIR = Path(__file__).with_name("v5_assets")


def _read_asset(name):
    chunks = []
    for path in sorted(_ASSET_DIR.glob(f"{name}.*.b64")):
        chunks.append(path.read_text(encoding="ascii").strip())
    if not chunks:
        raise RuntimeError(f"Missing v5 admin asset: {name}")
    return gzip.decompress(base64.b64decode("".join(chunks))).decode("utf-8")


@lru_cache(maxsize=1)
def _v5_admin_html():
    return _read_asset("admin_html")


@lru_cache(maxsize=1)
def _v5_admin_css():
    return _read_asset("admin_css")


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
    return [{"key": "all", "label": "\uc804\uccb4"}] + [
        {"key": key, "label": f"{key.split('-')[0]}\ud559\ub144 {int(key.split('-')[1])}\ubc18"}
        for key in available_class_keys
        if key != "unknown"
    ]


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
            legacy.compact_date_value(row.get("date"))
            for row in legacy.get_all_menu_rows(include_trash=False)
            if legacy.compact_date_value(row.get("date"))
        },
        reverse=True,
    )
    if today_sheet not in ai_date_options:
        ai_date_options.insert(0, today_sheet)

    return {
        "page_title": title,
        "title": title,
        "subtitle": subtitle,
        "active_tab": active_tab,
        "menu_rows": legacy.get_all_menu_rows(),
        "menu_groups": legacy.get_menu_groups(),
        "student_rows": filtered_student_rows,
        "student_summary": student_summary,
        "student_class_groups": legacy.build_class_groups(filtered_student_rows),
        "lunch_log_rows": filtered_lunch_rows,
        "lunch_log_class_groups": legacy.build_class_groups(filtered_lunch_rows),
        "trash_rows": legacy.get_trash_rows(),
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
        "ai_date_options": ai_date_options[:80],
        "meal_mode": meal_mode,
        "meal_preview": meal_preview or {"rows": [], "warnings": [], "warning_count": 0},
        "meal_ocr_text": meal_ocr_text,
        "meal_error": meal_error,
        "meal_created_by": meal_created_by or session.get("login_name", legacy.DEFAULT_ADMIN_NAME),
        "next_class_no": max([int(key.split("-")[1]) for key in available_class_keys if key != "unknown"] + [1]) + 1,
        "public_base_url": legacy.load_public_base_url(),
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
    template = (
        _v5_admin_html()
        .replace("__V5_ADMIN_CSS__", _v5_admin_css())
        .replace("__LEGACY_ADMIN_TAIL__", _legacy_admin_tail())
    )
    return render_template_string(template, **context)
