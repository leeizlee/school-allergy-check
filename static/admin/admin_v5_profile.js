(function () {
  "use strict";

  window.__adminV5ProfileUploadReady = true;

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

  function updateAvatars(src) {
    document.querySelectorAll(".topbar-avatar,.avatar-button").forEach(function (btn) {
      btn.innerHTML = avatar(src);
    });
    document.querySelectorAll("#profilePicturePreview").forEach(function (preview) {
      preview.innerHTML = avatar(src);
    });
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
        status.textContent = "드래그로 위치를 맞추고 확대/회전한 뒤 저장해.";
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

  async function saveCropped(canvas, status, saveButton) {
    if (!crop.image) {
      status.textContent = "먼저 사진을 선택해줘.";
      return;
    }
    saveButton.disabled = true;
    status.textContent = "프로필 사진 저장 중...";
    try {
      var body = new FormData();
      body.append("picture_data", canvas.toDataURL("image/png"));
      var res = await fetch("/api/my-account/picture", { method: "POST", body: body });
      var contentType = res.headers.get("content-type") || "";
      var data = contentType.indexOf("application/json") >= 0 ? await res.json() : { ok: false, error: await res.text() };
      if (!res.ok || !data.ok) throw new Error(data.error || "프로필 사진 저장에 실패했어.");
      updateAvatars(data.picture);
      status.textContent = "프로필 사진이 저장됐어.";
      toast("프로필 사진 저장 완료");
      setTimeout(closeCropModal, 450);
    } catch (err) {
      status.textContent = err.message || "프로필 사진 저장에 실패했어.";
    } finally {
      saveButton.disabled = false;
    }
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
    saveButton.addEventListener("click", function () { saveCropped(canvas, status, saveButton); });

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
      + '<div class="profile-edit-preview"><div class="profile-preview" id="profilePicturePreview">' + avatar(currentImage()) + '</div><div><strong>원형 미리보기</strong><small>저장하면 모든 관리자 아바타에 바로 반영됩니다.</small></div></div>'
      + '<label>확대/축소<input id="profileCropZoom" type="range" min="1" max="3" step="0.01" value="1"></label>'
      + '<div class="profile-crop-actions">'
      + '<button class="btn btn-light" type="button" id="profileCenterBtn">가운데 정렬</button>'
      + '<button class="btn btn-light" type="button" id="profileRotateLeftBtn">왼쪽 회전</button>'
      + '<button class="btn btn-light" type="button" id="profileRotateRightBtn">오른쪽 회전</button>'
      + '<button class="btn btn-light" type="button" id="profileCropCancelBtn">취소</button>'
      + '<button class="btn btn-primary" type="button" id="profilePictureSaveBtn">사진 저장</button>'
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
      + '<div class="profile-upload-copy"><div class="profile-preview" id="profilePicturePreview">' + avatar(currentImage()) + '</div><div><strong>프로필 사진</strong><small>프로필사진 업로드를 누른 뒤 사진을 선택하면 편집 화면이 열립니다.</small></div></div>'
      + '<div class="profile-upload-actions"><label class="profile-file-button">프로필사진 업로드<input id="profilePictureInput" type="file" accept="image/png,image/jpeg,image/jpg,image/jpe,image/webp,image/gif"></label><small class="profile-upload-status" id="profilePictureStatus">PNG, JPG, WEBP, GIF 이미지를 사용할 수 있어.</small></div>';

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
