from __future__ import annotations

import json
from typing import Any

from core.admin_domain import parse_codes
from core.admin_sheet_utils import append_row_by_headers


def _safe_str(value) -> str:
    return "" if value is None else str(value)


def normalize_compact_date(value: str) -> str:
    digits = "".join(ch for ch in _safe_str(value) if ch.isdigit())
    if len(digits) != 8:
        raise ValueError("급식 날짜는 YYYYMMDD 형식이어야 해.")
    return digits


def parse_preview_form(form) -> dict[str, Any]:
    created_by = _safe_str(form.get("created_by")).strip()
    ocr_text = _safe_str(form.get("ocr_text")).strip()

    try:
        row_count = max(int(form.get("row_count", "0") or 0), 0)
    except Exception:
        row_count = 0

    rows = []
    for index in range(row_count):
        date_value = normalize_compact_date(form.get(f"row_date_{index}", ""))
        menu_name = _safe_str(form.get(f"row_menu_name_{index}")).strip()
        if not menu_name:
            continue

        allergy_codes = sorted(parse_codes(form.get(f"row_allergy_codes_{index}", "")))
        try:
            confidence = round(float(form.get(f"row_confidence_{index}", "0") or 0), 2)
        except Exception:
            confidence = 0.0

        row_created_by = _safe_str(form.get(f"row_created_by_{index}")).strip() or created_by
        trash = "1" if _safe_str(form.get(f"row_trash_{index}", "0")).strip() == "1" else "0"

        rows.append(
            {
                "date": date_value,
                "menu_name": menu_name,
                "allergy_codes": allergy_codes,
                "confidence": confidence,
                "needs_review": form.get(f"row_needs_review_{index}") == "on",
                "review_reason": _safe_str(form.get(f"row_review_reason_{index}")).strip(),
                "created_by": row_created_by,
                "trash": trash,
            }
        )

    warnings_raw = _safe_str(form.get("warnings_json", "[]")).strip() or "[]"
    try:
        warnings = json.loads(warnings_raw)
    except Exception:
        warnings = []

    return {
        "created_by": created_by,
        "ocr_text": ocr_text,
        "rows": merge_duplicate_menu_rows(rows),
        "warnings": warnings,
    }


def merge_duplicate_menu_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    order: list[tuple[str, str]] = []

    for row in rows or []:
        date_value = normalize_compact_date(row.get("date", ""))
        menu_name = _safe_str(row.get("menu_name")).strip()
        if not menu_name:
            continue

        key = (date_value, menu_name)
        allergy_codes = set(parse_codes(row.get("allergy_codes", [])))
        if key not in merged:
            item = dict(row)
            item["date"] = date_value
            item["menu_name"] = menu_name
            item["allergy_codes"] = sorted(allergy_codes)
            merged[key] = item
            order.append(key)
            continue

        item = merged[key]
        item["allergy_codes"] = sorted(set(parse_codes(item.get("allergy_codes", []))) | allergy_codes)
        item["needs_review"] = bool(item.get("needs_review")) or bool(row.get("needs_review"))

        review_parts = []
        for text in (item.get("review_reason"), row.get("review_reason")):
            text = _safe_str(text).strip()
            if text and text not in review_parts:
                review_parts.append(text)
        item["review_reason"] = " / ".join(review_parts)

        try:
            item["confidence"] = min(float(item.get("confidence", 0) or 0), float(row.get("confidence", 0) or 0))
        except Exception:
            item["confidence"] = item.get("confidence", row.get("confidence", 0))

        if _safe_str(item.get("trash", "0")).strip() != "1":
            item["trash"] = "1" if _safe_str(row.get("trash", "0")).strip() == "1" else "0"

    return [merged[key] for key in order]


def save_ai_meal_analysis(menu_ws, analysis: dict[str, Any], created_by: str, now_time_str_fn):
    saved_rows = []

    for row in merge_duplicate_menu_rows(analysis.get("rows", [])):
        date_value = normalize_compact_date(row.get("date", ""))
        menu_name = _safe_str(row.get("menu_name")).strip()
        if not menu_name:
            continue

        allergy_codes = sorted(parse_codes(row.get("allergy_codes", [])))
        row_created_by = _safe_str(row.get("created_by")).strip() or created_by
        row_dict = {
            "date": date_value,
            "menu_name": menu_name,
            "allergy_codes": ",".join(str(code) for code in allergy_codes),
            "created_by": row_created_by,
            "created_at": now_time_str_fn(),
            "trash": "1" if _safe_str(row.get("trash", "0")).strip() == "1" else "0",
        }
        append_row_by_headers(menu_ws, row_dict)
        saved_rows.append(
            {
                "date": date_value,
                "menu_name": menu_name,
                "allergy_codes": allergy_codes,
                "created_by": row_created_by,
                "trash": row_dict["trash"],
            }
        )

    return {
        "saved_count": len(saved_rows),
        "saved_rows": saved_rows,
    }
