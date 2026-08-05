from pathlib import Path

path = Path("admin/app_admin.py")
text = path.read_text(encoding="utf-8-sig")

css_anchor = """    .row-actions {\n      display: flex;\n      gap: 10px;\n      flex-wrap: wrap;\n      margin-top: 16px;\n    }\n"""
css_insert = css_anchor + """
    .notification-settings {
      margin-top: 20px;
      padding: 18px;
      border: 1px solid #2a2f37;
      border-radius: 16px;
      background: #14171b;
    }
    .notification-status {
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 12px 0;
      font-weight: 800;
    }
    .status-dot {
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: #94a3b8;
      flex: 0 0 auto;
    }
    .status-dot.granted { background: #22c55e; }
    .status-dot.default { background: #f59e0b; }
    .status-dot.denied { background: #ef4444; }
    .notification-help {
      margin-top: 10px;
      color: #9aa4b2;
      font-size: 13px;
      line-height: 1.6;
      white-space: pre-line;
    }
"""
if css_anchor not in text:
    raise SystemExit("CSS anchor not found")
text = text.replace(css_anchor, css_insert, 1)

html_anchor = """      <div class=\"row-actions\">\n        <button class=\"btn btn-primary\" onclick=\"saveStudentMyAccount()\">저장</button>\n      </div>\n"""
html_insert = """      <div class=\"notification-settings\">\n        <h3>급식 푸시알림 권한</h3>\n        <div class=\"muted\">알림 권한 상태를 확인하고, 상태에 맞는 안내를 제공해.</div>\n        <div class=\"notification-status\">\n          <span id=\"notificationStatusDot\" class=\"status-dot\"></span>\n          <span id=\"notificationStatusText\">확인 중...</span>\n        </div>\n        <div class=\"row-actions\">\n          <button id=\"notificationPermissionButton\" class=\"btn\" type=\"button\" onclick=\"handleNotificationPermission()\">알림 상태 확인</button>\n          <button id=\"notificationTestButton\" class=\"btn btn-primary\" type=\"button\" onclick=\"sendNotificationTest()\" style=\"display:none;\">테스트 알림 보내기</button>\n        </div>\n        <div id=\"notificationHelp\" class=\"notification-help\"></div>\n      </div>\n\n""" + html_anchor
if html_anchor not in text:
    raise SystemExit("HTML anchor not found")
text = text.replace(html_anchor, html_insert, 1)

js_anchor = """    document.addEventListener(\"DOMContentLoaded\", () => {\n      renderMyAllergies(false);\n    });\n"""
js_insert = """    function notificationPermissionState() {
      if (!(\"Notification\" in window)) return \"unsupported\";
      return Notification.permission;
    }

    function renderNotificationPermissionState() {
      const state = notificationPermissionState();
      const dot = document.getElementById(\"notificationStatusDot\");
      const textEl = document.getElementById(\"notificationStatusText\");
      const button = document.getElementById(\"notificationPermissionButton\");
      const testButton = document.getElementById(\"notificationTestButton\");
      const help = document.getElementById(\"notificationHelp\");
      if (!dot || !textEl || !button || !testButton || !help) return;

      dot.className = \"status-dot\";
      testButton.style.display = \"none\";

      if (state === \"granted\") {
        dot.classList.add(\"granted\");
        textEl.textContent = \"알림 권한이 허용되어 있어.\";
        button.textContent = \"권한 다시 확인\";
        testButton.style.display = \"inline-flex\";
        help.textContent = \"이 기기에서 급식 푸시알림을 받을 수 있어.\";
        return;
      }

      if (state === \"default\") {
        dot.classList.add(\"default\");
        textEl.textContent = \"아직 알림 권한을 선택하지 않았어.\";
        button.textContent = \"알림 허용하기\";
        help.textContent = \"버튼을 누르면 브라우저의 알림 권한 요청창이 표시돼.\";
        return;
      }

      if (state === \"denied\") {
        dot.classList.add(\"denied\");
        textEl.textContent = \"알림 권한이 차단되어 있어.\";
        button.textContent = \"차단 해제 방법 보기\";
        help.textContent = \"주소창 옆 사이트 설정 아이콘을 누른 뒤, 알림을 ‘허용’으로 변경해줘. 변경 후 이 버튼을 다시 눌러 상태를 확인하면 돼.\";
        return;
      }

      textEl.textContent = \"이 브라우저는 푸시알림을 지원하지 않아.\";
      button.textContent = \"지원되지 않음\";
      button.disabled = true;
      help.textContent = \"Chrome, Edge, Safari 등 알림을 지원하는 최신 브라우저에서 다시 접속해줘.\";
    }

    async function handleNotificationPermission() {
      const state = notificationPermissionState();
      if (state === \"unsupported\") {
        renderNotificationPermissionState();
        return;
      }

      if (state === \"default\") {
        try {
          await Notification.requestPermission();
        } catch (error) {
          alert(\"알림 권한 요청 중 문제가 생겼어.\");
        }
        renderNotificationPermissionState();
        return;
      }

      if (state === \"denied\") {
        alert(\"알림이 차단되어 있어. 주소창 옆 사이트 설정에서 알림을 허용으로 바꾼 뒤 다시 확인해줘.\");
        renderNotificationPermissionState();
        return;
      }

      renderNotificationPermissionState();
    }

    function sendNotificationTest() {
      if (notificationPermissionState() !== \"granted\") {
        renderNotificationPermissionState();
        return;
      }
      new Notification(\"급식 안전 알림 테스트\", {
        body: \"푸시알림 권한이 정상적으로 설정됐어.\",
        tag: \"meal-safety-test\"
      });
    }

""" + js_anchor.replace("renderMyAllergies(false);", "renderMyAllergies(false);\n      renderNotificationPermissionState();\n      window.addEventListener(\"focus\", renderNotificationPermissionState);")
if js_anchor not in text:
    raise SystemExit("JS anchor not found")
text = text.replace(js_anchor, js_insert, 1)

path.write_text(text, encoding="utf-8")
print("Notification permission UI applied")
