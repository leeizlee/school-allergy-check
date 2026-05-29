import base64
import json
import os
import sys
from datetime import datetime, timezone
from urllib import error, request

NGROK_API = os.getenv("NGROK_API", "http://127.0.0.1:4040/api/tunnels")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
GITHUB_FILE_PATH = os.getenv("GITHUB_FILE_PATH", "index.html").strip()
GITHUB_DISCOVERY_FILE_PATH = os.getenv("GITHUB_DISCOVERY_FILE_PATH", "latest-url.json").strip()
SITE_TITLE = os.getenv("SITE_TITLE", "Allergy Monitoring Redirect").strip()
SHOW_MESSAGE = os.getenv("SHOW_MESSAGE", "Moving to current server...").strip()
API_VERSION = "2022-11-28"
RUNTIME_URL_FILE = os.getenv("NGROK_URL_FILE", "runtime/ngrok_url.txt").strip()


def http_json(url, method="GET", headers=None, data=None):
    req = request.Request(url, method=method)
    headers = headers or {}
    for key, value in headers.items():
        req.add_header(key, value)
    if data is not None:
        if isinstance(data, str):
            data = data.encode("utf-8")
        req.data = data
    with request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}


def get_ngrok_url():
    try:
        data = http_json(NGROK_API)
        tunnels = data.get("tunnels", [])
        https_urls = [t.get("public_url", "") for t in tunnels if t.get("public_url", "").startswith("https://")]
        if https_urls:
            return https_urls[0]
    except Exception:
        pass

    if RUNTIME_URL_FILE and os.path.exists(RUNTIME_URL_FILE):
        saved_url = open(RUNTIME_URL_FILE, "r", encoding="utf-8").read().strip()
        if saved_url:
            return saved_url

    raise RuntimeError("No active HTTPS ngrok tunnel was found, and no saved ngrok_url.txt fallback exists.")


def github_headers():
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN environment variable is empty.")
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "ngrok-github-pages-updater",
    }


def build_html(redirect_url):
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url={redirect_url}">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{SITE_TITLE}</title>
  <script>
    window.location.replace({json.dumps(redirect_url)});
  </script>
  <style>
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: #0f1115;
      color: #f5f7fb;
      font-family: system-ui, sans-serif;
    }}
    .box {{
      width: min(640px, 92vw);
      background: #181c23;
      border: 1px solid #2a3140;
      border-radius: 20px;
      padding: 28px;
      box-shadow: 0 18px 48px rgba(0,0,0,.28);
    }}
    a {{ color: #8ab4ff; word-break: break-all; }}
    .muted {{ color: #aab4c3; margin-top: 10px; }}
  </style>
</head>
<body>
  <div class="box">
    <h1>{SITE_TITLE}</h1>
    <p>{SHOW_MESSAGE}</p>
    <p class="muted">If automatic redirect does not work, open the link below.</p>
    <p><a href="{redirect_url}">{redirect_url}</a></p>
  </div>
</body>
</html>"""


def build_discovery_payload(redirect_url):
    return json.dumps(
        {
            "public_url": redirect_url,
            "admin_server_url": redirect_url,
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "ngrok",
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def get_existing_sha(file_path):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{file_path}?ref={GITHUB_BRANCH}"
    try:
        data = http_json(url, headers=github_headers())
        return data.get("sha")
    except error.HTTPError as exc:
        if exc.code == 404:
            return None
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GitHub lookup failed: HTTP {exc.code} {body}")


def update_github_file(file_path, content_text, message):
    sha = get_existing_sha(file_path)
    api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{file_path}"
    payload = {
        "message": message,
        "content": base64.b64encode(content_text.encode("utf-8")).decode("ascii"),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    try:
        return http_json(
            api_url,
            method="PUT",
            headers={**github_headers(), "Content-Type": "application/json"},
            data=json.dumps(payload),
        )
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GitHub update failed: HTTP {exc.code} {body}")


def main():
    required = {
        "GITHUB_OWNER": GITHUB_OWNER,
        "GITHUB_REPO": GITHUB_REPO,
        "GITHUB_BRANCH": GITHUB_BRANCH,
        "GITHUB_FILE_PATH": GITHUB_FILE_PATH,
        "GITHUB_DISCOVERY_FILE_PATH": GITHUB_DISCOVERY_FILE_PATH,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))

    ngrok_url = get_ngrok_url()
    html = build_html(ngrok_url)
    discovery_payload = build_discovery_payload(ngrok_url)

    update_github_file(
        GITHUB_FILE_PATH,
        html,
        "Update GitHub Pages redirect to current ngrok URL",
    )
    update_github_file(
        GITHUB_DISCOVERY_FILE_PATH,
        discovery_payload,
        "Update GitHub Pages discovery JSON to current ngrok URL",
    )

    pages_url = f"https://{GITHUB_OWNER}.github.io/{GITHUB_REPO}/"
    discovery_url = f"{pages_url}{GITHUB_DISCOVERY_FILE_PATH}"
    print("Current ngrok URL:", ngrok_url)
    print("Updated Pages URL:", pages_url)
    print("Updated discovery URL:", discovery_url)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Error:", exc)
        sys.exit(1)
