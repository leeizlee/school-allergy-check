(function () {
  "use strict";

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
  }

  function boot() {
    removeBlankStudentCards();
    polishAccountModal();
    var previousOpen = window.openMyAccountModal;
    if (typeof previousOpen === "function" && !previousOpen.__cleanupWrapped) {
      var wrapped = function () {
        previousOpen.apply(this, arguments);
        setTimeout(function () {
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
