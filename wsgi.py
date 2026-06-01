from app_admin import app
from admin import v5_runtime_patch  # noqa: F401 - registers v5 runtime routes
from admin import v5_ops_patch  # noqa: F401 - registers operations center routes
from admin import v5_profile_patch  # noqa: F401 - registers profile image storage and crop UI
from admin import v5_enterprise_patch  # noqa: F401 - registers persistence, roles, and AI safety insights
