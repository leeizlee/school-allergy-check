(() => {
  const SHELL_STYLE_ID = "gt-admin-shell-runtime-style";
  const SIDEBAR_STATE_KEY = "gtAdminSidebarOpen";

  const shellCss = `
    body.gt-admin-shell-ready { margin: 0; overflow-x: hidden; }
    .gt-layout {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 242px minmax(0, 1fr);
      background: var(--bg, #f5f7fb);
      color: var(--text, #0f172a);
    }
    .gt-sidebar {
      position: sticky;
      top: 0;
      height: 100vh;
      overflow-y: auto;
      background: var(--gt-sidebar, #1f2937);
      border-right: 1px solid var(--gt-sidebar-line, rgba(255,255,255,.1));
      padding: 14px 10px;
      z-index: 40;
    }
    .gt-brand {
      display: flex;
      align-items: center;
      gap: 10px;
      min-height: 44px;
      padding: 4px 2px 18px;
      margin: 0 0 12px;
      color: #fff;
      border-bottom: 1px solid var(--gt-sidebar-line, rgba(255,255,255,.1));
      font-size: 15px;
      font-weight: 800;
    }
    .gt-brand-mark {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 30px;
      height: 30px;
      border-radius: 7px;
      background: var(--gt-accent, #1abb9c);
      color: #fff;
      font-weight: 900;
      box-shadow: 0 8px 18px rgba(26,187,156,.24);
    }
    .gt-sidebar .section-title {
      color: var(--gt-sidebar-muted, #8290a6) !important;
      margin: 22px 10px 8px !important;
      letter-spacing: .04em !important;
    }
    .gt-sidebar .menu-link {
      padding: 10px 12px !important;
      border-radius: 6px !important;
      color: var(--gt-sidebar-text, #d7e3f1) !important;
      font-size: 14px;
      font-weight: 600 !important;
    }
    .gt-sidebar .menu-link:hover {
      background: var(--gt-sidebar-hover, rgba(255,255,255,.07)) !important;
      color: #fff !important;
      border-color: transparent !important;
    }
    .gt-sidebar .menu-link.active {
      background: var(--gt-sidebar-active, #253546) !important;
      color: #fff !important;
      border-color: transparent !important;
      box-shadow: inset 3px 0 0 var(--gt-accent, #1abb9c);
    }
    .gt-main { min-width: 0; display: flex; flex-direction: column; }
    .gt-topbar {
      position: sticky;
      top: 0;
      z-index: 30;
      min-height: 52px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 0 24px;
      background: var(--topbar, #fff);
      border-bottom: 1px solid var(--line, #dfe5ec);
      box-shadow: var(--card-shadow-soft, 0 4px 14px rgba(15,23,42,.06));
    }
    .gt-topbar-left { min-width: 0; display: flex; align-items: center; gap: 12px; }
    .gt-menu-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 34px;
      height: 34px;
      border: 1px solid var(--line, #dfe5ec);
      border-radius: 6px;
      background: var(--card-2, #f8fafc);
      color: var(--text, #0f172a);
      cursor: pointer;
      font-size: 18px;
      line-height: 1;
    }
    .gt-page-heading { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
    .gt-page-title { font-size: 18px; font-weight: 800; color: var(--text, #0f172a); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .gt-page-sub { color: var(--muted, #667085); font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .gt-topbar-actions { display: flex; align-items: center; justify-content: flex-end; gap: 10px; flex-wrap: wrap; }
    .gt-content { min-width: 0; width: 100%; padding: 24px; }
    .gt-content > .panel { max-width: 1560px !important; }
    .gt-backdrop { display: none; }
    body.gt-login-enhanced .login-btn.is-loading { opacity: .75; cursor: wait; }
    body.gt-login-enhanced .login-card { overflow: hidden; }
    @media (max-width: 1100px) {
      .gt-layout { grid-template-columns: 1fr; }
      .gt-sidebar {
        position: fixed;
        inset: 0 auto 0 0;
        width: min(82vw, 290px);
        transform: translateX(-102%);
        transition: transform .2s ease;
        box-shadow: 20px 0 40px rgba(15,23,42,.22);
      }
      body.gt-nav-open .gt-sidebar { transform: translateX(0); }
      .gt-backdrop {
        display: block;
        position: fixed;
        inset: 0;
        background: rgba(15,23,42,.45);
        z-index: 35;
        opacity: 0;
        pointer-events: none;
        transition: opacity .2s ease;
      }
      body.gt-nav-open .gt-backdrop { opacity: 1; pointer-events: auto; }
      .gt-topbar { min-height: auto; padding: 14px 16px; align-items: flex-start; flex-direction: column; }
      .gt-topbar-left, .gt-topbar-actions { width: 100%; }
      .gt-content { padding: 16px; }
    }
  `;

  function addRuntimeStyle() {
    if (document.getElementById(SHELL_STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = SHELL_STYLE_ID;
    style.textContent = shellCss;
    document.head.appendChild(style);
  }

  function makeButton(label) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "gt-menu-btn";
    button.setAttribute("aria-label", label);
    button.textContent = "☰";
    return button;
  }

  function moveChildren(from, to) {
    while (from && from.firstChild) {
      to.appendChild(from.firstChild);
    }
  }

  function cloneNav(oldSidebar) {
    const nav = document.createElement("nav");
    nav.className = "gt-nav";
    if (!oldSidebar) return nav;

    oldSidebar.querySelectorAll(".section-title, .menu-list").forEach((node) => {
      nav.appendChild(node.cloneNode(true));
    });
    return nav;
  }

  function mountAdminShell() {
    const oldLayout = document.querySelector(".layout");
    const oldSidebar = oldLayout?.querySelector(".sidebar");
    const oldTopbar = oldLayout?.querySelector(".topbar");
    const oldContent = oldLayout?.querySelector(".content");
    if (!oldLayout || !oldSidebar || !oldTopbar || !oldContent || document.querySelector(".gt-layout")) {
      return false;
    }

    const pageTitle = oldTopbar.querySelector(".page-title")?.textContent?.trim() || document.title || "Admin";
    const pageSub = oldTopbar.querySelector(".page-sub")?.textContent?.trim() || "";
    const actionSource = oldTopbar.querySelector(".topbar-right");

    const layout = document.createElement("div");
    layout.className = "gt-layout";

    const sidebar = document.createElement("aside");
    sidebar.className = "gt-sidebar";
    sidebar.innerHTML = `<div class="gt-brand"><span class="gt-brand-mark">A</span><span>급식 알레르기 Admin</span></div>`;
    sidebar.appendChild(cloneNav(oldSidebar));

    const backdrop = document.createElement("div");
    backdrop.className = "gt-backdrop";

    const main = document.createElement("section");
    main.className = "gt-main";

    const topbar = document.createElement("header");
    topbar.className = "gt-topbar";

    const topbarLeft = document.createElement("div");
    topbarLeft.className = "gt-topbar-left";
    const menuButton = makeButton("Open navigation");
    const heading = document.createElement("div");
    heading.className = "gt-page-heading";
    heading.innerHTML = `<div class="gt-page-title"></div><div class="gt-page-sub"></div>`;
    heading.querySelector(".gt-page-title").textContent = pageTitle;
    heading.querySelector(".gt-page-sub").textContent = pageSub;
    topbarLeft.append(menuButton, heading);

    const topbarActions = document.createElement("div");
    topbarActions.className = "gt-topbar-actions";
    moveChildren(actionSource, topbarActions);

    topbar.append(topbarLeft, topbarActions);

    const content = document.createElement("main");
    content.className = "gt-content";
    moveChildren(oldContent, content);

    main.append(topbar, content);
    layout.append(sidebar, backdrop, main);
    oldLayout.replaceWith(layout);

    document.body.classList.add("gt-admin-shell-ready");

    const closeNav = () => document.body.classList.remove("gt-nav-open");
    menuButton.addEventListener("click", () => document.body.classList.toggle("gt-nav-open"));
    backdrop.addEventListener("click", closeNav);
    sidebar.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeNav));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeNav();
    });

    try {
      sessionStorage.setItem(SIDEBAR_STATE_KEY, "ready");
    } catch (_error) {}

    return true;
  }

  function enhanceLogin() {
    const form = document.querySelector(".login-card form");
    if (!form) return;
    document.body.classList.add("gt-login-enhanced");
    form.addEventListener("submit", () => {
      const button = form.querySelector(".login-btn");
      if (!button) return;
      button.classList.add("is-loading");
      button.setAttribute("aria-busy", "true");
      button.textContent = "로그인 중...";
    });
  }

  function enhanceStudentAndKiosk() {
    if (document.querySelector(".page > .grid")) {
      document.body.classList.add("gt-student-home-ready");
    }
    if (document.querySelector(".wrap .waiting-card")) {
      document.body.classList.add("gt-kiosk-ready");
    }
  }

  function init() {
    addRuntimeStyle();
    mountAdminShell();
    enhanceLogin();
    enhanceStudentAndKiosk();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
