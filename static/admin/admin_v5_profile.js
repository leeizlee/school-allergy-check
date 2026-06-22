(function () {
  "use strict";

  window.__adminV5ProfileUploadReady = true;

  var pendingPictureData = "";
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
    if (document.getElementById("admin-v5-profile-stage-style")) return;
    var style = document.createElement("style");
    style.id = "admin-v5-profile-stage-style";
    style.textContent = ""
      + ".profile-edit-backdrop{position:fixed;inset:0;z-index:1400;display:grid;place-items:center;padding:24px;background:rgba(15,23,42,.62);backdrop-filter:blur(4px);}"
      + ".profile-edit-modal{width:min(760px,calc(100vw - 32px));max-height:calc(100vh - 48px);overflow:auto;border:1px solid var(--ui-border,#d8e0ea);border-radius:12px;background:var(--ui-surface,#fff);color:var(--ui-text,#111827);box-shadow:0 28px 90px rgba(15,23,42,.34);}"
      + ".profile-edit-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;padding:18px 20px;border-bottom:1px solid var(--ui-border-soft,#edf1f6);background:var(--ui-surface-soft,#f9fbfd);}.profile-edit-head h2{margin:0;font-size:18px;font-weight:750}.profile-edit-head p{margin:5px 0 0;color:var(--ui-muted,#667085);font-size:13px;line-height:1.45}"
      + ".profile-edit-close{width:34px;height:34px;border:1px solid var(--ui-border,#dfe5ee);border-radius:8px;background:var(--ui-surface,#fff);color:var(--ui-text,#475467);font-size:18px;font-weight:800;line-height:1}"
      + ".profile-edit-body{display:grid;grid-template-columns:300px minmax(0,1fr);gap:22px;padding:20px;align-items:center}.profile-crop-stage{position:relative;width:280px;height:280px;margin:auto;border-radius:18px;overflow:hidden;background:#0f172a;box-shadow:inset 0 0 0 1px rgba(255,255,255,.16),0 14px 28px rgba(15,23,42,.18)}"
      + ".profile-crop-stage canvas{display:block;width:280px;height:280px;cursor:grab;touch-action:none}.profile-crop-stage.is-dragging canvas{cursor:grabbing}"
      + ".profile-crop-stage:after{content:'';position:absolute;inset:28px;border-radius:50%;border:2px solid rgba(255,255,255,.9);box-shadow:0 0 0 999px rgba(0,0,0,.34);pointer-events:none}.profile-crop-stage:before{content:'';position:absolute;inset:28px;background:linear-gradient(90deg,transparent 32.8%,rgba(255,255,255,.34) 33%,rgba(255,255,255,.34) 33.5%,transparent 33.7%,transparent 65.8%,rgba(255,255,255,.34) 66%,rgba(255,255,255,.34) 66.5%,transparent 66.7%),linear-gradient(0deg,transparent 32.8%,rgba(255,255,255,.34) 33%,rgba(255,255,255,.34) 33.5%,transparent 33.7%,transparent 65.8%,rgba(255,255,255,.34) 66%,rgba(255,255,255,.34) 66.5%,transparent 66.7%);border-radius:50%;pointer-events:none;z-index:2}"
      + ".profile-crop-controls{display:grid;gap:12px;padding:14px;border:1px solid var(--ui-border-soft,#edf1f6);border-radius:10px;background:var(--ui-surface-soft,#f8fafc)}.profile-crop-controls label{font-size:12px;font-weight:800;color:var(--ui-muted,#667085)}.profile-crop-controls input[type='range']{width:100%;accent-color:#55c3aa}.profile-crop-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:2px}.profile-crop-status{display:block;min-height:18px;color:var(--ui-muted,#667085);font-size:12px;line-height:1.45}"
      + ".profile-edit-preview{display:flex;align-items:center;gap:10px;padding:12px;border:1px solid var(--ui-border-soft,#edf1f6);border-radius:10px;background:var(--ui-surface,#fff)}.profile-edit-preview .profile-preview{width:54px;height:54px;font-size:18px}.profile-edit-preview strong{display:block;font-size:13px;color:var(--ui-text,#111827)}.profile-edit-preview small{display:block;margin-top:3px;color:var(--ui-muted,#667085);font-size:12px}"
      + "@media(max-width:760px){.profile-edit-body{grid-template-columns:1fr}.profile-crop-stage{width:240px;height:240px}.profile-crop-stage canvas{width:240px;height:240px}}";
    document.head.appendChild(style);
  }

  function toast(message) {
    var old = document.querySelector(".admin-toast");
    if (old) old.remove();
    var node = document.createElement("div");
    node.className = "admin-toast";
    node.textContent = message;
    document.body.appendChild(node);
    setTimeout(function () { node.remove(); }, 2400);
  }

  function currentInitial() {
    var btn = document.querySelector(".topbar-avatar, .avatar-button");
    var text = btn ? String(btn.textContent || "").trim() : "";
    return text ? text.slice(0, 1) : "관";
  }

  function currentImage() {
    var img = document.querySelector(".topbar-avatar .avatar-img, .avatar-button .avatar-img");
    return img ? img.getAttribute("src") : "";
  }

  function avatar(src) {
    return src ? '<img class="avatar-img" src="' + src + '" alt="프로필">' : currentInitial();
  }

  function setAccountPreview(src) {
    document.querySelectorAll("#myAccountModal #profilePicturePreview").forEach(function (preview) {
      preview.innerHTML = avatar(src);
    });
  }

  function discardPendingPicture() {
    pendingPictureData = "";
    setAccountPreview(currentImage());
    var status = document.querySelector("#myAccountModal #profilePictureStatus");
    if (status) status.textContent = "PNG, JPG, WEBP, GIF 이미지를 사용할 수 있어.";
  }

  function updateAllAvatars(src) {
    document.querySelectorAll(".topbar-avatar,.avatar-button").forEach(function (btn) {
      btn.innerHTML = avatar(src);
    });
    setAccountPreview(src);
  }

  function isImageFile(file) {
    if (!file) return false;
    if ((file.type || "").indexOf("image/") === 0) return true;
    return /\.(png|jpe?g|jpe|webp|gif)$/i.test(file.name || "");
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
      ctx.fillText("사진을 불러오는 중...", size / 2, size / 2);
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

  function loadSelectedImage(file, canvas, status, zoom, backdrop) {
    status.textContent = "사진을 불러오는 중...";
    var reader = new FileReader();
    reader.onload = function () {
      var src = String(reader.result || "");
      var preview = backdrop.querySelector("#profilePicturePreview");
      if (preview) preview.innerHTML = avatar(src);

      var image = new Image();
      image.onload = function () {
        crop.image = image;
        resetCrop();
        zoom.value = "1";
        draw(canvas);
        status.textContent = "드래그로 위치를 맞추고 확대/회전한 뒤 편집 완료를 눌러줘.";
      };
      image.onerror = function () {
        crop.image = null;
        draw(canvas);
        status.textContent = "이미지를 읽지 못했어. 다른 파일로 시도해줘.";
      };
      image.src = src;
    };
    reader.onerror = function () {
      crop.image = null;
      draw(canvas);
      status.textContent = "이미지를 읽지 못했어. 다른 파일로 시도해줘.";
    };
    reader.readAsDataURL(file);
  }

  function stageCropped(canvas, status, saveButton) {
    if (!crop.image) {
      status.textContent = "먼저 사진을 선택해줘.";
      return;
    }
    pendingPictureData = canvas.toDataURL("image/png");
    setAccountPreview(pendingPictureData);
    status.textContent = "프로필 사진이 임시 반영됐어. 계정관리에서 저장을 눌러야 최종 적용돼.";
    var accountStatus = document.querySelector("#myAccountModal #profilePictureStatus");
    if (accountStatus) accountStatus.textContent = "사진 편집 완료. 아래 저장을 눌러야 실제 적용돼.";
    saveButton.disabled = true;
    toast("사진 편집 완료. 계정 저장을 눌러야 적용돼.");
    setTimeout(closeCropModal, 450);
  }

  function closeCropModal() {
    var modal = document.getElementById("profileCropModalBackdrop");
    if (modal) modal.remove();
  }

  function wireCrop(backdrop, file) {
    var canvas = backdrop.querySelector("#profileCropCanvas");
    var stage = backdrop.querySelector("#profileCropStage");
    var zoom = backdrop.querySelector("#profileCropZoom");
    var status = backdrop.querySelector("#profilePictureStatus");
    var saveButton = backdrop.querySelector("#profilePictureSaveBtn");

    draw(canvas);
    loadSelectedImage(file, canvas, status, zoom, backdrop);

    zoom.addEventListener("input", function () {
      crop.scale = Number(zoom.value || 1);
      draw(canvas);
    });
    backdrop.querySelector("#profileCenterBtn").addEventListener("click", function () {
      crop.offsetX = 0;
      crop.offsetY = 0;
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
    saveButton.addEventListener("click", function () { stageCropped(canvas, status, saveButton); });

    canvas.addEventListener("wheel", function (event) {
      event.preventDefault();
      var next = Number(zoom.value || 1) + (event.deltaY > 0 ? -0.08 : 0.08);
      next = Math.max(1, Math.min(3, next));
      zoom.value = String(next);
      crop.scale = next;
      draw(canvas);
    }, { passive: false });

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
      + '<header class="profile-edit-head"><div><h2>프로필 사진 편집</h2><p>원형 아바타에 맞게 위치를 조정하고 확대/회전한 뒤 미리보기에 적용해.</p></div><button class="profile-edit-close" id="profileCropCloseBtn" type="button" aria-label="닫기">×</button></header>'
      + '<div class="profile-edit-body">'
      + '<div class="profile-crop-stage" id="profileCropStage"><canvas id="profileCropCanvas" width="360" height="360"></canvas></div>'
      + '<div class="profile-crop-controls">'
      + '<div class="profile-edit-preview"><div class="profile-preview" id="profilePicturePreview">' + avatar(currentImage()) + '</div><div><strong>원형 미리보기</strong><small>저장은 계정관리 저장 버튼을 눌렀을 때 최종 반영됩니다.</small></div></div>'
      + '<label>확대/축소<input id="profileCropZoom" type="range" min="1" max="3" step="0.01" value="1"></label>'
      + '<div class="profile-crop-actions">'
      + '<button class="btn btn-light" type="button" id="profileCenterBtn">가운데 정렬</button>'
      + '<button class="btn btn-light" type="button" id="profileRotateLeftBtn">왼쪽 회전</button>'
      + '<button class="btn btn-light" type="button" id="profileRotateRightBtn">오른쪽 회전</button>'
      + '<button class="btn btn-light" type="button" id="profileCropCancelBtn">취소</button>'
      + '<button class="btn btn-primary" type="button" id="profilePictureSaveBtn">편집 완료</button>'
      + '</div><small class="profile-crop-status" id="profilePictureStatus">사진을 불러오는 중...</small>'
      + '</div></div></section>';
    document.body.appendChild(backdrop);
    wireCrop(backdrop, file);
  }

  function enhanceProfileUploadCard() {
    var modal = document.getElementById("myAccountModal");
    var uploader = modal && modal.querySelector(".profile-uploader");
    if (!uploader || uploader.dataset.profileUploadEnhanced === "1") return;

    uploader.dataset.profileUploadEnhanced = "1";
    uploader.className = "profile-uploader profile-upload-card";
    uploader.innerHTML = ""
      + '<div class="profile-upload-copy"><div class="profile-preview" id="profilePicturePreview">' + avatar(pendingPictureData || currentImage()) + '</div><div><strong>새 프로필 미리보기</strong><small>편집 완료 후에도 계정관리 저장 전까지는 실제 프로필이 바뀌지 않습니다.</small></div></div>'
      + '<div class="profile-upload-actions"><label class="profile-file-button">프로필사진 업로드<input id="profilePictureInput" type="file" accept="image/png,image/jpeg,image/jpg,image/jpe,image/webp,image/gif"></label><small class="profile-upload-status" id="profilePictureStatus">PNG, JPG, WEBP, GIF 이미지를 사용할 수 있어.</small></div>'
      + '<div class="profile-existing-picture"><span>현재 프로필</span><div class="profile-preview profile-existing-preview">' + avatar(currentImage()) + '</div><small>계정관리에서 취소하면 이 사진이 그대로 유지됩니다.</small></div>';

    var input = uploader.querySelector("#profilePictureInput");
    var status = uploader.querySelector("#profilePictureStatus");
    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) return;
      if (!isImageFile(file)) {
        status.textContent = "이미지 파일만 사용할 수 있어.";
        input.value = "";
        return;
      }
      status.textContent = file.name + " 선택됨. 편집 화면을 열었어.";
      openCropModal(file);
      input.value = "";
    });
  }

  async function uploadPendingPicture() {
    if (!pendingPictureData) return null;
    var body = new FormData();
    body.append("picture_data", pendingPictureData);
    var res = await fetch("/api/my-account/picture", { method: "POST", body: body });
    var contentType = res.headers.get("content-type") || "";
    var data = contentType.indexOf("application/json") >= 0 ? await res.json() : { ok: false, error: await res.text() };
    if (!res.ok || !data.ok) throw new Error(data.error || "프로필 사진 저장에 실패했어.");
    pendingPictureData = "";
    updateAllAvatars(data.picture);
    return data.picture;
  }

  function wrapAccountModal() {
    var previousOpen = window.openMyAccountModal;
    window.openMyAccountModal = function () {
      pendingPictureData = "";
      if (typeof previousOpen === "function") previousOpen.apply(this, arguments);
      setTimeout(enhanceProfileUploadCard, 0);
    };

    var previousClose = window.closeMyAccountModal;
    window.closeMyAccountModal = function () {
      discardPendingPicture();
      closeCropModal();
      if (typeof previousClose === "function") return previousClose.apply(this, arguments);
    };

    window.saveMyAccount = async function () {
      var newId = document.getElementById("myAccountId") ? document.getElementById("myAccountId").value.trim() : "";
      var newName = document.getElementById("myAccountName") ? document.getElementById("myAccountName").value.trim() : "";
      var newPw = document.getElementById("myAccountPw") ? document.getElementById("myAccountPw").value.trim() : "";

      try {
        var res = await fetch("/api/my-account/update", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({ new_id: newId, new_name: newName, new_pw: newPw })
        });
        var contentType = res.headers.get("content-type") || "";
        var data = contentType.indexOf("application/json") >= 0 ? await res.json() : { ok: false, error: await res.text() };
        if (!res.ok || !data.ok) throw new Error(data.error || "계정 수정 실패");
        await uploadPendingPicture();
        alert("내 계정이 수정됐어.");
        window.location.reload();
      } catch (err) {
        alert(err.message || "계정 수정 실패");
      }
    };

    setTimeout(enhanceProfileUploadCard, 0);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wrapAccountModal);
  } else {
    wrapAccountModal();
  }
})();
