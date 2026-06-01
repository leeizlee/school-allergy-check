(function () {
  "use strict";

  var styleId = "admin-v5-profile-style";
  var currentObjectUrl = "";
  var crop = {
    image: null,
    scale: 1,
    rotation: 0,
    offsetX: 0,
    offsetY: 0,
    dragging: false,
    lastX: 0,
    lastY: 0
  };

  function addStyle() {
    if (document.getElementById(styleId)) return;
    var style = document.createElement("style");
    style.id = styleId;
    style.textContent = ""
      + ".profile-uploader.profile-crop-enhanced{display:block;padding:18px;background:linear-gradient(180deg,rgba(85,195,170,.10),rgba(91,141,239,.07));}"
      + ".profile-crop-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;}"
      + ".profile-crop-head strong{font-size:15px;}.profile-crop-head small{display:block;color:var(--muted);margin-top:3px;}"
      + ".profile-crop-grid{display:grid;grid-template-columns:240px 1fr;gap:18px;align-items:center;}"
      + ".profile-crop-stage{position:relative;width:220px;height:220px;border-radius:18px;overflow:hidden;background:#0f172a;box-shadow:inset 0 0 0 1px rgba(255,255,255,.16),0 14px 28px rgba(15,23,42,.18);}"
      + ".profile-crop-stage canvas{display:block;width:220px;height:220px;cursor:grab;touch-action:none;}"
      + ".profile-crop-stage.is-dragging canvas{cursor:grabbing;}"
      + ".profile-crop-stage:after{content:'';position:absolute;inset:22px;border-radius:50%;border:2px solid rgba(255,255,255,.86);box-shadow:0 0 0 999px rgba(0,0,0,.34);pointer-events:none;}"
      + ".profile-crop-stage:before{content:'';position:absolute;inset:22px;background:linear-gradient(90deg,transparent 32.8%,rgba(255,255,255,.36) 33%,rgba(255,255,255,.36) 33.5%,transparent 33.7%,transparent 65.8%,rgba(255,255,255,.36) 66%,rgba(255,255,255,.36) 66.5%,transparent 66.7%),linear-gradient(0deg,transparent 32.8%,rgba(255,255,255,.36) 33%,rgba(255,255,255,.36) 33.5%,transparent 33.7%,transparent 65.8%,rgba(255,255,255,.36) 66%,rgba(255,255,255,.36) 66.5%,transparent 66.7%);border-radius:50%;pointer-events:none;z-index:2;}"
      + ".profile-crop-controls{display:grid;gap:10px;}.profile-crop-controls label{font-size:12px;font-weight:900;color:var(--muted);}"
      + ".profile-crop-controls input[type='range']{width:100%;}.profile-crop-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px;}"
      + ".profile-file-button{display:inline-flex;align-items:center;justify-content:center;min-height:36px;padding:0 12px;border-radius:8px;border:1px solid var(--line-soft);background:#fff;color:#263548;font-weight:900;cursor:pointer;}"
      + ".profile-file-button input{display:none;}.profile-crop-status{display:block;min-height:18px;color:var(--muted);font-size:12px;margin-top:6px;}"
      + "body:not(.light-mode).admin-v5 .profile-file-button{background:#111827;color:#eef4ff;border-color:#334155;}"
      + "body:not(.light-mode).admin-v5 .profile-uploader.profile-crop-enhanced{background:linear-gradient(180deg,rgba(85,195,170,.12),rgba(91,141,239,.10));}"
      + "@media(max-width:760px){.profile-crop-grid{grid-template-columns:1fr}.profile-crop-stage{margin:auto}}";
    document.head.appendChild(style);
  }

  function showToast(message) {
    var old = document.querySelector(".admin-toast");
    if (old) old.remove();
    var toast = document.createElement("div");
    toast.className = "admin-toast";
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(function () { toast.remove(); }, 2400);
  }

  function avatarMarkup(src, fallback) {
    if (src) return '<img class="avatar-img" src="' + src + '" alt="프로필">';
    return fallback || "관";
  }

  function draw(canvas) {
    var ctx = canvas.getContext("2d");
    var size = canvas.width;
    ctx.clearRect(0, 0, size, size);
    ctx.fillStyle = "#111827";
    ctx.fillRect(0, 0, size, size);
    if (!crop.image) {
      ctx.fillStyle = "#94a3b8";
      ctx.font = "700 13px system-ui, -apple-system, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("사진을 선택해줘", size / 2, size / 2);
      return;
    }

    var image = crop.image;
    var base = Math.max(size / image.width, size / image.height) * crop.scale;
    var width = image.width * base;
    var height = image.height * base;
    ctx.save();
    ctx.translate(size / 2 + crop.offsetX, size / 2 + crop.offsetY);
    ctx.rotate(crop.rotation * Math.PI / 180);
    ctx.drawImage(image, -width / 2, -height / 2, width, height);
    ctx.restore();
  }

  function resetCrop() {
    crop.scale = 1;
    crop.rotation = 0;
    crop.offsetX = 0;
    crop.offsetY = 0;
  }

  function loadImage(file, canvas, status, zoom) {
    if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl);
    currentObjectUrl = URL.createObjectURL(file);
    var image = new Image();
    image.onload = function () {
      crop.image = image;
      resetCrop();
      zoom.value = "1";
      draw(canvas);
      status.textContent = "드래그로 위치를 맞추고, 확대/회전 후 저장하면 돼.";
    };
    image.onerror = function () {
      status.textContent = "이미지를 읽지 못했어. 다른 파일로 시도해줘.";
    };
    image.src = currentObjectUrl;
  }

  function updateAllAvatars(src) {
    document.querySelectorAll(".avatar-img").forEach(function (img) {
      img.src = src;
    });
    document.querySelectorAll(".topbar-avatar,.avatar-button").forEach(function (button) {
      button.innerHTML = avatarMarkup(src);
    });
    var preview = document.querySelector("#profilePicturePreview");
    if (preview) preview.innerHTML = '<img src="' + src + '" alt="프로필">';
  }

  async function saveCropped(canvas, status, saveButton) {
    if (!crop.image) {
      status.textContent = "먼저 사진을 선택해줘.";
      return;
    }
    saveButton.disabled = true;
    status.textContent = "프로필 사진 저장 중...";
    try {
      var body = new FormData();
      body.append("picture_data", canvas.toDataURL("image/jpeg", 0.9));
      var res = await fetch("/api/my-account/picture", { method: "POST", body: body });
      var contentType = res.headers.get("content-type") || "";
      var data = contentType.indexOf("application/json") >= 0
        ? await res.json()
        : { ok: false, error: await res.text() };
      if (!res.ok || !data.ok) throw new Error(data.error || "프로필 사진 저장에 실패했어.");
      updateAllAvatars(data.picture);
      status.textContent = "프로필 사진이 저장됐어.";
      showToast("프로필 사진 저장 완료");
    } catch (err) {
      status.textContent = err.message || "프로필 사진 저장에 실패했어.";
    } finally {
      saveButton.disabled = false;
    }
  }

  function enhanceProfileCropper() {
    var modal = document.getElementById("myAccountModal");
    var uploader = modal && modal.querySelector(".profile-uploader");
    if (!uploader || uploader.dataset.cropEnhanced === "1") return;
    addStyle();

    var current = document.querySelector(".topbar-avatar .avatar-img, .avatar-button .avatar-img");
    var currentSrc = current ? current.getAttribute("src") : "";
    uploader.dataset.cropEnhanced = "1";
    uploader.classList.add("profile-crop-enhanced");
    uploader.innerHTML = ""
      + '<div class="profile-crop-head"><div><strong>프로필 사진</strong><small>사진을 고른 뒤 원형 영역에 맞게 자르고 저장해.</small></div><div class="profile-preview" id="profilePicturePreview">' + avatarMarkup(currentSrc) + '</div></div>'
      + '<div class="profile-crop-grid">'
      + '<div class="profile-crop-stage" id="profileCropStage"><canvas id="profileCropCanvas" width="320" height="320"></canvas></div>'
      + '<div class="profile-crop-controls">'
      + '<label class="profile-file-button">사진 선택<input id="profilePictureInput" type="file" accept="image/*"></label>'
      + '<label>확대/축소<input id="profileCropZoom" type="range" min="1" max="3" step="0.01" value="1"></label>'
      + '<div class="profile-crop-actions">'
      + '<button class="btn btn-light" type="button" id="profileRotateLeftBtn">왼쪽 회전</button>'
      + '<button class="btn btn-light" type="button" id="profileRotateRightBtn">오른쪽 회전</button>'
      + '<button class="btn btn-primary" type="button" id="profilePictureSaveBtn">사진 저장</button>'
      + '</div><small class="profile-crop-status" id="profilePictureStatus">사진을 선택하면 여기서 자르기와 회전을 할 수 있어.</small>'
      + '</div></div>';

    var canvas = uploader.querySelector("#profileCropCanvas");
    var stage = uploader.querySelector("#profileCropStage");
    var input = uploader.querySelector("#profilePictureInput");
    var zoom = uploader.querySelector("#profileCropZoom");
    var status = uploader.querySelector("#profilePictureStatus");
    var saveButton = uploader.querySelector("#profilePictureSaveBtn");

    draw(canvas);
    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) return;
      loadImage(file, canvas, status, zoom);
    });
    zoom.addEventListener("input", function () {
      crop.scale = Number(zoom.value || 1);
      draw(canvas);
    });
    uploader.querySelector("#profileRotateLeftBtn").addEventListener("click", function () {
      crop.rotation -= 90;
      draw(canvas);
    });
    uploader.querySelector("#profileRotateRightBtn").addEventListener("click", function () {
      crop.rotation += 90;
      draw(canvas);
    });
    saveButton.addEventListener("click", function () {
      saveCropped(canvas, status, saveButton);
    });

    canvas.addEventListener("pointerdown", function (event) {
      crop.dragging = true;
      crop.lastX = event.clientX;
      crop.lastY = event.clientY;
      stage.classList.add("is-dragging");
      canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener("pointermove", function (event) {
      if (!crop.dragging) return;
      crop.offsetX += event.clientX - crop.lastX;
      crop.offsetY += event.clientY - crop.lastY;
      crop.lastX = event.clientX;
      crop.lastY = event.clientY;
      draw(canvas);
    });
    canvas.addEventListener("pointerup", function (event) {
      crop.dragging = false;
      stage.classList.remove("is-dragging");
      try { canvas.releasePointerCapture(event.pointerId); } catch (err) {}
    });
    canvas.addEventListener("pointercancel", function () {
      crop.dragging = false;
      stage.classList.remove("is-dragging");
    });
  }

  function wrapAccountModal() {
    var previous = window.openMyAccountModal;
    window.openMyAccountModal = function () {
      if (typeof previous === "function") previous.apply(this, arguments);
      setTimeout(enhanceProfileCropper, 0);
    };
    setTimeout(enhanceProfileCropper, 0);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wrapAccountModal);
  } else {
    wrapAccountModal();
  }
})();
