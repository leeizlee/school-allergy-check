(function () {
  "use strict";

  function injectAvatarFixStyle() {
    if (document.getElementById("admin-v5-avatar-fix-style")) return;
    var style = document.createElement("style");
    style.id = "admin-v5-avatar-fix-style";
    style.textContent = ""
      + ".admin-v5 .topbar-avatar,.admin-v5 .avatar-button,.admin-v5 .profile-preview{aspect-ratio:1/1;border-radius:999px!important;overflow:hidden!important;display:inline-grid;place-items:center;padding:0!important;line-height:1!important;flex:0 0 auto;}"
      + ".admin-v5 .topbar-avatar,.admin-v5 .avatar-button{width:38px!important;height:38px!important;min-width:38px!important;max-width:38px!important;background:#55c3aa;color:#fff;}"
      + ".admin-v5 .sidebar-account .avatar-button{width:42px!important;height:42px!important;min-width:42px!important;max-width:42px!important;}"
      + ".admin-v5 .topbar-avatar .avatar-img,.admin-v5 .avatar-button .avatar-img,.admin-v5 .profile-preview .avatar-img,.admin-v5 .profile-preview img{display:block!important;width:100%!important;height:100%!important;max-width:none!important;max-height:none!important;object-fit:cover!important;object-position:center center!important;border-radius:999px!important;}"
      + ".admin-v5 .profile-upload-card .profile-preview{width:74px!important;height:74px!important;min-width:74px!important;}"
      + ".admin-v5 .profile-edit-preview .profile-preview{width:54px!important;height:54px!important;min-width:54px!important;}";
    document.head.appendChild(style);
  }

  function textOf(root, selector) {
    var node = root.querySelector(selector);
    return node ? String(node.textContent || "").trim() : "";
  }

  function isBlank(value) {
    var text = String(value || "").trim();
    return !text || text === "-" || text === "?";
  }

  function removeBlankStudentCards() {
    document.querySelectorAll(".student-card").forEach(function (card) {
      var name = textOf(card, ".student-card-title strong");
      var number = textOf(card, ".student-number");
      var rfid = textOf(card, ".rfid-pill.safe");
      if (isBlank(name) && isBlank(number) && isBlank(rfid)) card.remove();
    });

    document.querySelectorAll(".person-list-card").forEach(function (card) {
      var name = textOf(card, ".person-title strong");
      var number = textOf(card, ".student-number, .rfid-pill");
      var sub = textOf(card, ".person-sub").replace(/\s/g, "");
      if (isBlank(name) && isBlank(number) && (sub.indexOf("-학년-반-번") >= 0 || sub.indexOf("--") >= 0)) card.remove();
    });

    var count = document.getElementById("studentResultCount");
    if (count) count.textContent = String(document.querySelectorAll(".student-card:not([style*='display: none'])").length);
  }

  function polishAccountModal() {
    var modal = document.getElementById("myAccountModal");
    if (!modal) return;
    modal.classList.add("account-modal-polished");
    injectAvatarFixStyle();
  }

  function boot() {
    injectAvatarFixStyle();
    removeBlankStudentCards();
    polishAccountModal();
    var previousOpen = window.openMyAccountModal;
    if (typeof previousOpen === "function" && !previousOpen.__cleanupWrapped) {
      var wrapped = function () {
        previousOpen.apply(this, arguments);
        setTimeout(function () {
          injectAvatarFixStyle();
          polishAccountModal();
          removeBlankStudentCards();
        }, 0);
      };
      wrapped.__cleanupWrapped = true;
      window.openMyAccountModal = wrapped;
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
