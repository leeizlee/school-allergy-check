import os
import re
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
_ADMIN_SHELL_ENDPOINTS = {
    "student_manage_page",
    "menu_manage_page",
    "lunch_log_page",
    "meal_upload_page",
    "ai_tools_page",
    "trash_page",
}
_TOPBAR_LEFT_RE = re.compile(
    r'<div class="topbar-left">\s*'
    r'<div class="topbar-logo">.*?</div>\s*'
    r'<div class="topbar-title-wrap">\s*'
    r'<div class="page-title">(.*?)</div>\s*'
    r'<div class="page-sub">(.*?)</div>\s*'
    r"</div>\s*</div>",
    re.S,
)


def _rewrite_admin_shell(body):
    if '<div class="layout">' not in body:
        return body

    body = body.replace('<body class="">', '<body class="gt-admin-page light-mode">', 1)
    body = body.replace(
        '<body class="page-lunch-log">',
        '<body class="gt-admin-page light-mode page-lunch-log">',
        1,
    )
    body = body.replace('<div class="layout">', '<div class="gt-layout">', 1)
    body = body.replace(
        '<aside class="sidebar">',
        '<aside class="gt-sidebar" id="adminSidebar" aria-label="Admin navigation">',
        1,
    )
    body = body.replace(
        '<div class="brand">\uad00\ub9ac\uc790</div>',
        '<div class="gt-brand"><span class="gt-brand-mark">A</span><span>\uae09\uc2dd \uc54c\ub808\ub974\uae30 Admin</span></div>',
        1,
    )
    body = body.replace(">\ud559\uc0dd \uba54\ub274<", ">STUDENTS<", 1)
    body = body.replace(">\uae09\uc2dd\uba54\ub274<", ">MEALS<", 1)
    body = body.replace(">\uae30\ud0c0<", ">SYSTEM<", 1)
    body = body.replace('<section class="main">', '<section class="gt-main">', 1)
    body = body.replace('<header class="topbar">', '<header class="gt-topbar">', 1)
    body = body.replace('<div class="topbar-right">', '<div class="gt-topbar-actions">', 1)
    body = body.replace('<main class="content">', '<main class="gt-content">', 1)
    body = body.replace('<section class="panel">', '<section class="gt-panel panel">', 1)
    body = body.replace("let isDarkMode = true;", "let isDarkMode = false;", 1)
    body = body.replace(
        'id="themeToggleBtn" onclick="toggleAdminTheme()">\ud654\uc774\ud2b8\ubaa8\ub4dc</button>',
        'id="themeToggleBtn" onclick="toggleAdminTheme()">\ub2e4\ud06c\ubaa8\ub4dc</button>',
        1,
    )
    body = body.replace(
        '</aside>\n\n    <section class="gt-main">',
        '</aside>\n\n    <div class="gt-backdrop" data-sidebar-close></div>\n\n    <section class="gt-main">',
        1,
    )

    def replace_topbar_left(match):
        title = match.group(1)
        subtitle = match.group(2)
        return (
            '<div class="gt-topbar-left">\n'
            '          <button class="gt-menu-btn" id="adminSidebarToggle" type="button" '
            'aria-label="Open navigation" aria-controls="adminSidebar" aria-expanded="false">&#9776;</button>\n'
            '          <div class="gt-page-heading">\n'
            '            <div class="gt-page-kicker">OVERVIEW</div>\n'
            f'            <div class="gt-page-title">{title}</div>\n'
            f'            <div class="gt-page-sub">{subtitle}</div>\n'
            "          </div>\n"
            "        </div>"
        )

    return _TOPBAR_LEFT_RE.sub(replace_topbar_left, body, count=1)


@app.after_request
def inject_admin_layout_assets(response):
    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("text/html"):
        return response
    if request.endpoint not in _UI_SKIN_ENDPOINTS:
        return response

    body = response.get_data(as_text=True)
    if request.endpoint in _ADMIN_SHELL_ENDPOINTS:
        body = _rewrite_admin_shell(body)
    if "admin_layout_v5.css" not in body and "</head>" in body:
        body = body.replace("</head>", f"  {_UI_SKIN_STYLESHEET}\n</head>", 1)
    if "admin_layout_v5.js" not in body and "</body>" in body:
        body = body.replace("</body>", f"  {_UI_SKIN_SCRIPT}\n</body>", 1)

    response.set_data(body)
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")), debug=False)
