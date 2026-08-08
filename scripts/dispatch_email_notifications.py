import os
import sys

import requests


def main():
    base_url = os.getenv("PUBLIC_ADMIN_URL", "").strip().rstrip("/")
    token = os.getenv("EMAIL_DISPATCH_TOKEN", "").strip()
    if not base_url or not token:
        print("PUBLIC_ADMIN_URL and EMAIL_DISPATCH_TOKEN are required.", file=sys.stderr)
        return 2

    try:
        response = requests.post(
            f"{base_url}/api/notifications/email-dispatch",
            headers={"Authorization": f"Bearer {token}"},
            json={"window_minutes": 6},
            timeout=110,
        )
    except requests.RequestException as exc:
        print(f"Notification dispatch request failed: {exc}", file=sys.stderr)
        return 1

    try:
        payload = response.json()
    except ValueError:
        payload = {"error": response.text[:500]}
    print(
        "Notification dispatch result: "
        f"status={response.status_code} sent={payload.get('sent_count', 0)} "
        f"skipped={payload.get('skipped_count', 0)} failed={payload.get('failed_count', 0)}"
    )
    if not response.ok or payload.get("failed_count", 0):
        print(payload.get("error") or payload.get("failed") or "Dispatch failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
