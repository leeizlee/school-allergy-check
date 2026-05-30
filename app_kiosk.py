import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
os.environ.setdefault("NGROK_URL_FILE", str(_PROJECT_ROOT / "runtime" / "ngrok_url.txt"))

from kiosk.app_kiosk import *  # noqa: F401,F403,E402


if __name__ == "__main__":
    main()
