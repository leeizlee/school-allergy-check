from admin import v5_enterprise_patch as enterprise


_original_ensure_ops_sheet = enterprise._ensure_ops_sheet


def _safe_ensure_ops_sheet(title, headers):
    try:
        return _original_ensure_ops_sheet(title, headers)
    except Exception:
        return None


enterprise._ensure_ops_sheet = _safe_ensure_ops_sheet
