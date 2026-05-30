(() => {
  function initSidebar() {
    const toggle = document.getElementById("adminSidebarToggle");
    const backdrop = document.querySelector("[data-sidebar-close]");
    const sidebar = document.getElementById("adminSidebar");
    if (!toggle || !sidebar) return;

    const close = () => {
      document.body.classList.remove("gt-nav-open");
      toggle.setAttribute("aria-expanded", "false");
    };

    const open = () => {
      document.body.classList.add("gt-nav-open");
      toggle.setAttribute("aria-expanded", "true");
    };

    toggle.addEventListener("click", () => {
      if (document.body.classList.contains("gt-nav-open")) {
        close();
      } else {
        open();
      }
    });

    backdrop?.addEventListener("click", close);
    sidebar.querySelectorAll("a").forEach((link) => link.addEventListener("click", close));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
    });
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

  function init() {
    initSidebar();
    enhanceLogin();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
