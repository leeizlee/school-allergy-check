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

  installThemeFixCss();

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

  function isNotificationHref(href) {
    try {
      const path = new URL(href, window.location.origin).pathname;
      return path === "/notifications" || path === "/admin/notifications";
    } catch (error) {
      return href === "/notifications" || href === "/admin/notifications";
    }
  }

  function isNotificationLink(link) {
    const href = link.getAttribute("href") || "";
    const label = normalizeText(link.textContent || link.title || link.getAttribute("aria-label") || "");
    return link.dataset.navId === "notifications" || isNotificationHref(href) || label.includes("알림센터");
  }

  function cleanupDuplicateNotificationLinks(root) {
    const sidebarLinks = $all(".gentelella-nav a.nav-link", root || document).filter(isNotificationLink);
    sidebarLinks.forEach(function (link, index) {
      if (index > 0) link.remove();
    });

    const collapsedLinks = $all(".collapsed-icon-nav a.collapsed-icon-link", root || document).filter(isNotificationLink);
    collapsedLinks.forEach(function (link, index) {
      if (index > 0) link.remove();
    });
  }

  function syncNotificationActiveState(link) {
    if (!link) return;
    const isCurrent = window.location.pathname === "/notifications" || window.location.pathname === "/admin/notifications";
    link.classList.toggle("active", isCurrent);
    const group = link.closest(".nav-group");
    if (group && isCurrent) {
      group.classList.add("open");
      group.querySelector("[data-nav-toggle]")?.setAttribute("aria-expanded", "true");
    }
  }

  function installSidebarNotificationLink() {
    cleanupDuplicateNotificationLinks(document);
    const sidebarLink = $all(".gentelella-nav a.nav-link").find(isNotificationLink);
    const collapsedLink = $all(".collapsed-icon-nav a.collapsed-icon-link").find(isNotificationLink);
    syncNotificationActiveState(sidebarLink);
    syncNotificationActiveState(collapsedLink);
  }

  document.addEventListener("DOMContentLoaded", function () {
    installCardSelectionSync();
    installCardFilterFallback();
    installSidebarNotificationLink();
  });
})();