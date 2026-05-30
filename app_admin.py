import os
from pathlib import Path

from flask import request

from admin.app_admin import app

_PROJECT_ROOT = Path(__file__).resolve().parent
app.static_folder = str(_PROJECT_ROOT / "static")
app.template_folder = str(_PROJECT_ROOT / "templates")

_ADMIN_LAYOUT_ENDPOINTS = {
    "student_manage_page",
    "menu_manage_page",
    "lunch_log_page",
    "meal_upload_page",
    "ai_tools_page",
    "trash_page",
}
_ADMIN_LAYOUT_STYLESHEET = '<link rel="stylesheet" href="/static/admin_layout_v5.css">'


@app.after_request
def inject_admin_layout_stylesheet(response):
    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("text/html"):
        return response
    if request.endpoint not in _ADMIN_LAYOUT_ENDPOINTS:
        return response

    body = response.get_data(as_text=True)
    if "admin_layout_v5.css" in body or "</head>" not in body:
        return response

    response.set_data(body.replace("</head>", f"  {_ADMIN_LAYOUT_STYLESHEET}\n</head>", 1))
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")), debug=False)
