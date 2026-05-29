from __future__ import annotations

import re
from datetime import datetime


ALLERGY_MAP = {}
TIMESTAMP_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
)


def set_allergy_map(allergy_map):
    global ALLERGY_MAP
    ALLERGY_MAP = dict(allergy_map or {})


def safe_str(value) -> str:
    return "" if value is None else str(value)


def parse_codes(value):
    if value is None:
        return set()

    if isinstance(value, (list, tuple, set)):
        codes = set()
        for item in value:
            codes |= parse_codes(item)
        return codes

    text = str(value).strip()
    if not text:
        return set()

    codes = set()
    for token in re.findall(r"\d+", text):
        try:
            number = int(token)
        except Exception:
            continue
        if 1 <= number <= 19:
            codes.add(number)

    return codes


def codes_to_names(codes):
    return [ALLERGY_MAP.get(code, f"Unknown({code})") for code in codes]


def code_string_to_names(value, empty_text="없음"):
    codes = sorted(list(parse_codes(value)))
    if not codes:
        return empty_text
    return ", ".join(codes_to_names(codes))


def parse_timestamp(value):
    text = safe_str(value).strip()
    if not text:
        return None

    for fmt in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            pass
    return None


def build_menu_conflicts(student_codes, menus):
    eaten_menu_names = []
    blocked_menu_names = []
    blocked_codes = set()

    for menu in menus:
        menu_name = safe_str(menu.get("menu_name")).strip()
        menu_codes = parse_codes(menu.get("allergy_codes"))
        matched = student_codes & menu_codes

        if matched:
            if menu_name:
                blocked_menu_names.append(menu_name)
            blocked_codes |= matched
        elif menu_name:
            eaten_menu_names.append(menu_name)

    return eaten_menu_names, blocked_menu_names, sorted(blocked_codes)


def merge_menu_allergies(menus):
    merged_codes = set()
    menu_names = []

    for menu in menus:
        menu_name = safe_str(menu.get("menu_name")).strip()
        allergy_codes = parse_codes(menu.get("allergy_codes"))
        if menu_name:
            menu_names.append(menu_name)
        merged_codes |= allergy_codes

    return sorted(list(merged_codes)), menu_names


def get_menu_hit_details(student_codes, menus):
    details = []
    for menu in menus:
        menu_name = safe_str(menu.get("menu_name")).strip()
        menu_codes = parse_codes(menu.get("allergy_codes"))
        hit = sorted(list(student_codes & menu_codes))
        if hit:
            details.append(
                {
                    "menu_name": menu_name,
                    "hit_codes": hit,
                    "hit_names": codes_to_names(hit),
                }
            )
    return details


def student_number_to_parts(student_number):
    digits = "".join(ch for ch in safe_str(student_number) if ch.isdigit())
    if len(digits) != 5:
        return {
            "student_number": safe_str(student_number).strip(),
            "grade": None,
            "class_no": None,
            "number": None,
            "class_key": "unknown",
            "class_label": "미분류",
            "student_label": safe_str(student_number).strip() or "-",
        }

    grade = int(digits[0])
    class_no = int(digits[1:3])
    number = int(digits[3:5])
    return {
        "student_number": digits,
        "grade": grade,
        "class_no": class_no,
        "number": number,
        "class_key": f"{grade}-{class_no}",
        "class_label": f"{grade}학년 {class_no}반",
        "student_label": f"{number}번",
    }


def build_student_number(grade, class_no, number):
    try:
        grade = int(str(grade).strip())
        class_no = int(str(class_no).strip())
        number = int(str(number).strip())
    except Exception:
        return ""

    if grade <= 0 or class_no <= 0 or number <= 0:
        return ""
    if grade >= 10 or class_no >= 100 or number >= 100:
        return ""
    return f"{grade}{class_no:02d}{number:02d}"


def enrich_student_like_row(row):
    parts = student_number_to_parts(row.get("student_number", ""))
    new_row = dict(row)
    new_row.update(parts)
    return new_row


def sort_class_key(class_key):
    if class_key == "unknown":
        return (999, 999)
    try:
        grade, class_no = class_key.split("-")
        return (int(grade), int(class_no))
    except Exception:
        return (999, 999)


def get_available_class_keys(student_rows=None, lunch_log_rows=None):
    keys = {"1-1"}
    for row in student_rows or []:
        if row.get("class_key") and row.get("class_key") != "unknown":
            keys.add(row["class_key"])
    for row in lunch_log_rows or []:
        if row.get("class_key") and row.get("class_key") != "unknown":
            keys.add(row["class_key"])
    return sorted(keys, key=sort_class_key)


def build_class_groups(rows):
    grouped = {}
    for row in rows:
        key = row.get("class_key", "unknown")
        if key not in grouped:
            grouped[key] = {
                "class_key": key,
                "class_label": row.get("class_label", "미분류"),
                "rows": [],
            }
        grouped[key]["rows"].append(row)

    groups = []
    for key in sorted(grouped.keys(), key=sort_class_key):
        item = grouped[key]
        item["rows"].sort(
            key=lambda row: (
                (row.get("number") or 999),
                row.get("student_number", ""),
                row.get("name", ""),
            )
        )
        groups.append(item)
    return groups


def build_lunch_log_stats(rows, all_students=None):
    latest_by_person = {}
    for row in rows:
        student_key = (
            safe_str(row.get("rfid_id")).strip()
            or safe_str(row.get("student_number")).strip()
            or safe_str(row.get("name")).strip()
            or f"row-{row.get('row_index', '')}"
        )
        if student_key not in latest_by_person:
            latest_by_person[student_key] = row

    latest_rows = list(latest_by_person.values())
    registered_students = [
        row for row in (all_students or [])
        if safe_str(row.get("trash", "0")) != "1"
    ]
    registered_student_numbers = {
        safe_str(row.get("student_number")).strip()
        for row in registered_students
        if safe_str(row.get("student_number")).strip()
    }
    registered_rfid_ids = {
        safe_str(row.get("rfid_id")).strip()
        for row in registered_students
        if safe_str(row.get("rfid_id")).strip()
    }

    if registered_students:
        latest_rows = [
            row for row in latest_rows
            if (
                safe_str(row.get("student_number")).strip() in registered_student_numbers
                or safe_str(row.get("rfid_id")).strip() in registered_rfid_ids
            )
        ]

    total_count = len(latest_rows)
    warning_count = sum(1 for row in latest_rows if safe_str(row.get("result")) == "경고")
    ok_count = sum(1 for row in latest_rows if safe_str(row.get("result")) == "OK")
    other_count = total_count - warning_count - ok_count
    total_students = len(registered_students)
    utilization_rate = round((total_count / total_students) * 100, 1) if total_students else 0.0
    return {
        "total_count": total_count,
        "warning_count": warning_count,
        "ok_count": ok_count,
        "other_count": other_count,
        "total_students": total_students,
        "utilization_rate": utilization_rate,
        "scan_count": len(rows),
    }


def build_not_eaten_students(all_students, date_rows, selected_class="all"):
    eligible_students = []
    for student in all_students or []:
        if safe_str(student.get("trash", "0")) == "1":
            continue
        if selected_class != "all" and safe_str(student.get("class_key")) != selected_class:
            continue
        eligible_students.append(student)

    eaten_student_numbers = set()
    latest_by_person = {}
    for row in date_rows or []:
        student_key = (
            safe_str(row.get("student_number")).strip()
            or safe_str(row.get("rfid_id")).strip()
            or safe_str(row.get("name")).strip()
        )
        if not student_key:
            continue
        if student_key not in latest_by_person:
            latest_by_person[student_key] = row

    for row in latest_by_person.values():
        result = safe_str(row.get("result")).strip()
        student_no = safe_str(row.get("student_number")).strip()
        if result in {"OK", "경고"} and student_no:
            eaten_student_numbers.add(student_no)

    not_eaten_rows = []
    eaten_rows = []
    for student in eligible_students:
        student_no = safe_str(student.get("student_number")).strip()
        if student_no and student_no in eaten_student_numbers:
            eaten_rows.append(student)
        else:
            not_eaten_rows.append(student)

    sort_key = lambda row: (
        int(safe_str(row.get("grade", "0")) or 0),
        int(safe_str(row.get("class_no", "0")) or 0),
        int(safe_str(row.get("number", "0")) or 0),
        safe_str(row.get("student_number")),
    )
    not_eaten_rows.sort(key=sort_key)
    eaten_rows.sort(key=sort_key)

    return {
        "total_students": len(eligible_students),
        "eaten_count": len(eaten_rows),
        "not_eaten_count": len(not_eaten_rows),
        "not_eaten_rows": not_eaten_rows,
        "eaten_rows": eaten_rows,
    }

