from pathlib import Path


path = Path("admin/app_admin.py")
text = path.read_text(encoding="utf-8-sig")


def replace_once(old, new, label):
    global text
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"{label} anchor not found")
    text = text.replace(old, new, 1)


replace_once(
    '''            "notification_time": safe_str(r.get("notification_time")).strip() or "07:30",
            "trash": trash,
''',
    '''            "notification_time": safe_str(r.get("notification_time")).strip() or "07:30",
            "email_last_sent_date": safe_str(r.get("email_last_sent_date")).strip(),
            "trash": trash,
''',
    "last sent login field",
)

old_dispatch_setup = '''    target_time = safe_str(data.get("time")).strip() or local_now.strftime("%H:%M")
    date_value = compact_date_value(data.get("date")) or local_now.strftime("%Y%m%d")
    if not re.fullmatch(r"(?:[01]\\d|2[0-3]):[0-5]\\d", target_time):
        return jsonify({"ok": False, "error": "발송 시간 형식은 HH:MM이어야 해"}), 400

    sent = []
'''
new_dispatch_setup = '''    requested_time = safe_str(data.get("time")).strip()
    date_value = compact_date_value(data.get("date")) or local_now.strftime("%Y%m%d")
    try:
        window_minutes = max(1, min(int(data.get("window_minutes", 6)), 15))
    except Exception:
        window_minutes = 6

    if requested_time and not re.fullmatch(r"(?:[01]\\d|2[0-3]):[0-5]\\d", requested_time):
        return jsonify({"ok": False, "error": "발송 시간 형식은 HH:MM이어야 해"}), 400

    current_minutes = local_now.hour * 60 + local_now.minute

    def account_is_due(account):
        notification_time = safe_str(account.get("notification_time")).strip()
        if not re.fullmatch(r"(?:[01]\\d|2[0-3]):[0-5]\\d", notification_time):
            return False
        if requested_time:
            return notification_time == requested_time
        hour, minute = [int(value) for value in notification_time.split(":", 1)]
        scheduled_minutes = hour * 60 + minute
        elapsed = current_minutes - scheduled_minutes
        return 0 <= elapsed < window_minutes

    sent = []
'''
replace_once(old_dispatch_setup, new_dispatch_setup, "dispatch window setup")

replace_once(
    '''        if safe_str(account.get("notification_time")).strip() != target_time:
            continue

        recipient = safe_str(account.get("email")).strip()
''',
    '''        if not account_is_due(account):
            continue
        if safe_str(account.get("email_last_sent_date")).strip() == date_value:
            skipped.append({"id": account.get("id"), "reason": "오늘 이미 발송됨"})
            continue

        recipient = safe_str(account.get("email")).strip()
''',
    "dispatch due and duplicate check",
)

replace_once(
    '''            sent.append({
                "id": account.get("id"),
                "email": recipient,
                "email_id": email_id,
                "status": message.get("status"),
            })
''',
    '''            update_cell_by_header_create(id_ws, account["row_index"], "email_last_sent_date", date_value)
            sent.append({
                "id": account.get("id"),
                "email": recipient,
                "email_id": email_id,
                "status": message.get("status"),
            })
''',
    "record successful dispatch date",
)

replace_once(
    '''        "date": date_value,
        "time": target_time,
        "sent_count": len(sent),
''',
    '''        "date": date_value,
        "time": requested_time or local_now.strftime("%H:%M"),
        "window_minutes": window_minutes,
        "sent_count": len(sent),
''',
    "dispatch response window",
)

path.write_text(text, encoding="utf-8")
print("Scheduled email dispatch applied")
