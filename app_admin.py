import os
from pathlib import Path

from flask import redirect, url_for

from admin import app_admin as admin_app_module
from admin.app_admin import app
from admin.v5_admin_renderer import render_admin_page_v5


admin_app_module.render_admin_page = render_admin_page_v5


def _v5_admin_home():
    if admin_app_module.is_logged_in():
        if admin_app_module.is_admin():
            return admin_app_module.render_admin_page(
                "관리자 홈",
                "오늘 급식 안전 상태와 운영 지표를 한눈에 확인해.",
                "admin_home",
            )
        if admin_app_module.is_student():
            return redirect(url_for("student_home_page"))
    return redirect(url_for("login_page"))


app.view_functions["home"] = _v5_admin_home

_PROJECT_ROOT = Path(__file__).resolve().parent
app.static_folder = str(_PROJECT_ROOT / "static")
app.template_folder = str(_PROJECT_ROOT / "templates")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")), debug=False)
