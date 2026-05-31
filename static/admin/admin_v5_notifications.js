(function () {
  const notificationStoreKey = "allergySafeClientNotifications";
  const readStoreKey = "allergySafeReadNotifications";
  const aiJobStoreKey = "allergySafeAiMealJobs";

  function readStore(key, fallback) {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "");
      return value == null ? fallback : value;
    } catch (error) {
      return fallback;
    }
  }

  function writeStore(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {}
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function clientNotifications() {
    return readStore(notificationStoreKey, []);
  }

  function serverNotifications() {
    return window.__adminServerNotifications || [];
  }

  function readIds() {
    return new Set(readStore(readStoreKey, []));
  }

  function allNotifications() {
    const byId = new Map();
    serverNotifications().concat(clientNotifications()).forEach((item) => {
      if (item && item.id) byId.set(item.id, item);
    });
    return Array.from(byId.values()).slice(0, 40);
  }

  function unreadNotifications() {
    const read = readIds();
    return allNotifications().filter((item) => item.id && !read.has(item.id));
  }

  function saveClientNotification(item) {
    if (!item || !item.id) return;
    const list = clientNotifications().filter((old) => old.id !== item.id);
    list.unshift(item);
    writeStore(notificationStoreKey, list.slice(0, 30));
  }

  function markRead(id) {
    if (!id) return;
    const read = readIds();
    read.add(id);
    writeStore(readStoreKey, Array.from(read).slice(-200));
  }

  function markTargetRead(target) {
    allNotifications().forEach((item) => {
      if (!target || item.target === target) markRead(item.id);
    });
    renderNotifications();
    refreshBadges();
  }

  function notificationHtml(item, isRead) {
    const path = item.path || "/notifications";
    return `<a class="notification-item ${isRead ? "" : "unread"}" href="${escapeHtml(path)}" data-notification-id="${escapeHtml(item.id)}" data-notification-target="${escapeHtml(item.target || "notifications")}">
      <span class="notification-icon ${escapeHtml(item.kind || "info")}">${escapeHtml(item.icon || "N")}</span>
      <div><strong>${escapeHtml(item.title || "알림")}</strong><p>${escapeHtml(item.detail || "")}</p><time>${escapeHtml(item.time || "")}</time></div>
    </a>`;
  }

  async function readJsonResponse(res) {
    const contentType = res.headers && res.headers.get ? res.headers.get("content-type") || "" : "";
    if (!contentType.includes("application/json")) {
      await res.text().catch(() => "");
      throw new Error("서버가 JSON이 아닌 응답을 반환했습니다.");
    }
    return res.json();
  }

  function renderNotifications() {
    const list = document.getElementById("notificationList") || document.querySelector(".notification-list");
    if (!list) return;
    const items = allNotifications();
    const read = readIds();
    if (!items.length) {
      list.innerHTML = '<div class="empty-state"><strong>표시할 알림이 없습니다.</strong><p>RFID 인식, 학생/메뉴 등록, AI 작업 완료 기록이 생기면 표시됩니다.</p></div>';
      return;
    }
    list.innerHTML = items.slice(0, 12).map((item) => notificationHtml(item, read.has(item.id))).join("");
    list.querySelectorAll("[data-notification-id]").forEach((node) => {
      node.addEventListener("click", () => {
        markRead(node.dataset.notificationId);
        refreshBadges();
      });
    });
  }

  function refreshBadges() {
    const unreadTargets = new Set(unreadNotifications().map((item) => item.target).filter(Boolean));
    document.querySelectorAll(".js-new-badge").forEach((badge) => {
      const targets = String(badge.dataset.targets || "").split(/\s+/).filter(Boolean);
      badge.classList.toggle("hidden", !targets.some((target) => unreadTargets.has(target)));
    });
    const bell = document.getElementById("topbarNotificationButton") || document.querySelector(".notification-wrap .icon-action");
    if (bell) bell.classList.toggle("has-dot", unreadTargets.size > 0);
  }

  function injectStyle() {
    if (document.getElementById("adminNotificationPatchStyle")) return;
    const style = document.createElement("style");
    style.id = "adminNotificationPatchStyle";
    style.textContent = `
      .nav-link-new{margin-left:auto;padding:2px 6px;border-radius:999px;background:rgba(75,185,159,.13);border:1px solid rgba(75,185,159,.25);color:#75dbc8;font-size:10px;font-weight:900}
      .notification-item{color:inherit;text-decoration:none}
      .notification-item.unread{background:rgba(91,141,239,.07)}
      .notification-item:hover{background:rgba(85,195,170,.08)}
      html{scrollbar-width:thin;scrollbar-color:rgba(85,195,170,.5) transparent}
      ::-webkit-scrollbar{width:10px;height:10px}
      ::-webkit-scrollbar-track{background:transparent}
      ::-webkit-scrollbar-thumb{background:rgba(85,195,170,.42);border:3px solid transparent;border-radius:999px;background-clip:padding-box}
      ::-webkit-scrollbar-thumb:hover{background:rgba(85,195,170,.68);border:2px solid transparent;background-clip:padding-box}
      .admin-sidebar::-webkit-scrollbar-thumb{background:rgba(148,163,184,.34);border:3px solid transparent;background-clip:padding-box}
    `;
    document.head.appendChild(style);
  }

  function badge(targets) {
    return `<span class="nav-link-new js-new-badge hidden" data-targets="${targets}">New</span>`;
  }

  function enhanceSidebar() {
    const lunchLink = document.querySelector('a[href="/lunch-log"]');
    if (lunchLink && !lunchLink.querySelector(".js-new-badge")) {
      lunchLink.insertAdjacentHTML("beforeend", badge("lunch_log"));
    }
    const dashboardParent = lunchLink?.closest(".nav-group")?.querySelector(".nav-parent");
    if (dashboardParent && !dashboardParent.querySelector(".js-new-badge")) {
      dashboardParent.classList.add("has-tag");
      dashboardParent.querySelector(".chevron")?.insertAdjacentHTML("beforebegin", '<span class="nav-tag new js-new-badge hidden" data-targets="lunch_log notifications">New</span>');
    }
    if (lunchLink && !document.querySelector('a[href="/notifications"]')) {
      lunchLink.insertAdjacentHTML("afterend", `<a class="nav-link" href="/notifications"><span class="nav-bullet"></span>알림센터${badge("notifications lunch_log meal_ai ai_tools ai_daily ai_student ai_menu student_manage menu_manage")}</a>`);
    }

    const aiParentBadge = Array.from(document.querySelectorAll(".nav-parent .nav-tag.new")).find((node) => node.closest(".nav-parent")?.textContent.includes("AI Tools"));
    if (aiParentBadge) {
      aiParentBadge.classList.add("js-new-badge", "hidden");
      aiParentBadge.dataset.targets = "meal_ai ai_tools ai_daily ai_student ai_menu";
    }
    [
      ["/admin/meal/upload", "meal_ai"],
      ["/admin/ai-tools", "ai_tools"],
      ["/admin/ai-tools/daily-brief", "ai_daily"],
      ["/admin/ai-tools/student-plan", "ai_student"],
      ["/admin/ai-tools/menu-review", "ai_menu"],
    ].forEach(([href, target]) => {
      const link = document.querySelector(`.gentelella-nav a[href="${href}"]`);
      if (link && !link.querySelector(".js-new-badge")) link.insertAdjacentHTML("beforeend", badge(target));
    });
  }

  async function refreshServerNotifications() {
    try {
      const res = await fetch("/api/admin/notifications", { cache: "no-store" });
      if (!res.ok) return;
      const data = await readJsonResponse(res);
      if (!data.ok) return;
      window.__adminServerNotifications = data.notifications || [];
      renderNotifications();
      refreshBadges();
    } catch (error) {}
  }

  function removeAiJob(jobId) {
    writeStore(aiJobStoreKey, readStore(aiJobStoreKey, []).filter((item) => item.job_id !== jobId));
  }

  async function pollAiJobs() {
    const jobs = readStore(aiJobStoreKey, []);
    if (!jobs.length) return;
    for (const job of jobs) {
      try {
        const res = await fetch(job.status_url || `/api/meal/analyze-jobs/${encodeURIComponent(job.job_id)}`, { cache: "no-store" });
        if (!res.ok) {
          removeAiJob(job.job_id);
          continue;
        }
        const data = await readJsonResponse(res);
        if (!data.ok) {
          removeAiJob(job.job_id);
          continue;
        }
        if (data.status === "done" || data.status === "error") {
          if (data.notification) window.registerAdminNotification(data.notification);
          removeAiJob(job.job_id);
        }
      } catch (error) {}
    }
  }

  function wrapAiFetchNotifications() {
    if (!window.fetch || window.__adminAiNotifyFetch) return;
    window.__adminAiNotifyFetch = true;
    const nativeFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
      const response = await nativeFetch(...args);
      const url = String(args[0]?.url || args[0] || "");
      const targetMap = [
        ["/api/ai/safety-plan", "ai_student", "학생별 안전계획 완료", "/admin/ai-tools/student-plan"],
        ["/api/ai/daily-brief", "ai_daily", "오늘 위험 브리핑 완료", "/admin/ai-tools/daily-brief"],
        ["/api/ai/menu-review", "ai_menu", "메뉴 코드 점검 완료", "/admin/ai-tools/menu-review"],
      ];
      const match = targetMap.find(([path]) => url.includes(path));
      if (match && response.ok) {
        response.clone().json().then((data) => {
          if (data && data.ok) {
            window.registerAdminNotification({
              id: `${match[1]}:${Date.now()}`,
              target: match[1],
              kind: "ai",
              icon: "AI",
              title: match[2],
              detail: "AI 분석 결과가 준비됐어.",
              time: new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" }),
              path: match[3],
            });
          }
        }).catch(() => {});
      }
      return response;
    };
  }

  window.registerAdminNotification = function (item) {
    saveClientNotification(item);
    renderNotifications();
    refreshBadges();
  };
  window.markAdminNotificationsRead = markTargetRead;
  window.getAdminNotifications = allNotifications;
  window.adminNotificationHtml = notificationHtml;

  document.addEventListener("DOMContentLoaded", () => {
    injectStyle();
    enhanceSidebar();
    wrapAiFetchNotifications();
    renderNotifications();
    refreshBadges();
    setTimeout(refreshServerNotifications, 700);
    setTimeout(pollAiJobs, 1200);
    setInterval(refreshServerNotifications, 30000);
    setInterval(pollAiJobs, 5000);

    const path = window.location.pathname;
    if (path === "/notifications") setTimeout(() => markTargetRead(), 500);
    else if (path === "/lunch-log") setTimeout(() => markTargetRead("lunch_log"), 500);
    else if (path === "/admin/meal/upload" || path.startsWith("/admin/meal/analyze/result/")) setTimeout(() => markTargetRead("meal_ai"), 500);
    else if (path === "/admin/ai-tools/daily-brief") setTimeout(() => markTargetRead("ai_daily"), 500);
    else if (path === "/admin/ai-tools/student-plan") setTimeout(() => markTargetRead("ai_student"), 500);
    else if (path === "/admin/ai-tools/menu-review") setTimeout(() => markTargetRead("ai_menu"), 500);
    else if (path === "/admin/ai-tools") setTimeout(() => markTargetRead("ai_tools"), 500);
  });
})();
