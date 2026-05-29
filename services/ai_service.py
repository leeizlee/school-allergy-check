from __future__ import annotations

import copy
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


logger = logging.getLogger(__name__)

DEFAULT_MEAL_MODEL = os.getenv("OPENAI_MEAL_MODEL", "gpt-4o-mini")
DEFAULT_RISK_MODEL = os.getenv("OPENAI_RISK_MODEL", "gpt-4o-mini")
DEFAULT_SAFETY_MODEL = os.getenv("OPENAI_SAFETY_MODEL", "gpt-4o-mini")
DEFAULT_BRIEF_MODEL = os.getenv("OPENAI_BRIEF_MODEL", "gpt-4o-mini")

_CLIENT = None
_CACHE_TTL_SECONDS = int(os.getenv("AI_CACHE_TTL_SECONDS", "600"))
_ANALYSIS_CACHE: dict[str, dict[str, Any]] = {}
_RISK_CACHE: dict[str, dict[str, Any]] = {}
_SAFETY_CACHE: dict[str, dict[str, Any]] = {}
_BRIEF_CACHE: dict[str, dict[str, Any]] = {}
_MENU_REVIEW_CACHE: dict[str, dict[str, Any]] = {}


class AIServiceError(RuntimeError):
    pass


MEAL_ANALYSIS_SCHEMA = {
    "name": "meal_sheet_rows",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "date": {"type": "string"},
                        "menu_name": {"type": "string"},
                        "allergy_codes": {"type": "array", "items": {"type": "integer"}},
                        "confidence": {"type": "number"},
                        "needs_review": {"type": "boolean"},
                        "review_reason": {"type": "string"},
                    },
                    "required": [
                        "date",
                        "menu_name",
                        "allergy_codes",
                        "confidence",
                        "needs_review",
                        "review_reason",
                    ],
                },
            },
            "warnings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "date": {"type": "string"},
                        "menu_name": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "required": ["date", "menu_name", "message"],
                },
            },
        },
        "required": ["rows", "warnings"],
    },
}

RISK_ASSIST_SCHEMA = {
    "name": "meal_risk_assist",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "risk_explanation": {"type": "string"},
            "matched_allergies": {"type": "array", "items": {"type": "string"}},
            "unsafe_menus": {"type": "array", "items": {"type": "string"}},
            "alternative_recommendation": {"type": "string"},
            "needs_staff_review": {"type": "boolean"},
        },
        "required": [
            "risk_explanation",
            "matched_allergies",
            "unsafe_menus",
            "alternative_recommendation",
            "needs_staff_review",
        ],
    },
}

SAFETY_PLAN_SCHEMA = {
    "name": "allergy_safety_plan",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "risk_level": {"type": "string"},
            "risk_summary": {"type": "string"},
            "alternative_meals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string"},
                        "components": {"type": "string"},
                        "preparation_notes": {"type": "string"},
                        "avoids": {"type": "array", "items": {"type": "string"}},
                        "reason": {"type": "string"},
                        "staff_check": {"type": "string"},
                    },
                    "required": [
                        "name",
                        "components",
                        "preparation_notes",
                        "avoids",
                        "reason",
                        "staff_check",
                    ],
                },
            },
            "emergency_steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "order": {"type": "integer"},
                        "title": {"type": "string"},
                        "action": {"type": "string"},
                        "owner": {"type": "string"},
                        "urgency": {"type": "string"},
                    },
                    "required": ["order", "title", "action", "owner", "urgency"],
                },
            },
            "guardian_message": {"type": "string"},
            "nurse_message": {"type": "string"},
            "kitchen_message": {"type": "string"},
            "prevention_checklist": {"type": "array", "items": {"type": "string"}},
            "monitoring_points": {"type": "array", "items": {"type": "string"}},
            "staff_review_required": {"type": "boolean"},
        },
        "required": [
            "risk_level",
            "risk_summary",
            "alternative_meals",
            "emergency_steps",
            "guardian_message",
            "nurse_message",
            "kitchen_message",
            "prevention_checklist",
            "monitoring_points",
            "staff_review_required",
        ],
    },
}

DAILY_BRIEF_SCHEMA = {
    "name": "daily_allergy_brief",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "high_risk_count": {"type": "integer"},
            "priority_actions": {"type": "array", "items": {"type": "string"}},
            "watch_students": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "student_name": {"type": "string"},
                        "student_number": {"type": "string"},
                        "risk_level": {"type": "string"},
                        "allergies": {"type": "array", "items": {"type": "string"}},
                        "unsafe_menus": {"type": "array", "items": {"type": "string"}},
                        "action": {"type": "string"},
                    },
                    "required": [
                        "student_name",
                        "student_number",
                        "risk_level",
                        "allergies",
                        "unsafe_menus",
                        "action",
                    ],
                },
            },
            "kitchen_notes": {"type": "array", "items": {"type": "string"}},
            "staff_review_required": {"type": "boolean"},
        },
        "required": [
            "summary",
            "high_risk_count",
            "priority_actions",
            "watch_students",
            "kitchen_notes",
            "staff_review_required",
        ],
    },
}

MENU_REVIEW_SCHEMA = {
    "name": "menu_allergy_review",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "reviewed_menus": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "menu_name": {"type": "string"},
                        "current_codes": {"type": "array", "items": {"type": "integer"}},
                        "suspected_missing_codes": {"type": "array", "items": {"type": "integer"}},
                        "confidence": {"type": "number"},
                        "review_reason": {"type": "string"},
                    },
                    "required": [
                        "menu_name",
                        "current_codes",
                        "suspected_missing_codes",
                        "confidence",
                        "review_reason",
                    ],
                },
            },
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["reviewed_menus", "warnings"],
    },
}

STUDENT_SHEET_SCHEMA = {
    "name": "student_sheet_rows",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "rfid_id": {"type": "string"},
                        "name": {"type": "string"},
                        "student_number": {"type": "string"},
                        "allergy_codes": {"type": "array", "items": {"type": "integer"}},
                        "needs_review": {"type": "boolean"},
                        "review_reason": {"type": "string"},
                    },
                    "required": ["rfid_id", "name", "student_number", "allergy_codes", "needs_review", "review_reason"],
                },
            },
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["rows", "warnings"],
    },
}


def _safe_str(value) -> str:
    return "" if value is None else str(value)


def _dedupe_keep_order(values):
    seen = set()
    result = []
    for value in values or []:
        text = _safe_str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _clean_codes(values) -> list[int]:
    if values is None:
        return []

    if isinstance(values, str):
        raw_values = re.findall(r"\d+", values)
    elif isinstance(values, (list, tuple, set)):
        raw_values = []
        for item in values:
            if isinstance(item, str):
                raw_values.extend(re.findall(r"\d+", item))
            else:
                raw_values.append(item)
    else:
        raw_values = [values]

    cleaned = []
    for value in raw_values:
        try:
            number = int(value)
        except Exception:
            continue
        if 1 <= number <= 19 and number not in cleaned:
            cleaned.append(number)
    cleaned.sort()
    return cleaned


def _get_cache(cache: dict[str, dict[str, Any]], key: str):
    item = cache.get(key)
    if not item:
        return None
    if time.time() - item["ts"] > _CACHE_TTL_SECONDS:
        cache.pop(key, None)
        return None
    return copy.deepcopy(item["value"])


def _set_cache(cache: dict[str, dict[str, Any]], key: str, value: dict[str, Any]) -> dict[str, Any]:
    cache[key] = {"ts": time.time(), "value": copy.deepcopy(value)}
    return copy.deepcopy(value)


def _get_client():
    global _CLIENT

    if OpenAI is None:
        raise AIServiceError("openai 패키지가 설치되어 있지 않아 AI 기능을 사용할 수 없어.")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise AIServiceError("OPENAI_API_KEY 환경변수가 없어 AI 기능을 사용할 수 없어.")

    if _CLIENT is None:
        _CLIENT = OpenAI(api_key=api_key)
    return _CLIENT


def _json_cache_key(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def load_allergy_dict(path: str | os.PathLike[str]) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _normalize_compact_date(value: str, default: str = "") -> str:
    digits = re.sub(r"\D", "", _safe_str(value))
    if len(digits) >= 8:
        return digits[:8]
    if len(digits) == 4 and default:
        default_digits = re.sub(r"\D", "", default)
        if len(default_digits) >= 6:
            return f"{default_digits[:6]}{int(digits):02d}"
    return default


def _extract_default_date(text: str) -> str:
    match = re.search(r"(20\d{2})\D+(\d{1,2})\D+(\d{1,2})", text)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}{int(month):02d}{int(day):02d}"

    month_match = re.search(r"(20\d{2})\D+(\d{1,2})\D", text)
    if month_match:
        year, month = month_match.groups()
        return f"{int(year):04d}{int(month):02d}01"

    return datetime.now().strftime("%Y%m%d")


def _clean_menu_name(text: str) -> str:
    cleaned = _safe_str(text)
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)
    cleaned = re.sub(r"\b\d+(?:\.\d+)?\b", " ", cleaned)
    cleaned = re.sub(r"[※*#·ㆍ•]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_/,:;|")
    return cleaned


def _extract_menu_candidates(ocr_text: str) -> list[str]:
    candidates = []
    stop_keywords = [
        "알레르기",
        "원산지",
        "칼로리",
        "영양",
        "급식",
        "교직원",
        "학교",
        "가정통신문",
        "월",
        "화",
        "수",
        "목",
        "금",
    ]

    separators = re.compile(r"[,/|]+")
    for line in ocr_text.splitlines():
        line = line.strip()
        if not line:
            continue
        for token in separators.split(line):
            menu = _clean_menu_name(token)
            if len(menu) < 2:
                continue
            if any(keyword in menu for keyword in stop_keywords):
                continue
            if re.fullmatch(r"[\d\s\-]+", menu):
                continue
            candidates.append(menu)

    return _dedupe_keep_order(candidates)


def _hint_matches(menu_name: str, keyword: str) -> bool:
    normalized_menu = _safe_str(menu_name).replace(" ", "").lower()
    normalized_keyword = _safe_str(keyword).replace(" ", "").lower()
    return bool(normalized_keyword) and normalized_keyword in normalized_menu


def infer_allergies_from_menu_name(menu_name: str, allergy_dict: dict[str, Any]) -> list[int]:
    inferred = []

    for hint in allergy_dict.get("menu_hints", []):
        keyword = hint.get("keyword", "")
        if _hint_matches(menu_name, keyword):
            for code in _clean_codes(hint.get("allergies", [])):
                if code not in inferred:
                    inferred.append(code)

    for code_text, info in (allergy_dict.get("allergies") or {}).items():
        keywords = info.get("keywords", [])
        if any(_hint_matches(menu_name, keyword) for keyword in keywords):
            try:
                code = int(code_text)
            except Exception:
                continue
            if 1 <= code <= 19 and code not in inferred:
                inferred.append(code)

    inferred.sort()
    return inferred


def _code_name(code: int, allergy_dict: dict[str, Any]) -> str:
    info = (allergy_dict.get("allergies") or {}).get(str(code), {})
    return _safe_str(info.get("name")).strip() or f"알레르기 {code}"


def _validate_analysis(payload: dict[str, Any], allergy_dict: dict[str, Any], ocr_text: str = "") -> dict[str, Any]:
    default_date = _extract_default_date(ocr_text)
    result = {"rows": [], "warnings": []}

    for item in payload.get("rows", []):
        date_value = _normalize_compact_date(item.get("date", ""), default=default_date)
        menu_name = _clean_menu_name(item.get("menu_name"))
        if not date_value or not menu_name:
            continue

        allergy_codes = _clean_codes(item.get("allergy_codes", []))
        inferred = infer_allergies_from_menu_name(menu_name, allergy_dict)
        missing = [code for code in inferred if code not in allergy_codes]
        needs_review = bool(item.get("needs_review"))
        review_reason = _safe_str(item.get("review_reason")).strip()

        if missing:
            missing_names = ", ".join(_code_name(code, allergy_dict) for code in missing)
            message = (
                f"{date_value} {menu_name} 메뉴에 대표 알레르기 번호 "
                f"{', '.join(map(str, missing))}({missing_names})가 빠졌을 가능성이 있어 검토가 필요해."
            )
            result["warnings"].append({"date": date_value, "menu_name": menu_name, "message": message})
            needs_review = True
            if not review_reason:
                review_reason = message
            allergy_codes = _clean_codes(allergy_codes + missing)

        try:
            confidence = round(float(item.get("confidence", 0) or 0), 2)
        except Exception:
            confidence = 0.7 if allergy_codes else 0.45

        result["rows"].append(
            {
                "date": date_value,
                "menu_name": menu_name,
                "allergy_codes": allergy_codes,
                "confidence": max(0.0, min(confidence, 1.0)),
                "needs_review": needs_review,
                "review_reason": review_reason,
            }
        )

    for item in payload.get("warnings", []):
        date_value = _normalize_compact_date(item.get("date", ""), default=default_date)
        menu_name = _safe_str(item.get("menu_name")).strip()
        message = _safe_str(item.get("message")).strip()
        if date_value and menu_name and message:
            result["warnings"].append({"date": date_value, "menu_name": menu_name, "message": message})

    unique_rows = []
    seen_rows = set()
    for row in result["rows"]:
        key = (row["date"], row["menu_name"], tuple(row["allergy_codes"]))
        if key in seen_rows:
            continue
        seen_rows.add(key)
        unique_rows.append(row)
    result["rows"] = sorted(unique_rows, key=lambda row: (row["date"], row["menu_name"]))

    unique_warnings = []
    seen_warnings = set()
    for warning in result["warnings"]:
        key = (warning["date"], warning["menu_name"], warning["message"])
        if key in seen_warnings:
            continue
        seen_warnings.add(key)
        unique_warnings.append(warning)
    result["warnings"] = unique_warnings

    if not result["rows"]:
        raise AIServiceError("AI 결과에서 저장 가능한 급식 행을 찾지 못했어.")

    return result


def build_fallback_meal_analysis(ocr_text: str, allergy_dict: dict[str, Any]) -> dict[str, Any]:
    default_date = _extract_default_date(ocr_text)
    rows = []
    warnings = []

    for menu_name in _extract_menu_candidates(ocr_text):
        inferred = infer_allergies_from_menu_name(menu_name, allergy_dict)
        needs_review = len(inferred) == 0
        review_reason = (
            "메뉴명만으로 확실한 대표 알레르기를 찾지 못해 관리자 확인이 필요합니다."
            if needs_review
            else ""
        )
        if needs_review:
            warnings.append(
                {
                    "date": default_date,
                    "menu_name": menu_name,
                    "message": f"{default_date} {menu_name} 메뉴는 자동 추론 신뢰도가 낮아 검토가 필요합니다.",
                }
            )

        rows.append(
            {
                "date": default_date,
                "menu_name": menu_name,
                "allergy_codes": inferred,
                "confidence": 0.45 if needs_review else 0.65,
                "needs_review": needs_review,
                "review_reason": review_reason,
            }
        )

    if not rows:
        rows = [
            {
                "date": default_date,
                "menu_name": "확인 필요",
                "allergy_codes": [],
                "confidence": 0.2,
                "needs_review": True,
                "review_reason": "OCR 텍스트에서 급식 메뉴를 분리하지 못했어. 직접 수정해줘.",
            }
        ]
        warnings.append(
            {
                "date": default_date,
                "menu_name": "확인 필요",
                "message": "급식표에서 자동으로 메뉴를 분리하지 못했어. 직접 수정이 필요해.",
            }
        )

    return _validate_analysis({"rows": rows, "warnings": warnings}, allergy_dict, ocr_text=ocr_text)


def analyze_meal_ocr_text(ocr_text: str, allergy_dict: dict[str, Any]) -> dict[str, Any]:
    normalized_text = _safe_str(ocr_text).strip()
    if not normalized_text:
        raise AIServiceError("OCR 텍스트가 비어 있어 AI 분석을 진행할 수 없어.")

    cache_key = _json_cache_key({"type": "meal", "text": normalized_text})
    cached = _get_cache(_ANALYSIS_CACHE, cache_key)
    if cached:
        return cached

    fallback_result = build_fallback_meal_analysis(normalized_text, allergy_dict)

    try:
        client = _get_client()
        allergy_catalog = json.dumps(allergy_dict.get("allergies", {}), ensure_ascii=False)
        hints_text = json.dumps(allergy_dict.get("menu_hints", [])[:100], ensure_ascii=False)
        response = client.chat.completions.create(
            model=DEFAULT_MEAL_MODEL,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 한국 학교 급식표 OCR 보정 도우미야. "
                        "월간 급식표든 일일 급식표든 최종 결과는 반드시 food_menu 시트 저장용 행 목록으로 만들어. "
                        "각 메뉴를 한 행으로 분리하고 date(YYYYMMDD), menu_name, allergy_codes를 채워. "
                        "메뉴명이 잘못 인식되면 자연스럽게 보정하고, 알레르기 번호가 비어 있으면 메뉴명과 힌트를 바탕으로 보수적으로 추론해. "
                        "불확실하면 needs_review=true와 review_reason을 채워."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "다음 OCR 텍스트를 food_menu 시트 행 형식으로 구조화해줘.\n\n"
                        "[목표 형식]\n"
                        "date | menu_name | allergy_codes | confidence | needs_review | review_reason\n"
                        "예: 20260418 | 돈가스 | [1,2,5,6,10] | 0.95 | false | \"\"\n\n"
                        f"[OCR]\n{normalized_text}\n\n"
                        f"[알레르기 사전]\n{allergy_catalog}\n\n"
                        f"[메뉴 힌트]\n{hints_text}\n\n"
                        "출력은 반드시 JSON Schema만 따라줘."
                    ),
                },
            ],
            response_format={"type": "json_schema", "json_schema": MEAL_ANALYSIS_SCHEMA},
        )
        message = response.choices[0].message
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise AIServiceError(f"AI가 요청을 거절했어: {refusal}")

        parsed = json.loads(message.content or "{}")
        validated = _validate_analysis(parsed, allergy_dict, ocr_text=normalized_text)
        return _set_cache(_ANALYSIS_CACHE, cache_key, validated)
    except Exception as exc:
        logger.warning("급식표 AI 분석 실패, fallback 사용: %s", exc)
        return _set_cache(_ANALYSIS_CACHE, cache_key, fallback_result)


def analyze_student_sheet_text(sheet_text: str, allergy_dict: dict[str, Any]) -> dict[str, Any]:
    normalized_text = _safe_str(sheet_text).strip()
    if not normalized_text:
        raise AIServiceError("Student sheet text is empty.")

    cache_key = _json_cache_key({"type": "student_sheet", "text": normalized_text})
    cached = _get_cache(_ANALYSIS_CACHE, cache_key)
    if cached:
        return cached

    client = _get_client()
    allergy_catalog = json.dumps(allergy_dict.get("allergies", {}), ensure_ascii=False)
    response = client.chat.completions.create(
        model=DEFAULT_MEAL_MODEL,
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": (
                    "You convert Korean school student roster spreadsheets into normalized rows for an RFID system. "
                    "Create one row per student. Fill rfid_id, name, student_number, allergy_codes, needs_review, and review_reason. "
                    "Normalize student_number to five digits when possible: grade one digit + class two digits + number two digits. "
                    "For example, grade 1 class 3 number 7 becomes 10307. "
                    "If RFID, name, or a valid student number is missing, keep the best value you can and set needs_review=true. "
                    "Use allergy_codes as integer codes only, based on the supplied allergy catalog."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Parse this student roster sheet into the required JSON schema.\n\n"
                    "[Target columns]\n"
                    "rfid_id | name | student_number | allergy_codes | needs_review | review_reason\n\n"
                    f"[Student sheet]\n{normalized_text}\n\n"
                    f"[Allergy catalog]\n{allergy_catalog}\n\n"
                    "Return only data that matches the JSON schema."
                ),
            },
        ],
        response_format={"type": "json_schema", "json_schema": STUDENT_SHEET_SCHEMA},
    )
    message = response.choices[0].message
    refusal = getattr(message, "refusal", None)
    if refusal:
        raise AIServiceError(f"AI refused the request: {refusal}")

    parsed = json.loads(message.content or "{}")
    rows = []
    for item in parsed.get("rows", []):
        rfid_id = _safe_str(item.get("rfid_id")).strip()
        name = _safe_str(item.get("name")).strip()
        student_number = re.sub(r"\D", "", _safe_str(item.get("student_number")).strip())
        allergy_codes = _clean_codes(item.get("allergy_codes", []))
        rows.append(
            {
                "rfid_id": rfid_id,
                "name": name,
                "student_number": student_number,
                "allergy_codes": allergy_codes,
                "needs_review": bool(item.get("needs_review")) or not rfid_id or not name or len(student_number) != 5,
                "review_reason": _safe_str(item.get("review_reason")).strip(),
            }
        )

    result = {"rows": rows, "warnings": parsed.get("warnings") or []}
    return _set_cache(_ANALYSIS_CACHE, cache_key, result)

def _safe_menu_candidates(all_menus: list[str], unsafe_menus: list[str]) -> list[str]:
    unsafe_set = set(_dedupe_keep_order(unsafe_menus))
    return [menu for menu in _dedupe_keep_order(all_menus) if menu not in unsafe_set]


def build_fallback_risk_assistance(
    student_name: str,
    student_allergies: list[str],
    unsafe_menus: list[str],
    matched_allergies: list[str],
    all_menus: list[str],
) -> dict[str, Any]:
    unsafe = _dedupe_keep_order(unsafe_menus)
    matched = _dedupe_keep_order(matched_allergies or student_allergies)
    safe_menus = _safe_menu_candidates(all_menus, unsafe)
    student_label = student_name or "학생"

    if unsafe:
        explanation = (
            f"오늘 메뉴 중 {', '.join(unsafe)}에 {', '.join(matched) or '학생 등록 알레르기'} 관련 성분이 "
            f"포함될 가능성이 있어 {student_label}에게 주의가 필요합니다."
        )
    else:
        explanation = (
            f"{student_label}의 등록 알레르기와 오늘 메뉴의 직접 충돌은 현재 데이터 기준으로 확인되지 않았습니다. "
            "다만 실제 제공 전 원재료와 조리 교차접촉 여부는 확인해야 합니다."
        )

    if safe_menus:
        alternative = (
            f"{', '.join(safe_menus)} 중심으로 별도 제공 가능 여부를 확인해 주세요. "
            "AI 추천안이며 최종 제공 여부는 급식 담당자가 원재료표와 조리 상태를 확인해야 합니다."
        )
    else:
        alternative = (
            "오늘 전체 메뉴 안에서 바로 안전하다고 확정할 수 있는 대체 급식을 찾지 못했습니다. "
            "흰밥, 개별 포장 식품, 별도 조리 반찬 등 학교 기준에 맞는 대체식을 담당자가 확인해 주세요."
        )

    return {
        "risk_explanation": explanation,
        "matched_allergies": matched,
        "unsafe_menus": unsafe,
        "alternative_recommendation": alternative,
        "needs_staff_review": True,
    }


def generate_risk_assistance(
    student_name: str,
    student_allergies: list[str],
    unsafe_menus: list[str],
    matched_allergies: list[str],
    all_menus: list[str],
) -> dict[str, Any]:
    fallback = build_fallback_risk_assistance(
        student_name=student_name,
        student_allergies=student_allergies,
        unsafe_menus=unsafe_menus,
        matched_allergies=matched_allergies,
        all_menus=all_menus,
    )

    unsafe = _dedupe_keep_order(unsafe_menus)
    if not unsafe:
        return fallback

    cache_key = _json_cache_key(
        {
            "type": "risk",
            "student_name": student_name,
            "student_allergies": student_allergies,
            "unsafe_menus": unsafe_menus,
            "matched_allergies": matched_allergies,
            "all_menus": all_menus,
        }
    )
    cached = _get_cache(_RISK_CACHE, cache_key)
    if cached:
        return cached

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=DEFAULT_RISK_MODEL,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 학교 급식 알레르기 안내 도우미야. "
                        "학생과 교사가 바로 이해할 수 있도록 짧고 분명한 한국어 문장으로 설명해. "
                        "대체 급식 추천은 참고용으로만 제안하고, 반드시 담당자 확인이 필요하다고 명시해."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "student_name": student_name,
                            "student_allergies": student_allergies,
                            "matched_allergies": matched_allergies,
                            "unsafe_menus": unsafe_menus,
                            "all_menus": all_menus,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format={"type": "json_schema", "json_schema": RISK_ASSIST_SCHEMA},
        )
        message = response.choices[0].message
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise AIServiceError(f"AI가 요청을 거절했어: {refusal}")

        parsed = json.loads(message.content or "{}")
        result = {
            "risk_explanation": _safe_str(parsed.get("risk_explanation")).strip() or fallback["risk_explanation"],
            "matched_allergies": _dedupe_keep_order(parsed.get("matched_allergies") or fallback["matched_allergies"]),
            "unsafe_menus": _dedupe_keep_order(parsed.get("unsafe_menus") or fallback["unsafe_menus"]),
            "alternative_recommendation": _safe_str(parsed.get("alternative_recommendation")).strip()
            or fallback["alternative_recommendation"],
            "needs_staff_review": bool(parsed.get("needs_staff_review", True)),
        }
        return _set_cache(_RISK_CACHE, cache_key, result)
    except Exception as exc:
        logger.warning("위험 설명 AI 호출 실패, fallback 사용: %s", exc)
        return _set_cache(_RISK_CACHE, cache_key, fallback)


def build_fallback_safety_plan(
    student_name: str,
    student_number: str,
    student_allergies: list[str],
    unsafe_menus: list[str],
    matched_allergies: list[str],
    all_menus: list[str],
    context: str = "",
) -> dict[str, Any]:
    student_label = student_name or "학생"
    unsafe = _dedupe_keep_order(unsafe_menus)
    matched = _dedupe_keep_order(matched_allergies or student_allergies)
    safe_menus = _safe_menu_candidates(all_menus, unsafe)
    risk_level = "높음" if unsafe else "낮음"

    if unsafe:
        risk_summary = (
            f"{student_label}({student_number or '-'})는 {', '.join(matched) or '등록 알레르기'} 때문에 "
            f"{', '.join(unsafe)} 섭취를 피해야 합니다."
        )
    else:
        risk_summary = (
            f"{student_label}({student_number or '-'})는 현재 메뉴 데이터 기준 직접 충돌은 없지만, "
            "원재료표와 조리 교차접촉 확인이 필요합니다."
        )

    if safe_menus:
        alternative_meals = [
            {
                "name": "오늘 안전 후보 메뉴 중심 대체식",
                "components": ", ".join(safe_menus[:4]),
                "preparation_notes": "기존 배식 도구와 섞이지 않게 별도 집게, 별도 용기, 먼저 담기 순서로 준비합니다.",
                "avoids": matched,
                "reason": "현재 등록된 메뉴 알레르기 코드 기준으로 위험 메뉴에 포함되지 않은 항목입니다.",
                "staff_check": "원재료표, 소스, 육수, 튀김유 공동 사용 여부를 최종 확인합니다.",
            }
        ]
    else:
        alternative_meals = [
            {
                "name": "별도 확인 대체식",
                "components": "흰밥, 개별 포장 과일 또는 학교가 원재료를 확인한 별도 조리 반찬",
                "preparation_notes": "알레르기 유발 식재료와 같은 조리대, 칼, 집게, 튀김유를 사용하지 않습니다.",
                "avoids": matched,
                "reason": "오늘 등록 메뉴 중 안전 후보를 자동으로 확정할 수 없습니다.",
                "staff_check": "영양교사 또는 급식 담당자가 실제 식재료 라벨과 조리 동선을 확인한 뒤 제공합니다.",
            }
        ]

    emergency_steps = [
        {
            "order": 1,
            "title": "섭취 중단",
            "action": "의심 음식 섭취를 즉시 멈추고 남은 음식과 식판을 보관해 원인 확인에 사용합니다.",
            "owner": "현장 교직원",
            "urgency": "즉시",
        },
        {
            "order": 2,
            "title": "증상 확인",
            "action": "호흡곤란, 목 조임, 입술/얼굴 부종, 반복 구토, 어지러움, 전신 두드러기 여부를 확인합니다.",
            "owner": "보건 담당자",
            "urgency": "즉시",
        },
        {
            "order": 3,
            "title": "응급계획 실행",
            "action": "학생 개인 응급계획과 처방약이 있으면 훈련된 담당자가 학교 지침에 따라 즉시 시행합니다. 아나필락시스가 의심되면 119에 연락합니다.",
            "owner": "보건 담당자/관리자",
            "urgency": "즉시",
        },
        {
            "order": 4,
            "title": "연락 및 기록",
            "action": "보호자에게 상황, 섭취 음식, 증상, 조치 시간을 알리고 사고 기록을 남깁니다.",
            "owner": "담임/관리자",
            "urgency": "응급 조치와 병행",
        },
    ]

    return {
        "risk_level": risk_level,
        "risk_summary": risk_summary,
        "alternative_meals": alternative_meals,
        "emergency_steps": emergency_steps,
        "guardian_message": (
            f"{student_label} 학생 급식 알레르기 주의 상황이 확인되어 위험 메뉴 섭취를 제한하고 있습니다. "
            "현재 증상 여부와 학교 조치 내용을 확인해 추가 연락드리겠습니다."
        ),
        "nurse_message": (
            f"{student_label} 학생 알레르기: {', '.join(student_allergies) or '등록 정보 없음'}. "
            f"주의 메뉴: {', '.join(unsafe) or '현재 직접 충돌 없음'}. 증상 확인 및 개인 응급계획 확인이 필요합니다."
        ),
        "kitchen_message": (
            f"{student_label} 학생에게 {', '.join(matched) or '등록 알레르기'} 관련 성분과 교차접촉 가능성이 있는 메뉴를 제외하고 "
            "별도 도구와 별도 용기로 배식해 주세요."
        ),
        "prevention_checklist": [
            "원재료 라벨과 납품서의 알레르기 표시 확인",
            "소스, 육수, 튀김가루, 드레싱의 숨은 성분 확인",
            "공용 집게, 공용 튀김유, 공용 조리대 사용 여부 확인",
            "대체식은 학생 이름을 표시해 일반 배식과 분리",
        ],
        "monitoring_points": [
            "입 주변 가려움, 두드러기, 복통, 구토",
            "기침, 쌕쌕거림, 목 조임, 호흡 불편",
            "어지러움, 창백함, 갑작스러운 무기력",
        ],
        "staff_review_required": True,
    }


def generate_allergy_safety_plan(
    student_name: str,
    student_number: str,
    student_allergies: list[str],
    unsafe_menus: list[str],
    matched_allergies: list[str],
    all_menus: list[str],
    context: str = "",
) -> dict[str, Any]:
    fallback = build_fallback_safety_plan(
        student_name=student_name,
        student_number=student_number,
        student_allergies=student_allergies,
        unsafe_menus=unsafe_menus,
        matched_allergies=matched_allergies,
        all_menus=all_menus,
        context=context,
    )
    cache_key = _json_cache_key(
        {
            "type": "safety_plan",
            "student_name": student_name,
            "student_number": student_number,
            "student_allergies": student_allergies,
            "unsafe_menus": unsafe_menus,
            "matched_allergies": matched_allergies,
            "all_menus": all_menus,
            "context": context,
        }
    )
    cached = _get_cache(_SAFETY_CACHE, cache_key)
    if cached:
        return cached

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=DEFAULT_SAFETY_MODEL,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 학교 급식 알레르기 안전 도우미야. "
                        "대체급식, 사고 발생 시 현장 대응, 보호자/보건교사/급식실 메시지를 짧고 실행 가능하게 작성해. "
                        "의학적 진단이나 약물 용량을 지시하지 말고, 학생 개인 응급계획과 학교 지침, 119/의료진 판단을 우선한다고 써. "
                        "대체급식은 안전 확정 표현을 피하고 원재료표와 교차접촉 확인 필요성을 반드시 포함해."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "student_name": student_name,
                            "student_number": student_number,
                            "student_allergies": student_allergies,
                            "matched_allergies": matched_allergies,
                            "unsafe_menus": unsafe_menus,
                            "all_menus": all_menus,
                            "context": context,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format={"type": "json_schema", "json_schema": SAFETY_PLAN_SCHEMA},
        )
        message = response.choices[0].message
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise AIServiceError(f"AI가 요청을 거절했어: {refusal}")

        parsed = json.loads(message.content or "{}")
        result = _normalize_safety_plan(parsed, fallback)
        return _set_cache(_SAFETY_CACHE, cache_key, result)
    except Exception as exc:
        logger.warning("알레르기 안전계획 AI 호출 실패, fallback 사용: %s", exc)
        return _set_cache(_SAFETY_CACHE, cache_key, fallback)


def _normalize_safety_plan(parsed: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    alternative_meals = []
    for item in parsed.get("alternative_meals") or []:
        alternative_meals.append(
            {
                "name": _safe_str(item.get("name")).strip(),
                "components": _safe_str(item.get("components")).strip(),
                "preparation_notes": _safe_str(item.get("preparation_notes")).strip(),
                "avoids": _dedupe_keep_order(item.get("avoids") or []),
                "reason": _safe_str(item.get("reason")).strip(),
                "staff_check": _safe_str(item.get("staff_check")).strip(),
            }
        )
    alternative_meals = [item for item in alternative_meals if item["name"]] or fallback["alternative_meals"]

    emergency_steps = []
    for idx, item in enumerate(parsed.get("emergency_steps") or [], start=1):
        try:
            order = int(item.get("order") or idx)
        except Exception:
            order = idx
        emergency_steps.append(
            {
                "order": order,
                "title": _safe_str(item.get("title")).strip(),
                "action": _safe_str(item.get("action")).strip(),
                "owner": _safe_str(item.get("owner")).strip(),
                "urgency": _safe_str(item.get("urgency")).strip(),
            }
        )
    emergency_steps = [item for item in emergency_steps if item["title"] and item["action"]] or fallback["emergency_steps"]
    emergency_steps.sort(key=lambda item: item["order"])

    return {
        "risk_level": _safe_str(parsed.get("risk_level")).strip() or fallback["risk_level"],
        "risk_summary": _safe_str(parsed.get("risk_summary")).strip() or fallback["risk_summary"],
        "alternative_meals": alternative_meals,
        "emergency_steps": emergency_steps,
        "guardian_message": _safe_str(parsed.get("guardian_message")).strip() or fallback["guardian_message"],
        "nurse_message": _safe_str(parsed.get("nurse_message")).strip() or fallback["nurse_message"],
        "kitchen_message": _safe_str(parsed.get("kitchen_message")).strip() or fallback["kitchen_message"],
        "prevention_checklist": _dedupe_keep_order(parsed.get("prevention_checklist") or fallback["prevention_checklist"]),
        "monitoring_points": _dedupe_keep_order(parsed.get("monitoring_points") or fallback["monitoring_points"]),
        "staff_review_required": bool(parsed.get("staff_review_required", True)),
    }


def build_fallback_daily_brief(date_value: str, risk_items: list[dict[str, Any]], all_menus: list[str]) -> dict[str, Any]:
    watch_students = []
    for item in risk_items or []:
        unsafe = _dedupe_keep_order(item.get("unsafe_menus") or [])
        allergies = _dedupe_keep_order(item.get("matched_allergies") or item.get("student_allergies") or [])
        watch_students.append(
            {
                "student_name": _safe_str(item.get("student_name")).strip(),
                "student_number": _safe_str(item.get("student_number")).strip(),
                "risk_level": "높음" if unsafe else "낮음",
                "allergies": allergies,
                "unsafe_menus": unsafe,
                "action": (
                    f"{', '.join(unsafe)} 제외 배식과 대체식 확인"
                    if unsafe
                    else "일반 배식 가능 여부를 원재료표 기준으로 확인"
                ),
            }
        )

    if watch_students:
        summary = f"{date_value} 기준 알레르기 주의 학생 {len(watch_students)}명이 확인되었습니다."
    else:
        summary = f"{date_value} 기준 등록 데이터상 직접 충돌 학생은 확인되지 않았습니다."

    return {
        "summary": summary,
        "high_risk_count": len([item for item in watch_students if item["risk_level"] == "높음"]),
        "priority_actions": [
            "급식 시작 전 주의 학생 명단을 담임, 보건실, 급식실이 함께 확인",
            "위험 메뉴와 대체식 후보를 학생별로 분리 표시",
            "배식 도구와 용기 교차접촉 여부 확인",
        ],
        "watch_students": watch_students,
        "kitchen_notes": [
            f"오늘 메뉴: {', '.join(_dedupe_keep_order(all_menus)) or '등록 메뉴 없음'}",
            "소스, 육수, 튀김유, 드레싱은 별도 성분 확인이 필요합니다.",
        ],
        "staff_review_required": True,
    }


def generate_daily_ai_brief(date_value: str, risk_items: list[dict[str, Any]], all_menus: list[str]) -> dict[str, Any]:
    fallback = build_fallback_daily_brief(date_value, risk_items, all_menus)
    cache_key = _json_cache_key(
        {"type": "daily_brief", "date": date_value, "risk_items": risk_items, "all_menus": all_menus}
    )
    cached = _get_cache(_BRIEF_CACHE, cache_key)
    if cached:
        return cached

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=DEFAULT_BRIEF_MODEL,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 학교 급식 알레르기 당일 브리핑 도우미야. "
                        "관리자, 담임, 보건실, 급식실이 바로 실행할 수 있는 우선순위 중심으로 작성해. "
                        "안전 확정 표현은 피하고 담당자 확인 필요성을 포함해."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"date": date_value, "risk_items": risk_items, "all_menus": all_menus},
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format={"type": "json_schema", "json_schema": DAILY_BRIEF_SCHEMA},
        )
        message = response.choices[0].message
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise AIServiceError(f"AI가 요청을 거절했어: {refusal}")

        parsed = json.loads(message.content or "{}")
        result = {
            "summary": _safe_str(parsed.get("summary")).strip() or fallback["summary"],
            "high_risk_count": int(parsed.get("high_risk_count") or fallback["high_risk_count"]),
            "priority_actions": _dedupe_keep_order(parsed.get("priority_actions") or fallback["priority_actions"]),
            "watch_students": parsed.get("watch_students") or fallback["watch_students"],
            "kitchen_notes": _dedupe_keep_order(parsed.get("kitchen_notes") or fallback["kitchen_notes"]),
            "staff_review_required": bool(parsed.get("staff_review_required", True)),
        }
        return _set_cache(_BRIEF_CACHE, cache_key, result)
    except Exception as exc:
        logger.warning("오늘 알레르기 브리핑 AI 호출 실패, fallback 사용: %s", exc)
        return _set_cache(_BRIEF_CACHE, cache_key, fallback)


def build_fallback_menu_allergy_review(menu_rows: list[dict[str, Any]], allergy_dict: dict[str, Any]) -> dict[str, Any]:
    reviewed = []
    warnings = []
    for row in menu_rows or []:
        menu_name = _safe_str(row.get("menu_name")).strip()
        current_codes = _clean_codes(row.get("allergy_codes", []))
        inferred = infer_allergies_from_menu_name(menu_name, allergy_dict)
        missing = [code for code in inferred if code not in current_codes]
        if missing:
            missing_names = ", ".join(_code_name(code, allergy_dict) for code in missing)
            reason = f"메뉴명 기준으로 {missing_names} 포함 가능성이 있어 코드 추가 검토가 필요합니다."
            warnings.append(f"{menu_name}: {missing_names} 코드 검토 필요")
        else:
            reason = "현재 사전 기준으로 뚜렷한 누락 후보를 찾지 못했습니다."

        reviewed.append(
            {
                "menu_name": menu_name,
                "current_codes": current_codes,
                "suspected_missing_codes": missing,
                "confidence": 0.65 if missing else 0.55,
                "review_reason": reason,
            }
        )

    return {"reviewed_menus": reviewed, "warnings": warnings}


def generate_menu_allergy_review(menu_rows: list[dict[str, Any]], allergy_dict: dict[str, Any]) -> dict[str, Any]:
    fallback = build_fallback_menu_allergy_review(menu_rows, allergy_dict)
    cache_key = _json_cache_key({"type": "menu_review", "menu_rows": menu_rows})
    cached = _get_cache(_MENU_REVIEW_CACHE, cache_key)
    if cached:
        return cached

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=DEFAULT_MEAL_MODEL,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 한국 학교 급식 알레르기 코드 점검 도우미야. "
                        "메뉴명과 현재 알레르기 코드를 보고 빠졌을 가능성이 있는 대표 알레르기 번호를 보수적으로 제안해. "
                        "확실하지 않은 경우 confidence를 낮추고 review_reason에 담당자 확인이 필요하다고 써."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "menu_rows": menu_rows,
                            "allergy_catalog": allergy_dict.get("allergies", {}),
                            "menu_hints": allergy_dict.get("menu_hints", [])[:120],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format={"type": "json_schema", "json_schema": MENU_REVIEW_SCHEMA},
        )
        message = response.choices[0].message
        refusal = getattr(message, "refusal", None)
        if refusal:
            raise AIServiceError(f"AI가 요청을 거절했어: {refusal}")

        parsed = json.loads(message.content or "{}")
        reviewed = []
        for item in parsed.get("reviewed_menus") or []:
            menu_name = _safe_str(item.get("menu_name")).strip()
            if not menu_name:
                continue
            reviewed.append(
                {
                    "menu_name": menu_name,
                    "current_codes": _clean_codes(item.get("current_codes", [])),
                    "suspected_missing_codes": _clean_codes(item.get("suspected_missing_codes", [])),
                    "confidence": max(0.0, min(float(item.get("confidence", 0) or 0), 1.0)),
                    "review_reason": _safe_str(item.get("review_reason")).strip(),
                }
            )
        result = {
            "reviewed_menus": reviewed or fallback["reviewed_menus"],
            "warnings": _dedupe_keep_order(parsed.get("warnings") or fallback["warnings"]),
        }
        return _set_cache(_MENU_REVIEW_CACHE, cache_key, result)
    except Exception as exc:
        logger.warning("메뉴 알레르기 코드 점검 AI 호출 실패, fallback 사용: %s", exc)
        return _set_cache(_MENU_REVIEW_CACHE, cache_key, fallback)
