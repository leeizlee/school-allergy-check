import os
from pathlib import Path

from admin import app_admin as admin_app_module
from admin.app_admin import app
from admin.v5_admin_renderer import render_admin_page_v5


admin_app_module.render_admin_page = render_admin_page_v5

_PROJECT_ROOT = Path(__file__).resolve().parent
app.static_folder = str(_PROJECT_ROOT / "static")
app.template_folder = str(_PROJECT_ROOT / "templates")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")), debug=False)
