(() => {
  function makeMenuButton(label) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "gt-menu-btn";
    button.setAttribute("aria-label", label);
    button.textContent = "\u2630";
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

  function createBrand() {
    const brand = document.createElement("div");
    brand.className = "gt-brand";

    const mark = document.createElement("span");
    mark.className = "gt-brand-mark";
    mark.textContent = "A";

    const text = document.createElement("span");
    text.textContent = "\uae09\uc2dd \uc54c\ub808\ub974\uae30 Admin";

    brand.append(mark, text);
    return brand;
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
    sidebar.append(createBrand(), cloneNav(oldSidebar));

    const backdrop = document.createElement("div");
    backdrop.className = "gt-backdrop";

    const main = document.createElement("section");
    main.className = "gt-main";

    const topbar = document.createElement("header");
    topbar.className = "gt-topbar";

    const topbarLeft = document.createElement("div");
    topbarLeft.className = "gt-topbar-left";

    const menuButton = makeMenuButton("Open navigation");
    const heading = document.createElement("div");
    heading.className = "gt-page-heading";

    const title = document.createElement("div");
    title.className = "gt-page-title";
    title.textContent = pageTitle;

    const subtitle = document.createElement("div");
    subtitle.className = "gt-page-sub";
    subtitle.textContent = pageSub;

    heading.append(title, subtitle);
    topbarLeft.append(menuButton, heading);

    const topbarActions = document.createElement("div");
    topbarActions.className = "gt-topbar-actions";
    moveChildren(actionSource, topbarActions);

    const content = document.createElement("main");
    content.className = "gt-content";
    moveChildren(oldContent, content);

    topbar.append(topbarLeft, topbarActions);
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
      button.textContent = "\ub85c\uadf8\uc778 \uc911...";
    });
  }

  function enhanceStandalonePages() {
    if (document.querySelector(".page > .grid")) {
      document.body.classList.add("gt-student-home-ready");
    }
    if (document.querySelector(".wrap .waiting-card")) {
      document.body.classList.add("gt-kiosk-ready");
    }
  }

  function init() {
    mountAdminShell();
    enhanceLogin();
    enhanceStandalonePages();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
