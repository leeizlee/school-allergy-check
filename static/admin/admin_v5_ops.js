(function () {
  function enhanceOpsSidebar() {
    const systemGroup = Array.from(document.querySelectorAll(".nav-group")).find((group) => group.textContent.includes("Device"));
    const systemChildren = systemGroup && systemGroup.querySelector(".nav-children");
    if (systemChildren && !document.querySelector('a[href="/system-status"]')) {
      systemChildren.insertAdjacentHTML(
        "afterbegin",
        '<a class="nav-link" href="/system-status"><span class="nav-bullet"></span>시스템 상태</a><a class="nav-link" href="/audit-log"><span class="nav-bullet"></span>감사 로그</a>'
      );
    }
    if (systemGroup && ["/system-status", "/audit-log"].includes(window.location.pathname)) {
      systemGroup.classList.add("open");
      const button = systemGroup.querySelector("[data-nav-toggle]");
      if (button) button.setAttribute("aria-expanded", "true");
      const activeLink = systemGroup.querySelector(`a[href="${window.location.pathname}"]`);
      if (activeLink) activeLink.classList.add("active");
    }
  }

  document.addEventListener("DOMContentLoaded", enhanceOpsSidebar);
})();
