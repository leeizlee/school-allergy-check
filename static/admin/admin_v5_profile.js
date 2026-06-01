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
      + ".profile-uploader.profile-upload-card{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:16px 18px;margin:0 0 18px;border:1px solid var(--line-soft);border-radius:10px;background:#fff;box-shadow:0 1px 2px rgba(16,24,40,.05),0 14px 30px rgba(16,24,40,.06);}"
      + ".profile-upload-copy{min-width:0;display:flex;align-items:center;gap:13px;}.profile-upload-copy strong{display:block;font-size:15px;color:var(--text,#111827);}.profile-upload-copy small{display:block;color:var(--muted);margin-top:3px;line-height:1.45;}"
      + ".profile-upload-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap;justify-content:flex-end;}.profile-file-button{display:inline-flex;align-items:center;justify-content:center;min-height:38px;padding:0 14px;border-radius:8px;border:1px solid var(--line,#dfe5ee);background:#fff;color:#263548;font-weight:900;cursor:pointer;white-space:nowrap;}"
      + ".profile-file-button:hover{background:#f8fafc;}.profile-file-button input{display:none;}.profile-upload-status{display:block;flex-basis:100%;min-height:18px;color:var(--muted);font-size:12px;text-align:right;}"
      + ".profile-edit-backdrop{position:fixed;inset:0;z-index:1400;display:grid;place-items:center;padding:24px;background:rgba(15,23,42,.62);backdrop-filter:blur(4px);}"
      + ".profile-edit-modal{width:min(760px,calc(100vw - 32px));max-height:calc(100vh - 48px);overflow:auto;border:1px solid #d8e0ea;border-radius:12px;background:#fff;color:#111827;box-shadow:0 28px 90px rgba(15,23,42,.34);}"
      + ".profile-edit-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;padding:18px 20px;border-bottom:1px solid #edf1f6;background:linear-gradient(180deg,#fff,#f9fbfd);}.profile-edit-head h2{margin:0;font-size:18px;}.profile-edit-head p{margin:5px 0 0;color:#667085;font-size:13px;line-height:1.45;}"
      + ".profile-edit-close{width:34px;height:34px;border:1px solid #dfe5ee;border-radius:8px;background:#fff;color:#475467;font-size:18px;font-weight:900;line-height:1;}"
      + ".profile-edit-body{display:grid;grid-template-columns:300px minmax(0,1fr);gap:22px;padding:20px;align-items:center;}.profile-crop-stage{position:relative;width:280px;height:280px;margin:auto;border-radius:18px;overflow:hidden;background:#0f172a;box-shadow:inset 0 0 0 1px rgba(255,255,255,.16),0 14px 28px rgba(15,23,42,.18);}"
      + ".profile-crop-stage canvas{display:block;width:280px;height:280px;cursor:grab;touch-action:none;}.profile-crop-stage.is-dragging canvas{cursor:grabbing;}"
      + ".profile-crop-stage:after{content:'';position:absolute;inset:28px;border-radius:50%;border:2px solid rgba(255,255,255,.9);box-shadow:0 0 0 999px rgba(0,0,0,.34);pointer-events:none;}"
      + ".profile-crop-stage:before{content:'';position:absolute;inset:28px;background:linear-gradient(90deg,transparent 32.8%,rgba(255,255,255,.34) 33%,rgba(255,255,255,.34) 33.5%,transparent 33.7%,transparent 65.8%,rgba(255,255,255,.34) 66%,rgba(255,255,255,.34) 66.5%,transparent 66.7%),linear-gradient(0deg,transparent 32.8%,rgba(255,255,255,.34) 33%,rgba(255,255,255,.34) 33.5%,transparent 33.7%,transparent 65.8%,rgba(255,255,255,.34) 66%,rgba(255,255,255,.34) 66.5%,transparent 66.7%);border-radius:50%;pointer-events:none;z-index:2;}"
      + ".profile-crop-controls{display:grid;gap:12px;}.profile-crop-controls label{font-size:12px;font-weight:900;color:#667085;}.profile-crop-controls input[type='range']{width:100%;accent-color:#55c3aa;}.profile-crop-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:2px;}.profile-crop-status{display:block;min-height:18px;color:#667085;font-size:12px;line-height:1.45;}"
      + ".profile-edit-preview{display:flex;align-items:center;gap:10px;padding:12px;border:1px solid #edf1f6;border-radius:10px;background:#f8fafc;}.profile-edit-preview .profile-preview{width:54px;height:54px;font-size:18px;}.profile-edit-preview strong{display:block;font-size:13px;}.profile-edit-preview small{display:block;margin-top:3px;color:#667085;font-size:12px;}"
      + "body:not(.light-mode).admin-v5 .profile-uploader.profile-upload-card,body:not(.light-mode).admin-v5 .profile-edit-modal,body:not(.light-mode).admin-v5 .profile-edit-close{background:#172233;color:#eef4ff;border-color:#334155;}"
      + "body:not(.light-mode).admin-v5 .profile-upload-copy strong,body:not(.light-mode).admin-v5 .profile-edit-head h2,body:not(.light-mode).admin-v5 .profile-edit-preview strong{color:#eef4ff;}"
      + "body:not(.light-mode).admin-v5 .profile-file-button{background:#111827;color:#eef4ff;border-color:#334155;}body:not(.light-mode).admin-v5 .profile-file-button:hover{background:#1f2937;}"
      + "body:not(.light-mode).admin-v5 .profile-edit-head,body:not(.light-mode).admin-v5 .profile-edit-preview{background:#111827;border-color:#334155;}body:not(.light-mode).admin-v5 .profile-edit-head p,body:not(.light-mode).admin-v5 .profile-crop-controls label,body:not(.light-mode).admin-v5 .profile-crop-status,body:not(.light-mode).admin-v5 .profile-upload-status,body:not(.light-mode).admin-v5 .profile-edit-preview small{color:#a8b3c5;}"
      + "@media(max-width:760px){.profile-uploader.profile-upload-card,.profile-edit-body{grid-template-columns:1fr;flex-direction:column;align-items:stretch}.profile-upload-actions{justify-content:flex-start}.profile-upload-status{text-align:left}.profile-crop-stage{width:240px;height:240px}.profile-crop-stage canvas{width:240px;height:240px}}";
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

  function currentProfileSrc() {
    var current = document.querySelector(".topbar-avatar .avatar-img, .avatar-button .avatar-img");
    return current ? current.getAttribute("src") : "";
  }

  function resetCrop() {
    crop.scale = 1;
    crop.rotation = 0;
    crop.offsetX = 0;
    crop.offsetY = 0;
    crop.dragging = false;
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
    document.querySelectorAll("#profilePicturePreview").forEach(function (preview) {
      preview.innerHTML = avatarMarkup(src);
    });
  }

  function closeCropModal() {
    var modal = document.getElementById("profileCropModalBackdrop");
    if (modal) modal.remove();
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
      setTimeout(closeCropModal, 450);
    } catch (err) {
      status.textContent = err.message || "프로필 사진 저장에 실패했어.";
    } finally {
      saveButton.disabled = false;
    }
  }

  function wireCropInteractions(backdrop, file) {
    var canvas = backdrop.querySelector("#profileCropCanvas");
    var stage = backdrop.querySelector("#profileCropStage");
    var zoom = backdrop.querySelector("#profileCropZoom");
    var status = backdrop.querySelector("#profilePictureStatus");
    var saveButton = backdrop.querySelector("#profilePictureSaveBtn");

    draw(canvas);
    loadImage(file, canvas, status, zoom);

    zoom.addEventListener("input", function () {
      crop.scale = Number(zoom.value || 1);
      draw(canvas);
    });
    backdrop.querySelector("#profileRotateLeftBtn").addEventListener("click", function () {
      crop.rotation -= 90;
      draw(canvas);
    });
    backdrop.querySelector("#profileRotateRightBtn").addEventListener("click", function () {
      crop.rotation += 90;
      draw(canvas);
    });
    backdrop.querySelector("#profileCropCloseBtn").addEventListener("click", closeCropModal);
    backdrop.querySelector("#profileCropCancelBtn").addEventListener("click", closeCropModal);
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

  function openCropModal(file) {
    addStyle();
    closeCropModal();
    var backdrop = document.createElement("div");
    backdrop.id = "profileCropModalBackdrop";
    backdrop.className = "profile-edit-backdrop";
    backdrop.innerHTML = ""
      + '<section class="profile-edit-modal" role="dialog" aria-modal="true" aria-label="프로필 사진 편집">'
      + '<header class="profile-edit-head"><div><h2>프로필 사진 편집</h2><p>원형 아바타에 맞게 위치를 조정하고 확대/회전한 뒤 저장해.</p></div><button class="profile-edit-close" id="profileCropCloseBtn" type="button" aria-label="닫기">×</button></header>'
      + '<div class="profile-edit-body">'
      + '<div class="profile-crop-stage" id="profileCropStage"><canvas id="profileCropCanvas" width="360" height="360"></canvas></div>'
      + '<div class="profile-crop-controls">'
      + '<div class="profile-edit-preview"><div class="profile-preview" id="profilePicturePreview">' + avatarMarkup(currentProfileSrc()) + '</div><div><strong>원형 미리보기</strong><small>저장하면 모든 관리자 아바타에 바로 반영됩니다.</small></div></div>'
      + '<label>확대/축소<input id="profileCropZoom" type="range" min="1" max="3" step="0.01" value="1"></label>'
      + '<div class="profile-crop-actions">'
      + '<button class="btn btn-light" type="button" id="profileRotateLeftBtn">왼쪽 회전</button>'
      + '<button class="btn btn-light" type="button" id="profileRotateRightBtn">오른쪽 회전</button>'
      + '<button class="btn btn-light" type="button" id="profileCropCancelBtn">취소</button>'
      + '<button class="btn btn-primary" type="button" id="profilePictureSaveBtn">사진 저장</button>'
      + '</div><small class="profile-crop-status" id="profilePictureStatus">사진을 불러오는 중...</small>'
      + '</div></div></section>';
    document.body.appendChild(backdrop);
    wireCropInteractions(backdrop, file);
  }

  function enhanceProfileUploadCard() {
    var modal = document.getElementById("myAccountModal");
    var uploader = modal && modal.querySelector(".profile-uploader");
    if (!uploader || uploader.dataset.profileUploadEnhanced === "1") return;
    addStyle();

    uploader.dataset.profileUploadEnhanced = "1";
    uploader.className = "profile-uploader profile-upload-card";
    uploader.innerHTML = ""
      + '<div class="profile-upload-copy"><div class="profile-preview" id="profilePicturePreview">' + avatarMarkup(currentProfileSrc()) + '</div><div><strong>프로필 사진</strong><small>프로필사진 업로드를 누른 뒤 사진을 선택하면 편집 화면이 열립니다.</small></div></div>'
      + '<div class="profile-upload-actions"><label class="profile-file-button">프로필사진 업로드<input id="profilePictureInput" type="file" accept="image/*"></label><small class="profile-upload-status" id="profilePictureStatus">JPG, PNG 이미지를 사용할 수 있어.</small></div>';

    var input = uploader.querySelector("#profilePictureInput");
    var status = uploader.querySelector("#profilePictureStatus");
    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) return;
      status.textContent = file.name + " 선택됨. 편집 화면을 열었어.";
      openCropModal(file);
      input.value = "";
    });
  }

  function wrapAccountModal() {
    var previous = window.openMyAccountModal;
    window.openMyAccountModal = function () {
      if (typeof previous === "function") previous.apply(this, arguments);
      setTimeout(enhanceProfileUploadCard, 0);
    };
    setTimeout(enhanceProfileUploadCard, 0);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wrapAccountModal);
  } else {
    wrapAccountModal();
  }
})();
