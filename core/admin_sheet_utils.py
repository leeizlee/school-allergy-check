from __future__ import annotations

import logging
import threading
import time


logger = logging.getLogger(__name__)
_RETRYABLE_READ_STATUS_CODES = {429, 500, 502, 503, 504}
_RETRYABLE_READ_MARKERS = (
    "quota",
    "rate limit",
    "read requests",
    "resource_exhausted",
    "too many requests",
    "timeout",
    "timed out",
    "temporarily unavailable",
)


def _sheet_error_status(exc):
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def _is_retryable_sheet_read_error(exc):
    status = _sheet_error_status(exc)
    if status in _RETRYABLE_READ_STATUS_CODES:
        return True
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in _RETRYABLE_READ_MARKERS)


def _read_with_backoff(operation, *, max_attempts=4):
    last_error = None
    for attempt in range(max(1, int(max_attempts))):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if not _is_retryable_sheet_read_error(exc) or attempt + 1 >= max_attempts:
                raise
            delay = min(2 ** attempt, 8)
            logger.warning("Google Sheets 읽기 제한으로 %.1f초 후 재시도 (%d/%d)", delay, attempt + 1, max_attempts)
            time.sleep(delay)
    raise last_error


def safe_str(value) -> str:
    return "" if value is None else str(value)


def normalize_key(key) -> str:
    text = safe_str(key)
    for bad in ("\ufeff", "\u200b", "\xa0"):
        text = text.replace(bad, "")
    return " ".join(text.strip().lower().split())


def clean_record_keys(record: dict) -> dict:
    cleaned = {}
    for key, value in (record or {}).items():
        cleaned[normalize_key(key)] = value
    return cleaned


def pick_first_value(record: dict, *keys, default=""):
    record = clean_record_keys(record)
    for key in keys:
        normalized = normalize_key(key)
        if normalized in record and safe_str(record.get(normalized)).strip() != "":
            return safe_str(record.get(normalized)).strip()
    return default


def get_sheet_records_raw(ws):
    """Read rows without trusting header normalization inside get_all_records()."""
    values = _read_with_backoff(ws.get_all_values)
    if not values:
        return []

    headers = [normalize_key(header) for header in values[0]]
    records = []

    for row in values[1:]:
        if len(row) < len(headers):
            row = row + [""] * (len(headers) - len(row))

        record = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            record[header] = row[index] if index < len(row) else ""
            record[chr(97 + index)] = row[index] if index < len(row) else ""
        records.append(record)

    return records


class _TTLCache:
    def __init__(self, ttl: float = 8.0):
        self._ttl = ttl
        self._store: dict = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self._store.get(key)
            if entry and (time.monotonic() - entry["ts"]) < self._ttl:
                return entry["value"], True
        return None, False

    def set(self, key, value):
        with self._lock:
            self._store[key] = {"value": value, "ts": time.monotonic()}

    def invalidate(self, key):
        with self._lock:
            self._store.pop(key, None)


_cache = _TTLCache(ttl=8.0)
_cache_load_lock = threading.Lock()


def _sheet_cache_key(ws, kind: str = "records"):
    title = getattr(ws, "title", None) or "sheet"
    spreadsheet_id = getattr(ws, "spreadsheet_id", None)
    if not spreadsheet_id:
        spreadsheet_id = getattr(getattr(ws, "spreadsheet", None), "id", None)
    return f"{kind}::{spreadsheet_id or 'unknown'}::{title}"


def _cached_get_all_records(ws):
    key = _sheet_cache_key(ws, "records")
    value, hit = _cache.get(key)
    if hit:
        return value
    with _cache_load_lock:
        value, hit = _cache.get(key)
        if hit:
            return value
        records = _read_with_backoff(ws.get_all_records)
        _cache.set(key, records)
        return records


def _cached_get_sheet_records_raw(ws):
    key = _sheet_cache_key(ws, "raw")
    value, hit = _cache.get(key)
    if hit:
        return value
    with _cache_load_lock:
        value, hit = _cache.get(key)
        if hit:
            return value
        records = get_sheet_records_raw(ws)
        _cache.set(key, records)
        return records


def _invalidate_sheet_cache(ws):
    _cache.invalidate(_sheet_cache_key(ws, "records"))
    _cache.invalidate(_sheet_cache_key(ws, "raw"))


def normalize_trash(value):
    return "1" if str(value).strip() == "1" else "0"


def find_header_col(ws, header_name):
    headers = _read_with_backoff(lambda: ws.row_values(1))
    for index, header in enumerate(headers, start=1):
        if str(header).strip() == header_name:
            return index
    return None


def update_cell_by_header(ws, row_index, header_name, value):
    col = find_header_col(ws, header_name)
    if col is None:
        raise ValueError(f"Missing header: {header_name}")
    ws.update_cell(row_index, col, value)
    _invalidate_sheet_cache(ws)


def find_header_col_any(ws, header_names):
    for header_name in header_names:
        col = find_header_col(ws, header_name)
        if col is not None:
            return col, header_name
    return None, None


def update_cell_by_headers(ws, row_index, header_names, value):
    col, found = find_header_col_any(ws, header_names)
    if col is None:
        raise ValueError(f"Missing headers: {', '.join(header_names)}")
    ws.update_cell(row_index, col, value)
    _invalidate_sheet_cache(ws)
    return found


def get_record_value(record, *keys, default=""):
    for key in keys:
        if key in record:
            return record.get(key)
    return default


def append_row_by_headers(ws, row_dict, default_value=""):
    headers = [str(value).strip() for value in _read_with_backoff(lambda: ws.row_values(1))]
    row = [row_dict.get(header, default_value) for header in headers]
    ws.append_row(row)
    _invalidate_sheet_cache(ws)


def append_rows_by_headers(ws, row_dicts, default_value=""):
    rows_to_add = list(row_dicts or [])
    if not rows_to_add:
        return
    headers = [str(value).strip() for value in _read_with_backoff(lambda: ws.row_values(1))]
    rows = [[row_dict.get(header, default_value) for header in headers] for row_dict in rows_to_add]
    if hasattr(ws, "append_rows"):
        ws.append_rows(rows)
    else:
        for row in rows:
            ws.append_row(row)
    _invalidate_sheet_cache(ws)


def soft_delete_rows(ws, row_indexes):
    for row_index in row_indexes:
        update_cell_by_header(ws, row_index, "trash", "1")
    _invalidate_sheet_cache(ws)


def restore_rows(ws, row_indexes):
    for row_index in row_indexes:
        update_cell_by_header(ws, row_index, "trash", "0")
    _invalidate_sheet_cache(ws)


def hard_delete_rows(ws, row_indexes):
    for row_index in sorted(row_indexes, reverse=True):
        ws.delete_rows(row_index)
    _invalidate_sheet_cache(ws)
