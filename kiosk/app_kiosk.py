#!/usr/bin/env python3
import json
import os
import queue
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

import requests


APP_DIR = Path(__file__).resolve().parent

# lgpio creates a .lgd-nfy* notification pipe in the current working directory
# during import. Use a writable temp directory so systemd or root-based launches
# do not fail with FileNotFoundError: '.lgd-nfy-*'.
os.chdir(tempfile.gettempdir())

try:
    import lgpio
except Exception as exc:
    lgpio = None
    LGPIO_IMPORT_ERROR = exc
else:
    LGPIO_IMPORT_ERROR = None

try:
    import spidev
except Exception as exc:
    spidev = None
    SPIDEV_IMPORT_ERROR = exc
else:
    SPIDEV_IMPORT_ERROR = None


# =============================
# Configuration
# =============================
DEFAULT_ADMIN_SERVER_LOCAL = os.getenv(
    "DEFAULT_ADMIN_SERVER_LOCAL",
    "http://192.168.0.182:5001",
).strip() or "http://192.168.0.182:5001"
DEFAULT_ADMIN_SERVER_DISCOVERY_URL = (
    "https://leeizlee.github.io/school-allergy-check/latest-url.json"
)

SERVER_BASE_URL_ENV = os.getenv("SERVER_BASE_URL", "").strip().rstrip("/")
ADMIN_SERVER_ENV = os.getenv("ADMIN_SERVER_URL", "").strip().rstrip("/")
API_PATH = os.getenv("API_PATH", "/api/kiosk/scan").strip() or "/api/kiosk/scan"
if not API_PATH.startswith("/"):
    API_PATH = "/" + API_PATH

NGROK_URL_FILE = Path(os.getenv("NGROK_URL_FILE", "runtime/ngrok_url.txt"))
if not NGROK_URL_FILE.is_absolute():
    NGROK_URL_FILE = APP_DIR / NGROK_URL_FILE

ADMIN_SERVER_DISCOVERY_URL = os.getenv(
    "ADMIN_SERVER_DISCOVERY_URL",
    DEFAULT_ADMIN_SERVER_DISCOVERY_URL,
).strip()
DISCOVERY_GITHUB_OWNER = os.getenv("GITHUB_OWNER", "leeizlee").strip()
DISCOVERY_GITHUB_REPO = os.getenv("GITHUB_REPO", "school-allergy-check").strip()
ADMIN_SERVER_DISCOVERY_FILE = os.getenv(
    "ADMIN_SERVER_DISCOVERY_FILE",
    "latest-url.json",
).strip()

KIOSK_SCAN_API_TOKEN = os.getenv("KIOSK_SCAN_API_TOKEN", "").strip()
if not KIOSK_SCAN_API_TOKEN:
    print("[WARN] KIOSK_SCAN_API_TOKEN is not set. The admin server may reject scans.")
DEVICE_NAME = os.getenv("DEVICE_NAME", "raspberrypi-rfid-01").strip()
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "6"))
DISCOVERY_REQUEST_TIMEOUT = float(os.getenv("DISCOVERY_REQUEST_TIMEOUT", "3"))
DISCOVERY_REFRESH_SECONDS = float(os.getenv("DISCOVERY_REFRESH_SECONDS", "30"))
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "0.08"))
RFID_DEDUP_SECONDS = float(os.getenv("RFID_DEDUP_SECONDS", "1.5"))
POST_SCAN_DELAY = float(os.getenv("POST_SCAN_DELAY", "0.5"))
SEND_TO_SERVER = os.getenv("SEND_TO_SERVER", "1").strip() != "0"
USE_SERVER_RESPONSE = os.getenv("USE_SERVER_RESPONSE", "1").strip() != "0"
VERBOSE_LOGS = os.getenv("VERBOSE_LOGS", "0").strip() == "1"
ENABLE_LOCAL_GUI = os.getenv("ENABLE_LOCAL_GUI", "1").strip() != "0"

RED_PIN = int(os.getenv("RED_PIN", "17"))
GREEN_PIN = int(os.getenv("GREEN_PIN", "27"))
BLUE_PIN = int(os.getenv("BLUE_PIN", "22"))
BUZZER_PIN = int(os.getenv("BUZZER_PIN", "23"))
RST_PIN = int(os.getenv("RST_PIN", "25"))

DATE_FORMAT = "%Y%m%d"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
WRONG_READ = "WRONG_READ"

SERVER_REQUEST_HEADERS = {
    "ngrok-skip-browser-warning": "true",
}

_DISCOVERY_LAST_URL = ""
_DISCOVERY_LAST_CHECK_AT = 0.0
SERVER_BASE_URL = ""

lock = threading.Lock()
GUI_EVENT_QUEUE = queue.Queue()
SCAN_STOP_EVENT = threading.Event()

last_scan = {
    "uid": None,
    "name": None,
    "status": "대기중",
    "reason": "",
    "menu_date": None,
    "menu_name": None,
    "student_number": "",
    "scanned_at": None,
}

rfid_state = {
    "mode": "대기",
    "last_uid": None,
    "last_read_at": None,
    "last_error": "",
}


def log_debug(*args):
    if VERBOSE_LOGS:
        print(*args)


def now_date() -> str:
    return datetime.now().strftime(DATE_FORMAT)


def now_time() -> str:
    return datetime.now().strftime(TIME_FORMAT)


def print_scan_summary(rfid_id, status, reason):
    print("------")
    print("rfid id:", rfid_id)
    print("status:", status)
    print("reason:", reason)
    print("------")
    print("ready for next scan")


def publish_gui_event(kind: str, **payload) -> None:
    if not ENABLE_LOCAL_GUI:
        return
    GUI_EVENT_QUEUE.put({"kind": kind, **payload})


def publish_gui_ready(message: str = "Place a card near the reader.") -> None:
    publish_gui_event(
        "ready",
        title="Scan RFID Card",
        message=message,
    )


def publish_gui_scan(uid_text: str, result=None, uid_hyphen="", read_warning="") -> None:
    scan = {}
    if isinstance(result, dict):
        scan = result.get("scan") or {}
        if not isinstance(scan, dict):
            scan = {}

    if not SEND_TO_SERVER:
        server_text = "Not sent"
    elif result is None:
        server_text = "Waiting"
    elif result.get("ok"):
        server_text = "Response received"
    else:
        server_text = "Send failed"

    note = read_warning or ""
    if not note:
        note = "Scan data updated." if result is None else "Scan data sent to server."

    publish_gui_event(
        "scan",
        title="RFID Scan Info",
        uid=uid_text or "-",
        uid_hyphen=uid_hyphen or "-",
        scanned_at=now_time(),
        server=server_text,
        name=str(scan.get("name") or "-"),
        student_number=str(scan.get("student_number") or "-"),
        menu_date=str(scan.get("menu_date") or scan.get("date") or "-"),
        menu_name=str(scan.get("menu_name") or "-"),
        note=note,
    )


class LEDBuzzer:
    def __init__(
        self,
        chip,
        red_pin=RED_PIN,
        green_pin=GREEN_PIN,
        blue_pin=BLUE_PIN,
        buzzer_pin=BUZZER_PIN,
    ):
        self.chip = chip
        self.red_pin = red_pin
        self.green_pin = green_pin
        self.blue_pin = blue_pin
        self.buzzer_pin = buzzer_pin

        for pin in (self.red_pin, self.green_pin, self.blue_pin, self.buzzer_pin):
            lgpio.gpio_claim_output(self.chip, pin)

        self.all_off()

    def _write(self, red=0, green=0, blue=0, buzzer=0):
        lgpio.gpio_write(self.chip, self.red_pin, red)
        lgpio.gpio_write(self.chip, self.green_pin, green)
        lgpio.gpio_write(self.chip, self.blue_pin, blue)
        lgpio.gpio_write(self.chip, self.buzzer_pin, buzzer)

    def all_off(self):
        self._write(0, 0, 0, 0)

    def green_signal(self):
        log_debug("LED decision: green only, buzzer OFF")
        self._write(red=0, green=1, blue=0, buzzer=0)

    def red_signal(self):
        log_debug("LED decision: red only, buzzer OFF")
        self._write(red=1, green=0, blue=0, buzzer=0)

    def red_with_buzzer_signal(self, repeat=3, on_seconds=0.18, off_seconds=0.18):
        log_debug("LED decision: red blinking with buzzer, then red stays ON")
        for _ in range(repeat):
            self._write(red=1, green=0, blue=0, buzzer=1)
            time.sleep(on_seconds)
            self.all_off()
            time.sleep(off_seconds)
        self._write(red=1, green=0, blue=0, buzzer=0)


class RC522:
    MAX_LEN = 16

    PCD_IDLE = 0x00
    PCD_AUTHENT = 0x0E
    PCD_RECEIVE = 0x08
    PCD_TRANSMIT = 0x04
    PCD_TRANSCEIVE = 0x0C
    PCD_RESETPHASE = 0x0F
    PCD_CALCCRC = 0x03

    PICC_REQIDL = 0x26
    PICC_REQALL = 0x52
    PICC_ANTICOLL = 0x93
    PICC_SELECTTAG = 0x93
    PICC_HALT = 0x50

    MI_OK = 0
    MI_NOTAGERR = 1
    MI_ERR = 2

    CommandReg = 0x01
    CommIEnReg = 0x02
    DivIEnReg = 0x03
    CommIrqReg = 0x04
    DivIrqReg = 0x05
    ErrorReg = 0x06
    Status2Reg = 0x08
    FIFODataReg = 0x09
    FIFOLevelReg = 0x0A
    ControlReg = 0x0C
    BitFramingReg = 0x0D
    ModeReg = 0x11
    TxModeReg = 0x12
    RxModeReg = 0x13
    TxControlReg = 0x14
    TModeReg = 0x2A
    TPrescalerReg = 0x2B
    TReloadRegH = 0x2C
    TReloadRegL = 0x2D
    CRCResultRegM = 0x21
    CRCResultRegL = 0x22
    TxASKReg = 0x15
    RFCfgReg = 0x26

    def __init__(self, chip=None, bus=0, device=0, rst_pin=RST_PIN):
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = 100000
        self.spi.mode = 0

        self.rst_pin = rst_pin
        self.owns_gpio = chip is None
        self.gpio = chip if chip is not None else lgpio.gpiochip_open(0)
        self.last_read_error = ""
        lgpio.gpio_claim_output(self.gpio, self.rst_pin)

        self.reset()
        self.init()

    def write_reg(self, reg, value):
        self.spi.xfer2([(reg << 1) & 0x7E, value])

    def read_reg(self, reg):
        value = self.spi.xfer2([((reg << 1) & 0x7E) | 0x80, 0])
        return value[1]

    def set_bit_mask(self, reg, mask):
        tmp = self.read_reg(reg)
        self.write_reg(reg, tmp | mask)

    def clear_bit_mask(self, reg, mask):
        tmp = self.read_reg(reg)
        self.write_reg(reg, tmp & (~mask))

    def reset(self):
        lgpio.gpio_write(self.gpio, self.rst_pin, 0)
        time.sleep(0.05)
        lgpio.gpio_write(self.gpio, self.rst_pin, 1)
        time.sleep(0.05)
        self.write_reg(self.CommandReg, self.PCD_RESETPHASE)

    def antenna_on(self):
        temp = self.read_reg(self.TxControlReg)
        if not (temp & 0x03):
            self.set_bit_mask(self.TxControlReg, 0x03)

    def antenna_off(self):
        self.clear_bit_mask(self.TxControlReg, 0x03)

    def init(self):
        self.write_reg(self.CommandReg, self.PCD_RESETPHASE)
        time.sleep(0.05)

        self.write_reg(self.TModeReg, 0x8D)
        self.write_reg(self.TPrescalerReg, 0x3E)
        self.write_reg(self.TReloadRegL, 30)
        self.write_reg(self.TReloadRegH, 0)

        self.write_reg(self.TxModeReg, 0x00)
        self.write_reg(self.RxModeReg, 0x00)
        self.write_reg(self.ModeReg, 0x3D)

        self.write_reg(self.TxASKReg, 0x40)
        self.write_reg(self.RFCfgReg, 0x70)

        self.antenna_off()
        time.sleep(0.05)
        self.antenna_on()
        time.sleep(0.05)

    def to_card(self, command, send_data):
        back_data = []
        back_len = 0
        status = self.MI_ERR

        irq_en = 0x00
        wait_irq = 0x00

        if command == self.PCD_AUTHENT:
            irq_en = 0x12
            wait_irq = 0x10

        if command == self.PCD_TRANSCEIVE:
            irq_en = 0x77
            wait_irq = 0x30

        self.write_reg(self.CommIEnReg, irq_en | 0x80)
        self.clear_bit_mask(self.CommIrqReg, 0x80)
        self.set_bit_mask(self.FIFOLevelReg, 0x80)

        self.write_reg(self.CommandReg, self.PCD_IDLE)

        for data in send_data:
            self.write_reg(self.FIFODataReg, data)

        self.write_reg(self.CommandReg, command)

        if command == self.PCD_TRANSCEIVE:
            self.set_bit_mask(self.BitFramingReg, 0x80)

        i = 2000
        while True:
            n = self.read_reg(self.CommIrqReg)
            i -= 1
            if not ((i != 0) and not (n & 0x01) and not (n & wait_irq)):
                break

        self.clear_bit_mask(self.BitFramingReg, 0x80)

        if i != 0:
            if (self.read_reg(self.ErrorReg) & 0x1B) == 0x00:
                status = self.MI_OK

                if n & irq_en & 0x01:
                    status = self.MI_NOTAGERR

                if command == self.PCD_TRANSCEIVE:
                    n = self.read_reg(self.FIFOLevelReg)
                    last_bits = self.read_reg(self.ControlReg) & 0x07

                    if last_bits != 0:
                        back_len = (n - 1) * 8 + last_bits
                    else:
                        back_len = n * 8

                    if n == 0:
                        n = 1

                    if n > self.MAX_LEN:
                        n = self.MAX_LEN

                    for _ in range(n):
                        back_data.append(self.read_reg(self.FIFODataReg))
            else:
                status = self.MI_ERR

        return status, back_data, back_len

    def request(self, req_mode):
        self.write_reg(self.BitFramingReg, 0x07)

        status, _, back_bits = self.to_card(
            self.PCD_TRANSCEIVE,
            [req_mode],
        )

        if status != self.MI_OK or back_bits != 0x10:
            status = self.MI_ERR

        return status, back_bits

    def anticoll(self):
        serial_number = []

        self.write_reg(self.BitFramingReg, 0x00)

        serial_number_check = 0
        serial_number.append(self.PICC_ANTICOLL)
        serial_number.append(0x20)

        status, back_data, _ = self.to_card(
            self.PCD_TRANSCEIVE,
            serial_number,
        )

        if status == self.MI_OK and len(back_data) == 5:
            for i in range(4):
                serial_number_check ^= back_data[i]

            if serial_number_check != back_data[4]:
                status = self.MI_ERR

        return status, back_data

    def calculate_crc(self, data):
        self.clear_bit_mask(self.DivIrqReg, 0x04)
        self.set_bit_mask(self.FIFOLevelReg, 0x80)

        for item in data:
            self.write_reg(self.FIFODataReg, item)

        self.write_reg(self.CommandReg, self.PCD_CALCCRC)

        i = 255
        while True:
            n = self.read_reg(self.DivIrqReg)
            i -= 1
            if not ((i != 0) and not (n & 0x04)):
                break

        return [
            self.read_reg(self.CRCResultRegL),
            self.read_reg(self.CRCResultRegM),
        ]

    def select_tag(self, serial_number):
        buffer = [
            self.PICC_SELECTTAG,
            0x70,
        ]

        for i in range(5):
            buffer.append(serial_number[i])

        crc = self.calculate_crc(buffer)
        buffer.append(crc[0])
        buffer.append(crc[1])

        status, _, back_len = self.to_card(
            self.PCD_TRANSCEIVE,
            buffer,
        )

        return status == self.MI_OK and back_len == 0x18

    def read_uid(self):
        self.last_read_error = ""
        status, _ = self.request(self.PICC_REQIDL)

        if status != self.MI_OK:
            return None

        status, uid = self.anticoll()

        if status != self.MI_OK:
            self.last_read_error = "anticoll failed"
            log_debug("RFID read warning: anticoll failed", uid)
            if len(uid) >= 4:
                return uid[:4]
            return WRONG_READ

        if len(uid) != 5:
            self.last_read_error = f"invalid UID length: {len(uid)}"
            log_debug("RFID read warning:", self.last_read_error, uid)
            if len(uid) >= 4:
                return uid[:4]
            return WRONG_READ

        if not self.select_tag(uid):
            self.last_read_error = "select_tag failed"
            log_debug("RFID read warning: select_tag failed", uid)
            if len(uid) >= 4:
                return uid[:4]
            return WRONG_READ

        return uid[:4]

    def close(self):
        try:
            self.antenna_off()
        except Exception as exc:
            log_debug("RC522 antenna off failed:", exc)

        try:
            self.spi.close()
        except Exception as exc:
            log_debug("SPI close failed:", exc)

        if self.owns_gpio:
            try:
                lgpio.gpiochip_close(self.gpio)
            except Exception as exc:
                log_debug("GPIO chip close failed:", exc)


def build_discovery_url() -> str:
    if ADMIN_SERVER_DISCOVERY_URL:
        return ADMIN_SERVER_DISCOVERY_URL
    if DISCOVERY_GITHUB_OWNER and DISCOVERY_GITHUB_REPO and ADMIN_SERVER_DISCOVERY_FILE:
        return (
            f"https://{DISCOVERY_GITHUB_OWNER}.github.io/"
            f"{DISCOVERY_GITHUB_REPO}/{ADMIN_SERVER_DISCOVERY_FILE}"
        )
    return ""


def fetch_server_base_url_from_discovery() -> str:
    discovery_url = build_discovery_url()
    if not discovery_url:
        return ""

    try:
        separator = "&" if "?" in discovery_url else "?"
        cache_busted_url = f"{discovery_url}{separator}ts={int(time.time())}"
        response = requests.get(
            cache_busted_url,
            timeout=DISCOVERY_REQUEST_TIMEOUT,
            headers={"Cache-Control": "no-cache"},
        )
        response.raise_for_status()
        data = response.json()

        for key in ("public_url", "admin_server_url", "url"):
            value = str(data.get(key, "")).strip()
            if value:
                return value.rstrip("/")
    except Exception as exc:
        print(f"[WARN] discovery URL fetch failed: {exc}")

    return ""


def load_saved_server_base_url() -> str:
    try:
        if NGROK_URL_FILE.exists():
            saved = NGROK_URL_FILE.read_text(encoding="utf-8").strip()
            if saved:
                return saved.rstrip("/")
    except Exception as exc:
        print(f"[WARN] ngrok URL file read failed: {exc}")
    return ""


def resolve_server_base_url() -> str:
    global _DISCOVERY_LAST_URL, _DISCOVERY_LAST_CHECK_AT

    if SERVER_BASE_URL_ENV:
        return SERVER_BASE_URL_ENV

    if ADMIN_SERVER_ENV:
        return ADMIN_SERVER_ENV

    now = time.time()
    if build_discovery_url():
        if _DISCOVERY_LAST_URL and (now - _DISCOVERY_LAST_CHECK_AT) < DISCOVERY_REFRESH_SECONDS:
            return _DISCOVERY_LAST_URL

        discovered = fetch_server_base_url_from_discovery()
        _DISCOVERY_LAST_CHECK_AT = now
        if discovered:
            _DISCOVERY_LAST_URL = discovered
            return discovered
        if _DISCOVERY_LAST_URL:
            return _DISCOVERY_LAST_URL

    saved = load_saved_server_base_url()
    if saved:
        return saved

    return DEFAULT_ADMIN_SERVER_LOCAL.rstrip("/")


def refresh_server_base_url() -> str:
    global SERVER_BASE_URL
    latest = resolve_server_base_url()
    if latest != SERVER_BASE_URL:
        previous = SERVER_BASE_URL or "-"
        print(f"[INFO] 관리자 서버 주소 갱신: {previous} -> {latest}")
        SERVER_BASE_URL = latest
    return SERVER_BASE_URL


def build_scan_url() -> str:
    return f"{refresh_server_base_url()}{API_PATH}"


def update_last_scan_from_server(result: dict) -> None:
    scan = result.get("scan", {}) or {}
    with lock:
        last_scan.update({
            "uid": scan.get("uid"),
            "name": scan.get("name"),
            "status": scan.get("status", "대기중"),
            "reason": scan.get("reason", ""),
            "menu_date": scan.get("menu_date") or scan.get("date"),
            "menu_name": scan.get("menu_name"),
            "student_number": scan.get("student_number", ""),
            "scanned_at": now_time(),
        })


def update_last_scan_error(uid: str, reason: str) -> None:
    with lock:
        last_scan.update({
            "uid": uid,
            "name": None,
            "status": "오류",
            "reason": reason,
            "menu_date": now_date(),
            "menu_name": None,
            "student_number": "",
            "scanned_at": now_time(),
        })


def print_server_result(result: dict) -> None:
    ok = result.get("ok", False)
    scan = result.get("scan", {}) or {}

    print("\n" + "=" * 56)
    print(f"[SERVER OK] {ok}")
    print(f"UID: {scan.get('uid', '-')}")
    print(f"이름: {scan.get('name', '-')}")
    print(f"학번: {scan.get('student_number', '-')}")
    print(f"상태: {scan.get('status', '-')}")
    print(f"메뉴 날짜: {scan.get('menu_date') or scan.get('date', '-')}")
    print(f"메뉴명: {scan.get('menu_name', '-')}")
    print(f"걸린 코드: {scan.get('hit_codes', '-')}")
    print(f"걸린 알러지: {scan.get('hit_names', '-')}")
    print("사유:")
    print(scan.get("reason", "-"))
    if result.get("error"):
        print(f"오류: {result.get('error')}")
    print("=" * 56)


def extract_server_reason(data: dict) -> str:
    scan = data.get("scan")
    if not isinstance(scan, dict):
        scan = {}
    reason = data.get("reason") or scan.get("reason") or data.get("error")
    return str(reason or "").strip()


def normalize_server_status(data: dict) -> str:
    if data.get("ok") is False:
        return "error"

    scan = data.get("scan")
    if not isinstance(scan, dict):
        scan = {}

    raw_status = data.get("status")
    if raw_status is None:
        raw_status = scan.get("status")

    status_text = str(raw_status or "").strip().lower()
    log_debug("Raw server status:", raw_status)

    safe_statuses = {
        "safe",
        "ok",
        "안전",
        "정상",
        "알레르기 없음",
        "알러지 없음",
    }
    danger_statuses = {
        "danger",
        "unsafe",
        "위험",
        "주의",
        "경고",
        "알레르기 있음",
        "알러지 있음",
    }
    unknown_statuses = {
        "unknown",
        "unregistered",
        "not_registered",
        "not found",
        "미등록",
        "메뉴없음",
        "없음",
    }

    if status_text in safe_statuses:
        return "safe"

    if status_text in danger_statuses:
        return "danger"

    if status_text in unknown_statuses:
        return "unknown"

    matched_allergies = scan.get("matched_allergies")
    unsafe_menus = scan.get("unsafe_menus")
    needs_staff_review = scan.get("needs_staff_review")

    if isinstance(matched_allergies, list) and matched_allergies:
        return "danger"

    if isinstance(unsafe_menus, list) and unsafe_menus:
        return "danger"

    if needs_staff_review is True:
        return "unknown"

    if data.get("ok") is True and not status_text:
        return "safe"

    return "error"


def send_uid(uid: str) -> dict:
    url = build_scan_url()
    payload = {
        "uid": str(uid).strip(),
        "token": KIOSK_SCAN_API_TOKEN,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=SERVER_REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        print(f"[HTTP] {response.status_code} {url}")
        print(f"[HTTP] content-type: {response.headers.get('content-type', '-')}")

        try:
            data = response.json()
        except json.JSONDecodeError:
            body = response.text or ""
            print("[ERROR] 서버 응답이 JSON 형식이 아니야.")
            if not body.strip():
                print("[DEBUG] 응답 본문이 비어 있어.")
            else:
                print("[DEBUG] 응답 본문 미리보기:")
                print(body[:500])
            reason = "server response is not JSON"
            update_last_scan_error(uid, reason)
            return {
                "ok": False,
                "server_status": "error",
                "error": reason,
                "reason": reason,
            }

        print_server_result(data)
        if "scan" in data:
            update_last_scan_from_server(data)

        data["server_status"] = normalize_server_status(data)
        data["reason"] = extract_server_reason(data)

        if response.ok and data.get("ok"):
            return data

        reason = str(data.get("error") or "서버가 요청을 처리하지 못했어")
        update_last_scan_error(uid, reason)
        data["ok"] = False
        data["reason"] = reason
        return data
    except requests.RequestException as exc:
        reason = str(exc)
        print(f"[NETWORK ERROR] 서버 전송 실패: {reason}")
        update_last_scan_error(uid, reason)
        return {
            "ok": False,
            "server_status": "error",
            "error": reason,
            "reason": reason,
        }


def format_uid_hyphen(uid):
    return "-".join(str(x) for x in uid)


def format_uid_for_server(uid):
    uid_value = 0
    for byte in uid:
        uid_value = (uid_value << 8) | int(byte)
    return str(uid_value).zfill(10)


def apply_led_result(led_buzzer, result):
    reason = result.get("reason") or ""

    if not result.get("ok"):
        led_buzzer.red_with_buzzer_signal()
        return "잘못 인식됨", reason or "server send failed"

    if not USE_SERVER_RESPONSE:
        led_buzzer.green_signal()
        return "알레르기 없음", "server send success"

    server_status = result.get("server_status")

    if server_status == "safe":
        led_buzzer.green_signal()
        return "알레르기 없음", reason
    if server_status == "danger":
        led_buzzer.red_signal()
        return "알레르기 있음", reason
    if server_status == "unknown":
        led_buzzer.red_with_buzzer_signal()
        return "잘못 인식됨", reason or "unknown rfid"

    led_buzzer.red_with_buzzer_signal()
    return "잘못 인식됨", reason or "server response error"


def update_rfid_state(mode: str, uid=None, error: str = "") -> None:
    with lock:
        rfid_state["mode"] = mode
        rfid_state["last_error"] = error
        if uid is not None:
            rfid_state["last_uid"] = uid
            rfid_state["last_read_at"] = now_time()


def run_local_gui(scan_target) -> bool:
    if not ENABLE_LOCAL_GUI:
        return False

    try:
        import tkinter as tk
    except Exception as exc:
        print(f"[WARN] Local GUI is not available: {exc}")
        return False

    try:
        root = tk.Tk()
    except Exception as exc:
        print(f"[WARN] Local GUI could not start: {exc}")
        return False

    root.title("RFID Scan Monitor")
    root.geometry("760x520")
    root.minsize(640, 440)
    root.configure(bg="#f5f7fb")

    title_var = tk.StringVar(value="Scan RFID Card")
    message_var = tk.StringVar(value="Place a card near the reader.")
    field_vars = {
        "UID": tk.StringVar(value="-"),
        "Raw UID": tk.StringVar(value="-"),
        "Scan Time": tk.StringVar(value="-"),
        "Server": tk.StringVar(value="-"),
        "Name": tk.StringVar(value="-"),
        "Student No": tk.StringVar(value="-"),
        "Menu Date": tk.StringVar(value="-"),
        "Menu Name": tk.StringVar(value="-"),
        "Note": tk.StringVar(value="-"),
    }

    outer = tk.Frame(root, bg="#f5f7fb", padx=28, pady=26)
    outer.pack(fill="both", expand=True)

    title_label = tk.Label(
        outer,
        textvariable=title_var,
        bg="#f5f7fb",
        fg="#172033",
        font=("Helvetica", 28, "bold"),
        anchor="w",
    )
    title_label.pack(fill="x")

    message_label = tk.Label(
        outer,
        textvariable=message_var,
        bg="#f5f7fb",
        fg="#526173",
        font=("Helvetica", 15),
        anchor="w",
        pady=10,
    )
    message_label.pack(fill="x")

    panel = tk.Frame(outer, bg="#ffffff", padx=24, pady=22, highlightthickness=1, highlightbackground="#d9e0ea")
    panel.pack(fill="both", expand=True, pady=(18, 0))
    panel.grid_columnconfigure(1, weight=1)

    for row, (label, var) in enumerate(field_vars.items()):
        tk.Label(
            panel,
            text=label,
            bg="#ffffff",
            fg="#6b7280",
            font=("Helvetica", 12, "bold"),
            anchor="w",
            width=12,
        ).grid(row=row, column=0, sticky="nw", pady=7)
        tk.Label(
            panel,
            textvariable=var,
            bg="#ffffff",
            fg="#111827",
            font=("Helvetica", 14),
            anchor="w",
            justify="left",
            wraplength=500,
        ).grid(row=row, column=1, sticky="ew", pady=7)

    def reset_fields():
        for var in field_vars.values():
            var.set("-")

    reset_after_id = {"value": None}

    def cancel_reset_timer():
        if reset_after_id["value"] is not None:
            try:
                root.after_cancel(reset_after_id["value"])
            except Exception:
                pass
            reset_after_id["value"] = None

    def show_ready():
        cancel_reset_timer()
        title_var.set("Scan RFID Card")
        message_var.set("Place a card near the reader.")
        reset_fields()

    def apply_event(event):
        kind = event.get("kind")
        if kind == "ready":
            show_ready()
            if event.get("title"):
                title_var.set(event.get("title"))
            if event.get("message"):
                message_var.set(event.get("message"))
            return

        if kind == "scan":
            cancel_reset_timer()
            title_var.set(event.get("title") or "RFID Scan Info")
            message_var.set("Scan data updated. Returning to standby in 3 seconds.")
            field_vars["UID"].set(event.get("uid") or "-")
            field_vars["Raw UID"].set(event.get("uid_hyphen") or "-")
            field_vars["Scan Time"].set(event.get("scanned_at") or "-")
            field_vars["Server"].set(event.get("server") or "-")
            field_vars["Name"].set(event.get("name") or "-")
            field_vars["Student No"].set(event.get("student_number") or "-")
            field_vars["Menu Date"].set(event.get("menu_date") or "-")
            field_vars["Menu Name"].set(event.get("menu_name") or "-")
            field_vars["Note"].set(event.get("note") or "-")
            reset_after_id["value"] = root.after(3000, show_ready)
            return

        if kind == "error":
            cancel_reset_timer()
            title_var.set("RFID Status Check")
            message_var.set(event.get("message") or "An error occurred.")

    def drain_events():
        while True:
            try:
                event = GUI_EVENT_QUEUE.get_nowait()
            except queue.Empty:
                break
            apply_event(event)
        if not SCAN_STOP_EVENT.is_set():
            root.after(120, drain_events)

    def on_close():
        SCAN_STOP_EVENT.set()
        root.after(150, root.destroy)

    SCAN_STOP_EVENT.clear()
    publish_gui_ready()
    worker = threading.Thread(target=scan_target, daemon=True)
    worker.start()
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(120, drain_events)
    root.mainloop()
    SCAN_STOP_EVENT.set()
    worker.join(timeout=2)
    return True


def scan_loop() -> None:
    if lgpio is None or spidev is None:
        if LGPIO_IMPORT_ERROR:
            print(f"[ERROR] lgpio 로드 실패: {LGPIO_IMPORT_ERROR}")
        if SPIDEV_IMPORT_ERROR:
            print(f"[ERROR] spidev 로드 실패: {SPIDEV_IMPORT_ERROR}")
        update_rfid_state("오류", error="lgpio 또는 spidev를 불러오지 못했어")
        publish_gui_event("error", message="lgpio or spidev is not available.")
        return

    chip = None
    reader = None
    led_buzzer = None
    last_uid = None
    last_sent_time = 0.0

    try:
        chip = lgpio.gpiochip_open(0)
        led_buzzer = LEDBuzzer(chip)
        reader = RC522(chip=chip, rst_pin=RST_PIN)

        update_rfid_state("감시중")
        publish_gui_ready()
        print("ready for scan")
        print("[INFO] 카드 태그 대기 중... Ctrl+C로 종료")

        while not SCAN_STOP_EVENT.is_set():
            try:
                uid = reader.read_uid()
                read_warning = reader.last_read_error

                if uid is None:
                    if last_uid is not None:
                        log_debug("Card removed. Ready for next scan.")
                        last_uid = None
                        led_buzzer.all_off()
                        update_rfid_state("감시중", error="")
                        publish_gui_ready()
                    time.sleep(POLL_INTERVAL)
                    continue

                if uid == WRONG_READ:
                    uid_text = WRONG_READ
                    reason = "rfid read failed"
                    now = time.time()

                    if uid_text == last_uid and (now - last_sent_time) < RFID_DEDUP_SECONDS:
                        time.sleep(POLL_INTERVAL)
                        continue

                    last_uid = uid_text
                    update_rfid_state("잘못 인식됨", uid=uid_text, error=reason)
                    print(f"\n[SCAN] UID 감지 실패: {uid_text}")

                    if SEND_TO_SERVER:
                        result = send_uid(uid_text)
                        status_text, reason = apply_led_result(led_buzzer, result)
                        if result.get("ok"):
                            last_sent_time = now
                        publish_gui_scan(uid_text, result=result, read_warning=reason)
                    else:
                        led_buzzer.red_with_buzzer_signal()
                        status_text = "잘못 인식됨"
                        update_last_scan_error(uid_text, reason)
                        publish_gui_scan(uid_text, read_warning=reason)

                    print_scan_summary(uid_text, status_text, reason)
                    update_rfid_state("감시중", uid=uid_text, error=reason)
                    time.sleep(POST_SCAN_DELAY)
                    continue

                uid_hyphen_text = format_uid_hyphen(uid)
                uid_text = format_uid_for_server(uid)

                now = time.time()
                if uid_text == last_uid and (now - last_sent_time) < RFID_DEDUP_SECONDS:
                    time.sleep(POLL_INTERVAL)
                    continue

                last_uid = uid_text
                update_rfid_state("태그 감지", uid=uid_text, error=read_warning)
                print(f"\n[SCAN] UID 감지: {uid_text}")
                log_debug("Decimal UID (hyphen):", uid_hyphen_text)
                log_debug("HEX UID:", " ".join(hex(x) for x in uid))
                log_debug("Server UID:", uid_text)
                if read_warning:
                    print(f"[WARN] RFID validation warning: {read_warning}")

                if SEND_TO_SERVER:
                    result = send_uid(uid_text)
                    status_text, reason = apply_led_result(led_buzzer, result)
                    if result.get("ok"):
                        last_sent_time = now
                    publish_gui_scan(
                        uid_text,
                        result=result,
                        uid_hyphen=uid_hyphen_text,
                        read_warning=read_warning,
                    )
                else:
                    log_debug("Server send skipped: local RFID scan success mode")
                    led_buzzer.green_signal()
                    status_text = "알레르기 없음"
                    reason = "local RFID scan success"
                    publish_gui_scan(
                        uid_text,
                        uid_hyphen=uid_hyphen_text,
                        read_warning=read_warning,
                    )

                print_scan_summary(uid_text, status_text, reason)
                update_rfid_state("감시중", uid=uid_text, error=read_warning)
                time.sleep(POST_SCAN_DELAY)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                print(f"[ERROR] RFID 오류: {exc}")
                update_rfid_state("오류", error=str(exc))
                publish_gui_event("error", message=str(exc))
                if led_buzzer is not None:
                    led_buzzer.red_with_buzzer_signal()

            time.sleep(POLL_INTERVAL)
    finally:
        if led_buzzer is not None:
            led_buzzer.all_off()

        if reader is not None:
            reader.close()

        if chip is not None:
            try:
                lgpio.gpiochip_close(chip)
            except Exception as exc:
                log_debug("GPIO chip close failed:", exc)


def main() -> None:
    refresh_server_base_url()
    print(f"[INFO] 서버 주소: {build_scan_url()}")

    discovery_url = build_discovery_url()
    if discovery_url:
        print(f"[INFO] discovery URL: {discovery_url}")

    if not run_local_gui(scan_loop):
        SCAN_STOP_EVENT.clear()
        scan_loop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] 종료 중...")
