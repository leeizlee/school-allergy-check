(function () {
  function $all(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function installThemeFixCss() {
    if (document.querySelector('link[data-admin-theme-fix="1"]')) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/static/admin/admin_theme_fix.css";
    link.setAttribute("data-admin-theme-fix", "1");
    document.head.appendChild(link);
  }

  function installProfilePreviewScript() {
    if (document.querySelector('script[data-profile-preview-fix="1"]')) return;
    const script = document.createElement("script");
    script.src = "/static/admin/profile_preview_fix.js";
    script.defer = true;
    script.setAttribute("data-profile-preview-fix", "1");
    document.head.appendChild(script);
  }

  installThemeFixCss();
  installProfilePreviewScript();

  function setStatus(node, message, ok) {
    if (!node) return;
    node.textContent = message || "";
    node.classList.toggle("profile-upload-ok", Boolean(ok));
    node.classList.toggle("profile-upload-error", ok === false);
  }

  function updateProfilePreview(file, preview, status) {
    if (!file) return;
    if (!file.type || !file.type.startsWith("image/")) {
      setStatus(status, "이미지 파일만 사용할 수 있어.", false);
      return;
    }
    const reader = new FileReader();
    reader.onload = function () {
      const url = String(reader.result || "");
      if (!url) {
        setStatus(status, "이미지를 읽지 못했어. 다른 파일로 시도해줘.", false);
        return;
      }
      if (preview) {
        preview.innerHTML = '<img class="profile-live-preview" src="' + url + '" alt="프로필 미리보기">';
      }
      setStatus(status, "미리보기 완료. 저장하면 상단 관리자 아바타에도 바로 반영돼.", true);
    };
    reader.onerror = function () {
      setStatus(status, "이미지 로드에 실패했어. 다른 파일로 시도해줘.", false);
    };
    reader.readAsDataURL(file);
  }

  function syncAvatarNodes(src) {
    if (!src) return;
    $all(".topbar-avatar,.avatar-button").forEach(function (button) {
      button.innerHTML = '<img class="avatar-img" src="' + src + '" alt="프로필">';
    });
    $all(".avatar-img").forEach(function (img) {
      img.src = src;
    });
    $all("#profilePicturePreview,.profile-preview").forEach(function (preview) {
      preview.innerHTML = '<img src="' + src + '" alt="프로필">';
    });
  }

  function installProfilePreviewFix() {
    document.addEventListener("change", function (event) {
      const input = event.target;
      if (!(input instanceof HTMLInputElement)) return;
      if (input.type !== "file" || !input.accept || !input.accept.includes("image")) return;
      const modal = input.closest(".modal-backdrop,.modal,.modal-card") || document;
      const preview = modal.querySelector("#profilePicturePreview,.profile-preview,.crop-preview,.profile-crop-preview,.profile-preview-surface");
      const status = modal.querySelector("#profilePictureStatus,.profile-status,.crop-status") || input.parentElement?.querySelector("small");
      const file = input.files && input.files[0];
      if (!file) return;
      updateProfilePreview(file, preview, status);
    }, true);

    document.addEventListener("click", async function (event) {
      const button = event.target.closest("#profilePictureSaveBtn,button");
      if (!button) return;
      const text = (button.textContent || "").trim();
      const looksLikeProfileSave = button.id === "profilePictureSaveBtn" || (text.includes("사진 저장") && button.closest(".profile-uploader,#myAccountModal"));
      if (!looksLikeProfileSave) return;
      const modal = button.closest(".modal-backdrop,.modal,.modal-card") || document;
      const input = modal.querySelector("#profilePictureInput,input[type='file'][accept*='image']");
      const preview = modal.querySelector("#profilePicturePreview,.profile-preview,.crop-preview,.profile-crop-preview,.profile-preview-surface");
      const status = modal.querySelector("#profilePictureStatus,.profile-status,.crop-status") || button.parentElement?.querySelector("small");
      const file = input && input.files && input.files[0];
      if (!file) return;
      event.preventDefault();
      event.stopPropagation();
      setStatus(status, "프로필 사진 저장 중...", true);
      try {
        const body = new FormData();
        body.append("picture", file);
        const res = await fetch("/api/my-account/picture", { method: "POST", body: body });
        const contentType = res.headers.get("content-type") || "";
        const data = contentType.includes("application/json") ? await res.json() : { ok: false, error: await res.text() };
        if (!res.ok || !data.ok) throw new Error(data.error || "프로필 사진 저장 실패");
        syncAvatarNodes(data.picture);
        if (preview) preview.innerHTML = '<img class="profile-live-preview" src="' + data.picture + '" alt="프로필">';
        setStatus(status, "프로필 사진이 저장됐어.", true);
      } catch (error) {
        setStatus(status, error.message || "프로필 사진 저장 실패", false);
      }
    }, true);
  }

  function installCardSelectionSync() {
    const update = function () {
      const selectionMode = !document.getElementById("studentCheckboxHeader")?.classList.contains("hidden");
      $all(".student-card").forEach(function (card) {
        card.classList.toggle("selection-visible", selectionMode);
      });
    };
    document.addEventListener("click", function (event) {
      if (event.target.closest("#toggleStudentDeleteModeBtn,#deleteSelectedStudentsBtn")) {
        setTimeout(update, 40);
      }
    });
    document.addEventListener("DOMContentLoaded", update);
  }

  function installCardFilterFallback() {
    if (typeof window.filterStudentRows === "function") return;
    window.filterStudentRows = function () {
      const active = document.querySelector(".js-student-filter.active")?.dataset.filter || "all";
      const query = (document.getElementById("studentSearchInput")?.value || "").trim().toLowerCase();
      let visibleCount = 0;
      $all(".student-data-row").forEach(function (row) {
        const hasAllergy = row.dataset.hasAllergy === "1";
        const hasRfid = row.dataset.hasRfid === "1";
        const matchesState = active === "all" || (active === "allergy" && hasAllergy) || (active === "no-allergy" && !hasAllergy) || (active === "rfid" && hasRfid) || (active === "no-rfid" && !hasRfid);
        const matchesQuery = !query || (row.dataset.search || "").includes(query);
        const visible = matchesState && matchesQuery;
        row.hidden = !visible;
        row.style.display = visible ? "" : "none";
        if (visible) visibleCount += 1;
      });
      const counter = document.getElementById("studentResultCount");
      if (counter) counter.textContent = String(visibleCount);
    };
  }

  function normalizeText(text) {
    return String(text || "").replace(/\s+/g, "");
  }

  function cleanupDuplicateNotificationLinks(root) {
    const links = $all("a.nav-link", root || document).filter(function (link) {
      return normalizeText(link.textContent).includes("알림센터");
    });
    links.forEach(function (link, index) {
      if (index > 0) link.remove();
    });
  }

  function installSidebarNotificationLink() {
    cleanupDuplicateNotificationLinks(document);
    const dashboards = document.querySelector(".gentelella-nav .nav-group .nav-children");
    if (dashboards) {
      const existing = $all("a.nav-link", dashboards).some(function (link) {
        return normalizeText(link.textContent).includes("알림센터") || link.href.endsWith("/admin/notifications");
      });
      if (!existing) {
        const link = document.createElement("a");
        link.className = "nav-link";
        link.href = "/admin/notifications";
        link.setAttribute("data-polish-notification-link", "1");
        link.innerHTML = '<span class="nav-bullet"></span>알림센터';
        dashboards.appendChild(link);
      }
    }

    const collapsed = document.querySelector(".collapsed-icon-nav");
    if (collapsed && !collapsed.querySelector("[data-polish-notification-link]")) {
      const link = document.createElement("a");
      link.className = "collapsed-icon-link";
      link.href = "/admin/notifications";
      link.title = "알림센터";
      link.setAttribute("aria-label", "알림센터");
      link.setAttribute("data-polish-notification-link", "1");
      link.innerHTML = '<svg><use href="#i-bell"></use></svg>';
      const firstDivider = collapsed.querySelector(".collapsed-icon-divider");
      collapsed.insertBefore(link, firstDivider || collapsed.children[2] || null);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    installProfilePreviewFix();
    installCardSelectionSync();
    installCardFilterFallback();
    installSidebarNotificationLink();
  });
})();