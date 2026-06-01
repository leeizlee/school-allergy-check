(function () {
  const toastSeenKey = "allergySafeToastSeen";
  const readStoreKey = "allergySafeReadNotifications";
  const backgroundJobStoreKey = "allergySafeBackgroundJobs";
  let serverNotificationsBootstrapped = false;
  let registerWrapped = false;

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

  function nowTime() {
    try {
      return new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
    } catch (error) {
      return "";
    }
  }

  function seenIds() {
    return new Set(readStore(toastSeenKey, []));
  }

  function rememberSeen(id) {
    if (!id) return;
    const seen = seenIds();
    seen.add(id);
    writeStore(toastSeenKey, Array.from(seen).slice(-240));
  }

  function markRead(item) {
    if (!item || !item.id) return;
    const read = new Set(readStore(readStoreKey, []));
    read.add(item.id);
    writeStore(readStoreKey, Array.from(read).slice(-240));
    if (item.target && typeof window.markAdminNotificationsRead === "function") {
      window.markAdminNotificationsRead(item.target);
    }
  }

  function thumbnailMarkup(item) {
    if (item && item.image) {
      return `<img src="${escapeHtml(item.image)}" alt="">`;
    }
    const label = escapeHtml(item?.icon || "AI");
    const kind = escapeHtml(item?.kind || "ai");
    return `<span class="admin-workflow-toast-thumb ${kind}">${label}</span>`;
  }

  function showWorkflowToast(item) {
    if (!item || !item.id) return;
    const seen = seenIds();
    if (seen.has(item.id)) return;
    rememberSeen(item.id);

    let stack = document.getElementById("adminWorkflowToastStack");
    if (!stack) {
      stack = document.createElement("div");
      stack.id = "adminWorkflowToastStack";
      stack.className = "admin-workflow-toast-stack";
      document.body.appendChild(stack);
    }

    const toast = document.createElement("a");
    toast.className = `admin-workflow-toast ${item.kind || "ai"}`;
    toast.href = item.path || "/notifications";
    toast.innerHTML = `
      <span class="admin-workflow-toast-media">${thumbnailMarkup(item)}</span>
      <span class="admin-workflow-toast-copy">
        <strong>${escapeHtml(item.title || "작업 완료")}</strong>
        <small>${escapeHtml(item.detail || "")}</small>
      </span>
    `;
    toast.addEventListener("click", function () {
      markRead(item);
      toast.remove();
    });
    stack.prepend(toast);
    window.setTimeout(function () {
      toast.classList.add("leaving");
      window.setTimeout(function () {
        toast.remove();
      }, 220);
    }, 7200);
  }

  function normalizeNotification(item, fallback) {
    const next = Object.assign({}, fallback || {}, item || {});
    if (!next.id) next.id = `${next.target || "notice"}:${Date.now()}`;
    if (!next.time) next.time = nowTime();
    if (!next.path) next.path = "/notifications";
    if (!next.kind) next.kind = "ai";
    if (!next.icon) next.icon = "AI";
    return next;
  }

  function wrapRegisterNotification() {
    if (registerWrapped || typeof window.registerAdminNotification !== "function") return;
    registerWrapped = true;
    const original = window.registerAdminNotification;
    window.registerAdminNotification = function (item, options) {
      const normalized = normalizeNotification(item);
      original.call(window, normalized);
      if (!options || options.toast !== false) showWorkflowToast(normalized);
    };
  }

  async function readJsonResponse(res) {
    const type = res.headers.get("content-type") || "";
    if (!type.includes("application/json")) {
      const text = await res.text().catch(() => "");
      throw new Error(text || "서버가 JSON이 아닌 응답을 반환했어.");
    }
    const data = await res.json();
    if (!res.ok || data.ok === false) throw new Error(data.error || data.message || `서버 오류 ${res.status}`);
    return data;
  }

  async function refreshServerToasts() {
    try {
      const res = await fetch("/api/admin/notifications", { cache: "no-store" });
      const data = await readJsonResponse(res);
      const notifications = Array.isArray(data.notifications) ? data.notifications : [];
      if (!serverNotificationsBootstrapped) {
        notifications.forEach((item) => rememberSeen(item.id));
        serverNotificationsBootstrapped = true;
        return;
      }
      const read = new Set(readStore(readStoreKey, []));
      notifications.forEach((item) => {
        if (item && item.id && !read.has(item.id)) showWorkflowToast(normalizeNotification(item));
      });
    } catch (error) {}
  }

  function backgroundJobs() {
    return readStore(backgroundJobStoreKey, []);
  }

  function saveBackgroundJobs(jobs) {
    writeStore(backgroundJobStoreKey, jobs.slice(0, 20));
  }

  function trackBackgroundJob(job) {
    if (!job || !job.job_id) return;
    const list = backgroundJobs().filter((item) => item.job_id !== job.job_id);
    list.unshift(job);
    saveBackgroundJobs(list);
  }

  function removeBackgroundJob(jobId) {
    saveBackgroundJobs(backgroundJobs().filter((item) => item.job_id !== jobId));
  }

  async function pollBackgroundJobs() {
    const jobs = backgroundJobs();
    if (!jobs.length) return;
    for (const job of jobs) {
      try {
        const res = await fetch(job.status_url || `/api/admin/background-jobs/${encodeURIComponent(job.job_id)}`, { cache: "no-store" });
        const data = await readJsonResponse(res);
        const state = data.job || {};
        if (state.status === "done" || state.status === "error") {
          const notification = normalizeNotification(state.notification, {
            id: `job:${job.job_id}:${state.status}`,
            target: job.target || state.target || "notifications",
            path: state.path || job.path || "/notifications",
            icon: state.icon || job.icon || "AI",
            title: state.status === "done" ? (job.success_title || "작업 완료") : (job.failure_title || "작업 실패"),
            detail: state.message || "",
            kind: state.status === "done" ? (job.kind || "ai") : "danger",
          });
          if (typeof window.registerAdminNotification === "function") {
            window.registerAdminNotification(notification);
          } else {
            showWorkflowToast(notification);
          }
          removeBackgroundJob(job.job_id);
        }
      } catch (error) {
        removeBackgroundJob(job.job_id);
      }
    }
  }

  function ensureMealSaveStatus(form) {
    let panel = document.getElementById("mealSaveAsyncStatus");
    if (panel) return panel;
    panel = document.createElement("div");
    panel.id = "mealSaveAsyncStatus";
    panel.className = "alert-panel info";
    panel.style.margin = "16px 0";
    panel.innerHTML = '<span class="alert-icon">AI</span><div><strong>저장 작업 등록 중</strong><p>대량 저장은 백그라운드에서 처리하고, 완료되면 오른쪽 위에 알림을 띄울게.</p></div>';
    form.prepend(panel);
    return panel;
  }

  function installMealSaveAsync() {
    document.querySelectorAll('form[action$="/admin/meal/save"]').forEach((form) => {
      if (form.dataset.asyncSaveInstalled === "1") return;
      form.dataset.asyncSaveInstalled = "1";
      form.addEventListener(
        "submit",
        async function (event) {
          event.preventDefault();
          event.stopImmediatePropagation();
          const submitButton = form.querySelector('[type="submit"]');
          const panel = ensureMealSaveStatus(form);
          const message = panel.querySelector("p");
          if (submitButton) submitButton.disabled = true;
          panel.classList.remove("danger", "safe");
          panel.classList.add("info");
          if (message) message.textContent = "Google Sheets 저장 작업을 등록하고 있어. 화면을 이동해도 계속 확인할게.";
          try {
            const res = await fetch("/api/meal/save-async", { method: "POST", body: new FormData(form) });
            const data = await readJsonResponse(res);
            trackBackgroundJob({
              job_id: data.job_id,
              status_url: data.status_url,
              target: "menu_manage",
              path: "/menu-manage",
              icon: "ME",
              kind: "ai",
              success_title: "급식관리 - AI급식 저장 완료",
              failure_title: "급식관리 - AI급식 저장 실패",
            });
            if (message) message.textContent = "저장 명령을 받았어. Sheets 제한이 걸리면 자동으로 기다렸다가 다시 시도할게.";
            if (typeof window.registerAdminNotification === "function") {
              window.registerAdminNotification(
                {
                  id: `meal-save-start:${data.job_id}`,
                  target: "menu_manage",
                  path: "/menu-manage",
                  icon: "ME",
                  title: "급식관리 - AI급식 저장 대기",
                  detail: "대량 저장 작업이 백그라운드에서 진행 중이야.",
                  time: nowTime(),
                  kind: "ai",
                },
                { toast: false }
              );
            }
            window.setTimeout(pollBackgroundJobs, 1200);
          } catch (error) {
            panel.classList.remove("info");
            panel.classList.add("danger");
            if (message) message.textContent = error.message || "저장 작업을 시작하지 못했어.";
          } finally {
            if (submitButton) submitButton.disabled = false;
          }
        },
        true
      );
    });
  }

  function wrapAiResultFetchToasts() {
    if (!window.fetch || window.__adminWorkflowFetchWrapped) return;
    window.__adminWorkflowFetchWrapped = true;
    const nativeFetch = window.fetch.bind(window);
    window.fetch = async function (...args) {
      const response = await nativeFetch(...args);
      const url = String(args[0]?.url || args[0] || "");
      const map = [
        ["/api/ai/safety-plan", "ai_student", "학생별 안전계획 - 분석 완료", "/admin/ai-tools/student-plan"],
        ["/api/ai/daily-brief", "ai_daily", "오늘 위험 브리핑 - 분석 완료", "/admin/ai-tools/daily-brief"],
        ["/api/ai/menu-review", "ai_menu", "메뉴 코드 점검 - 분석 완료", "/admin/ai-tools/menu-review"],
      ];
      const match = map.find(([path]) => url.includes(path));
      if (match && response.ok) {
        response
          .clone()
          .json()
          .then((data) => {
            if (!data || data.ok === false) return;
            const item = {
              id: `${match[1]}:${Date.now()}`,
              target: match[1],
              path: match[3],
              icon: "AI",
              title: match[2],
              detail: "요청한 AI 분석 결과가 준비됐어.",
              time: nowTime(),
              kind: "ai",
            };
            if (typeof window.registerAdminNotification === "function") window.registerAdminNotification(item);
            else showWorkflowToast(item);
          })
          .catch(() => {});
      }
      return response;
    };
  }

  function installStudentImportTracking() {
    if (!window.fetch || window.__adminStudentImportTracking) return;
    window.__adminStudentImportTracking = true;
    const nativeFetch = window.fetch.bind(window);
    window.fetch = async function (...args) {
      const response = await nativeFetch(...args);
      const url = String(args[0]?.url || args[0] || "");
      if (url.includes("/api/student/sheet-confirm")) {
        response
          .clone()
          .json()
          .then((data) => {
            if (!data || !data.pending || !data.job_id) return;
            trackBackgroundJob({
              job_id: data.job_id,
              status_url: data.status_url,
              target: "student_manage",
              path: "/student-manage",
              icon: "ST",
              kind: "info",
              success_title: "학생관리 - 시트 대량 등록 완료",
              failure_title: "학생관리 - 시트 대량 등록 실패",
            });
            window.setTimeout(pollBackgroundJobs, 1200);
          })
          .catch(() => {});
      }
      return response;
    };
  }

  window.trackAdminBackgroundJob = trackBackgroundJob;
  window.showAdminWorkflowToast = showWorkflowToast;

  document.addEventListener("DOMContentLoaded", function () {
    wrapRegisterNotification();
    window.setTimeout(wrapRegisterNotification, 300);
    window.setTimeout(wrapRegisterNotification, 1200);
    wrapAiResultFetchToasts();
    installStudentImportTracking();
    installMealSaveAsync();
    refreshServerToasts();
    pollBackgroundJobs();
    window.setInterval(refreshServerToasts, 20000);
    window.setInterval(pollBackgroundJobs, 5000);
  });
})();
