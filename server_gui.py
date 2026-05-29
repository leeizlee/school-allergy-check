from __future__ import annotations

import json
import os
import traceback
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import messagebox


ROOT = Path(__file__).resolve().parent
RUNTIME_DIR = ROOT / "runtime"
PID_FILE = RUNTIME_DIR / "server_gui_pid.json"
SERVER_LOG = RUNTIME_DIR / "server_gui_server.log"
NGROK_LOG = RUNTIME_DIR / "ngrok.log"
NGROK_URL_FILE = RUNTIME_DIR / "ngrok_url.txt"
LOCAL_SECRETS = ROOT / "config" / "local_secrets.bat"
ADMIN_URL = "http://127.0.0.1:5001"
HEALTH_URL = f"{ADMIN_URL}/health"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


DEFAULT_ENV = {
    "SERVICE_ACCOUNT_JSON": "config\\service_account.json",
    "NGROK_URL_FILE": "runtime\\ngrok_url.txt",
    "FLASK_SECRET_KEY": "",
    "NGROK_AUTHTOKEN": "",
    "KIOSK_SCAN_API_TOKEN": "",
    "DEFAULT_STUDENT_PASSWORD": "",
    "RFID_DASHBOARD_URL": "http://allergy-monitoring.duckdns.org:5000",
    "PUBLIC_ADMIN_URL": "http://allergy-admin.duckdns.org:5001",
    "PYTHONIOENCODING": "utf-8",
}


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(DEFAULT_ENV)
    if LOCAL_SECRETS.exists():
        for raw_line in LOCAL_SECRETS.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line.lower().startswith("set "):
                continue
            value = line[4:].strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            if "=" not in value:
                continue
            key, item = value.split("=", 1)
            env[key.strip()] = item
    return env


def python_executable() -> str:
    current = Path(sys.executable)
    if current.name.lower() == "pythonw.exe":
        python = current.with_name("python.exe")
        if python.exists():
            return str(python)
    return str(current)


def run_hidden(command: list[str], timeout: int = 20, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )


def save_pids(server_pid: int | None = None, ngrok_pid: int | None = None) -> None:
    RUNTIME_DIR.mkdir(exist_ok=True)
    PID_FILE.write_text(
        json.dumps({"server_pid": server_pid, "ngrok_pid": ngrok_pid, "started_at": time.time()}),
        encoding="utf-8",
    )


def load_pids() -> dict[str, int | None]:
    try:
        data = json.loads(PID_FILE.read_text(encoding="utf-8"))
        if "pid" in data:
            return {"server_pid": int(data.get("pid") or 0) or None, "ngrok_pid": None}
        return {
            "server_pid": int(data.get("server_pid") or 0) or None,
            "ngrok_pid": int(data.get("ngrok_pid") or 0) or None,
        }
    except Exception:
        return {"server_pid": None, "ngrok_pid": None}


def clear_pids() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def is_pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    result = run_hidden(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ exit 0 }} else {{ exit 1 }}",
        ],
        timeout=8,
    )
    return result.returncode == 0


def stop_process_tree(pid: int | None) -> None:
    if pid and is_pid_running(pid):
        run_hidden(["taskkill", "/PID", str(pid), "/T", "/F"], timeout=15)


def stop_server_processes() -> None:
    pids = load_pids()
    stop_process_tree(pids.get("server_pid"))
    stop_process_tree(pids.get("ngrok_pid"))
    clear_pids()

    script = r"""
$listeners = Get-NetTCPConnection -LocalPort 5001 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($procId in $listeners) {
  Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}
Get-Process ngrok -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
"""
    run_hidden(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], timeout=20)


def wait_for_ngrok_url(timeout_seconds: int = 30) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=2) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
            tunnels = data.get("tunnels") or []
            https_url = next((item.get("public_url") for item in tunnels if str(item.get("public_url", "")).startswith("https://")), "")
            url = https_url or next((item.get("public_url") for item in tunnels if item.get("public_url")), "")
            if url:
                NGROK_URL_FILE.write_text(url, encoding="ascii", errors="ignore")
                return url
        except Exception:
            time.sleep(1)
    return ""


def start_ngrok(env: dict[str, str]):
    token = (env.get("NGROK_AUTHTOKEN") or "").strip()
    if not token:
        return None
    run_hidden(["ngrok", "config", "add-authtoken", token], timeout=20, env=env)
    ngrok_log = NGROK_LOG.open("a", encoding="utf-8", errors="replace")
    return subprocess.Popen(
        ["ngrok", "http", "5001", "--log=stdout", "--log-format=logfmt"],
        cwd=ROOT,
        env=env,
        stdout=ngrok_log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
    )


def start_flask(env: dict[str, str]):
    server_log = SERVER_LOG.open("a", encoding="utf-8", errors="replace")
    return subprocess.Popen(
        [python_executable(), "app_admin.py"],
        cwd=ROOT,
        env=env,
        stdout=server_log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
    )


def start_server_processes() -> tuple[int, int | None]:
    RUNTIME_DIR.mkdir(exist_ok=True)
    NGROK_URL_FILE.unlink(missing_ok=True)
    env = build_env()
    ngrok_proc = start_ngrok(env)
    server_proc = start_flask(env)
    save_pids(server_proc.pid, ngrok_proc.pid if ngrok_proc else None)
    if ngrok_proc:
        threading.Thread(target=wait_for_ngrok_url, daemon=True).start()
    return server_proc.pid, ngrok_proc.pid if ngrok_proc else None


def wait_for_server_ready(timeout_seconds: int = 90) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=2) as response:
                if 200 <= response.status < 500:
                    return True
        except Exception:
            time.sleep(1)
    return False


class ServerGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("SERVER CONTROL")
        self.geometry("300x270")
        self.resizable(False, False)
        self.configure(bg="#181b20")

        self.status_var = tk.StringVar(value="WAITING")
        self.busy = False

        tk.Label(
            self,
            text="ADMIN SERVER",
            font=("Segoe UI", 15, "bold"),
            fg="#f1f5f9",
            bg="#181b20",
        ).pack(pady=(22, 6))

        tk.Label(
            self,
            textvariable=self.status_var,
            font=("Segoe UI", 10),
            fg="#9aa4b2",
            bg="#181b20",
        ).pack(pady=(0, 16))

        btn_frame = tk.Frame(self, bg="#181b20")
        btn_frame.pack()

        self.start_btn = self.make_button(btn_frame, "START", self.start_server, "#f3f4f6", "#111827")
        self.restart_btn = self.make_button(btn_frame, "RESTART", self.restart_server, "#2a2f37", "#f1f5f9")
        self.stop_btn = self.make_button(btn_frame, "STOP SERVER", self.stop_server, "#3a1f24", "#fca5a5")
        self.exit_btn = self.make_button(btn_frame, "EXIT", self.destroy, "#222831", "#d1d5db")

        self.start_btn.grid(row=0, column=0, padx=5, pady=5)
        self.restart_btn.grid(row=0, column=1, padx=5, pady=5)
        self.stop_btn.grid(row=1, column=0, columnspan=2, padx=5, pady=6, sticky="ew")
        self.exit_btn.grid(row=2, column=0, columnspan=2, padx=5, pady=0, sticky="ew")

        tk.Label(
            self,
            text=ADMIN_URL,
            font=("Segoe UI", 9),
            fg="#60a5fa",
            bg="#181b20",
        ).pack(pady=(14, 0))

        self.refresh_status()
        self.after(2000, self.monitor_status)

    def make_button(self, parent, text, command, bg, fg):
        return tk.Button(
            parent,
            text=text,
            command=command,
            width=12,
            height=2,
            font=("Segoe UI", 10, "bold"),
            bg=bg,
            fg=fg,
            activebackground=bg,
            activeforeground=fg,
            relief="flat",
            bd=0,
            cursor="hand2",
        )

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.start_btn.config(state=state)
        self.restart_btn.config(state=state)
        self.stop_btn.config(state=state)
        self.update_idletasks()

    def refresh_status(self) -> None:
        pids = load_pids()
        if wait_for_server_ready(timeout_seconds=1):
            self.status_var.set("SERVER RUNNING")
        elif is_pid_running(pids.get("server_pid")):
            self.status_var.set("LOADING...")
        else:
            clear_pids()
            self.status_var.set("WAITING")

    def monitor_status(self) -> None:
        if not self.busy:
            self.refresh_status()
        self.after(2000, self.monitor_status)

    def start_server(self) -> None:
        self.set_busy(True)
        self.status_var.set("LOADING...")
        threading.Thread(target=self._start_server_worker, daemon=True).start()

    def _start_server_worker(self) -> None:
        try:
            pids = load_pids()
            if is_pid_running(pids.get("server_pid")) and wait_for_server_ready(timeout_seconds=3):
                self.after(0, lambda: self.status_var.set("SERVER RUNNING"))
                return
            if pids.get("server_pid") and not is_pid_running(pids.get("server_pid")):
                clear_pids()
            start_server_processes()
            ready = wait_for_server_ready()
            self.after(0, lambda: self.status_var.set("SERVER RUNNING" if ready else "START CHECK FAILED"))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("START FAILED", str(exc)))
            self.after(0, lambda: self.status_var.set("START FAILED"))
        finally:
            self.after(0, lambda: self.set_busy(False))

    def stop_server(self) -> None:
        self.set_busy(True)
        try:
            stop_server_processes()
            self.status_var.set("STOPPED")
        except Exception as exc:
            messagebox.showerror("STOP FAILED", str(exc))
            self.status_var.set("STOP FAILED")
        finally:
            self.set_busy(False)

    def restart_server(self) -> None:
        self.set_busy(True)
        self.status_var.set("LOADING...")
        threading.Thread(target=self._restart_server_worker, daemon=True).start()

    def _restart_server_worker(self) -> None:
        try:
            stop_server_processes()
            time.sleep(1)
            start_server_processes()
            ready = wait_for_server_ready()
            self.after(0, lambda: self.status_var.set("SERVER RUNNING" if ready else "RESTART CHECK FAILED"))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("RESTART FAILED", str(exc)))
            self.after(0, lambda: self.status_var.set("RESTART FAILED"))
        finally:
            self.after(0, lambda: self.set_busy(False))


if __name__ == "__main__":
    try:
        if sys.platform != "win32":
            raise SystemExit("Windows only.")
        app = ServerGui()
        app.mainloop()
    except Exception:
        RUNTIME_DIR.mkdir(exist_ok=True)
        (RUNTIME_DIR / "server_gui_error.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise
