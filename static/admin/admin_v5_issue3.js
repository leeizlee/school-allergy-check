(function () {
  "use strict";

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  async function readJsonResponse(res) {
    var contentType = res.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      var text = await res.text().catch(function () { return ""; });
      throw new Error(text || "서버가 JSON이 아닌 응답을 반환했어.");
    }
    var data = await res.json();
    if (!res.ok || data.ok === false) throw new Error(data.error || data.message || "요청 처리에 실패했어.");
    return data;
  }

  function setStatus(message, kind) {
    var node = document.getElementById("aiStatusBox");
    if (!node) return;
    node.classList.remove("hidden", "safe", "danger", "warn", "info");
    node.classList.add(kind || "info");
    node.textContent = message || "";
  }

  function installModalGuard() {
    function sync() {
      var open = Array.from(document.querySelectorAll(".modal-backdrop")).some(function (modal) {
        return !modal.classList.contains("hidden");
      });
      document.body.classList.toggle("modal-open", open);
    }
    document.addEventListener("click", function (event) {
      var backdrop = event.target.closest(".modal-backdrop");
      if (backdrop && event.target === backdrop) {
        event.preventDefault();
        event.stopPropagation();
      }
      window.setTimeout(sync, 0);
    }, true);
    new MutationObserver(sync).observe(document.body, { subtree: true, attributes: true, attributeFilter: ["class"] });
    sync();
  }

  window.requestAlternativeMeal = async function () {
    var student = document.getElementById("aiStudentSelect");
    var date = document.getElementById("aiDateSelect");
    var context = document.getElementById("aiContextInput");
    var result = document.getElementById("aiAlternativeResult");
    if (!student || !student.value) {
      setStatus("대체급식을 추천할 학생을 먼저 선택해줘.", "warn");
      return;
    }
    setStatus("대체급식 추천안을 만들고 검토 대기함에 등록하고 있어.", "info");
    if (result) result.innerHTML = '<div class="loading-panel"><span class="spinner"></span><strong>대체급식 추천 분석 중</strong><p>추천 결과는 바로 실제 급식에 반영되지 않고 검토 대기함으로 이동합니다.</p></div>';
    try {
      var res = await fetch("/api/ai/alternative-meal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          student_number: student.value,
          date: date ? date.value : "",
          context: context ? context.value : ""
        })
      });
      var data = await readJsonResponse(res);
      var item = data.result || {};
      if (result) {
        result.innerHTML = ''
          + '<div class="alert-panel warn"><span class="alert-icon">RV</span><div><strong>' + escapeHtml(item.menu_name || "대체급식 추천안") + '</strong>'
          + '<p>' + escapeHtml(item.components || item.reason || "관리자 확인이 필요합니다.") + '</p>'
          + '<div class="button-row"><a class="btn btn-primary" href="' + escapeHtml(data.review_url || "/admin/review-queue") + '">검토 대기함 열기</a></div></div></div>';
      }
      setStatus("추천안이 검토 대기함에 등록됐어. 승인 전에는 food_menu에 반영되지 않아.", "safe");
    } catch (error) {
      if (result) result.innerHTML = '<div class="alert-panel danger"><span class="alert-icon">!</span><div><strong>대체급식 추천 실패</strong><p>' + escapeHtml(error.message) + '</p></div></div>';
      setStatus(error.message || "대체급식 추천에 실패했어.", "danger");
    }
  };

  function reviewPayload(card) {
    return {
      menu_name: card.querySelector('[data-review-field="menu_name"]')?.value || "",
      date: card.querySelector('[data-review-field="date"]')?.value || "",
      target: card.querySelector('[data-review-field="target"]')?.value || "",
      allergy_codes: card.querySelector('[data-review-field="allergy_codes"]')?.value || ""
    };
  }

  async function handleReviewAction(button) {
    var card = button.closest("[data-review-id]");
    if (!card) return;
    var itemId = card.dataset.reviewId;
    var action = button.dataset.reviewAction;
    var body = action === "approve" ? reviewPayload(card) : { reason: window.prompt("반려 사유를 입력해줘.", "담당자 재검토 필요") || "" };
    if (action === "reject" && !body.reason) return;
    var message = action === "approve" ? "수정된 내용을 승인하고 food_menu에 반영할까?" : "이 추천안을 반려할까?";
    if (!window.confirm(message)) return;
    button.disabled = true;
    try {
      var res = await fetch("/api/admin/review-queue/" + encodeURIComponent(itemId) + "/" + action, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      await readJsonResponse(res);
      window.location.reload();
    } catch (error) {
      window.alert(error.message || "검토 작업에 실패했어.");
      button.disabled = false;
    }
  }

  function installReviewActions() {
    document.addEventListener("click", function (event) {
      var button = event.target.closest("[data-review-action]");
      if (button) handleReviewAction(button);
    });
  }

  function installKioskAlternativePanel() {
    if (window.location.pathname !== "/kiosk" || typeof window.renderDetected !== "function") return;
    var original = window.renderDetected;
    window.renderDetected = function (data) {
      original(data);
      var card = document.getElementById("detected");
      if (!card) return;
      var panel = document.getElementById("kioskAlternativeMeals");
      if (!panel) {
        panel = document.createElement("div");
        panel.id = "kioskAlternativeMeals";
        panel.className = "kiosk-alternative-box";
        card.appendChild(panel);
      }
      var items = Array.isArray(data.alternative_meals) ? data.alternative_meals : [];
      if (!items.length) {
        panel.hidden = true;
        return;
      }
      panel.hidden = false;
      panel.innerHTML = '<strong>대체급식 있음 · 담당자 확인 필요</strong><ul>'
        + items.map(function (item) { return '<li>' + escapeHtml(item.menu_name || "대체급식") + ' <small>(' + escapeHtml(item.allergy_names || "코드 확인 필요") + ')</small></li>'; }).join("")
        + '</ul>';
    };
  }

  document.addEventListener("DOMContentLoaded", function () {
    installModalGuard();
    installReviewActions();
    installKioskAlternativePanel();
  });
})();
