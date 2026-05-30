import os
from pathlib import Path

from flask import request

from admin.app_admin import app

_PROJECT_ROOT = Path(__file__).resolve().parent
app.static_folder = str(_PROJECT_ROOT / "static")
app.template_folder = str(_PROJECT_ROOT / "templates")

_UI_SKIN_ENDPOINTS = {
    "login_page",
    "kiosk_page",
    "student_home_page",
    "student_manage_page",
    "menu_manage_page",
    "lunch_log_page",
    "meal_upload_page",
    "ai_tools_page",
    "trash_page",
}
_UI_SKIN_STYLESHEET = '<link rel="stylesheet" href="/static/admin_layout_v5.css">'
_UI_SKIN_SCRIPT = '<script src="/static/admin_layout_v5.js" defer></script>'


@app.after_request
def inject_admin_layout_assets(response):
    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("text/html"):
        return response
    if request.endpoint not in _UI_SKIN_ENDPOINTS:
        return response

    body = response.get_data(as_text=True)
    if "admin_layout_v5.css" not in body and "</head>" in body:
        body = body.replace("</head>", f"  {_UI_SKIN_STYLESHEET}\n</head>", 1)
    if "admin_layout_v5.js" not in body and "</body>" in body:
        body = body.replace("</body>", f"  {_UI_SKIN_SCRIPT}\n</body>", 1)

    response.set_data(body)
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")), debug=False)
