(function () {
  var allowedExt = ["png", "jpg", "jpeg", "jpe", "webp", "gif"];
  var state = null;

  function qs(selector, root) { return (root || document).querySelector(selector); }
  function qsa(selector, root) { return Array.from((root || document).querySelectorAll(selector)); }
  function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }

  function extensionOf(file) {
    var name = String((file && file.name) || "").toLowerCase();
    var dot = name.lastIndexOf(".");
    return dot >= 0 ? name.slice(dot + 1) : "";
  }

  function isAllowedImage(file) {
    if (!file) return false;
    var type = String(file.type || "").toLowerCase();
    var ext = extensionOf(file);
    return allowedExt.indexOf(ext) >= 0 || type.indexOf("image/") === 0;
  }

  function rootOf(node) {
    return node && node.closest ? (node.closest("#myAccountModal,.modal-backdrop,.modal,.modal-card") || document) : document;
  }

  function findPreview(root) {
    return qs("#profilePicturePreview,.profile-preview,.profile-preview-surface,.profile-crop-preview,.crop-preview", root || document);
  }

  function findStatus(root, input) {
    return qs("#profilePictureStatus,.profile-status,.crop-status", root || document) || (input && input.parentElement ? qs("small", input.parentElement) : null);
  }

  function setStatus(node, text, ok) {
    if (!node) return;
    node.textContent = text || "";
    node.classList.toggle("profile-upload-ok", ok === true);
    node.classList.toggle("profile-upload-error", ok === false);
  }

  function setImage(preview, src) {
    if (!preview || !src) return;
    preview.innerHTML = "";
    var img = document.createElement("img");
    img.src = src;
    img.alt = "프로필 미리보기";
    img.style.width = "100%";
    img.style.height = "100%";
    img.style.objectFit = "cover";
    img.style.borderRadius = "inherit";
    preview.appendChild(img);
  }

  function syncAvatar(src) {
    if (!src) return;
    qsa(".topbar-avatar,.avatar-button,#profilePicturePreview,.profile-preview").forEach(function (node) {
      setImage(node, src);
    });
    qsa(".avatar-img").forEach(function (img) { img.src = src; });
  }

  function ensureEditor() {
    var old = qs("#profileCropEditor");
    if (old) return old;

    var modal = document.createElement("div");
    modal.id = "profileCropEditor";
    modal.className = "modal-backdrop profile-crop-editor hidden";
    modal.innerHTML = ''
      + '<section class="modal-card profile-crop-card">'
      + '  <div class="modal-header">'
      + '    <div><h2>프로필 사진 편집</h2><p>원 크기와 위치를 조정한 뒤 저장해.</p></div>'
      + '    <button class="btn btn-light" type="button" data-profile-crop-close>×</button>'
      + '  </div>'
      + '  <div class="profile-crop-grid">'
      + '    <div class="profile-crop-stage"><canvas id="profileCropCanvas" width="320" height="320"></canvas><div class="profile-crop-ring"></div></div>'
      + '    <div class="profile-crop-controls">'
      + '      <div class="profile-crop-live"><span id="profileCropLive" class="profile-preview">관</span><div><strong>원형 미리보기</strong><small>저장하면 관리자 아바타에 바로 반영됩니다.</small></div></div>'
      + '      <label class="profile-crop-label">사진 확대/축소<input id="profileCropZoom" type="range" min="0.6" max="3" step="0.01" value="1"></label>'
      + '      <label class="profile-crop-label">큰 원 크기<input id="profileCropRing" type="range" min="0.58" max="0.94" step="0.01" value="0.79"></label>'
      + '      <label class="profile-crop-label">미리보기 원 크기<input id="profileCropLiveSize" type="range" min="56" max="112" step="1" value="76"></label>'
      + '      <div class="button-row"><button class="btn btn-light" type="button" data-profile-center>가운데 정렬</button><button class="btn btn-light" type="button" data-profile-rotate-left>왼쪽 회전</button><button class="btn btn-light" type="button" data-profile-rotate-right>오른쪽 회전</button></div>'
      + '      <div class="button-row"><button class="btn btn-light" type="button" data-profile-crop-cancel>취소</button><button class="btn btn-primary" type="button" data-profile-crop-save>사진 저장</button></div>'
      + '      <small id="profileCropStatus">드래그로 위치를 맞추고, 틀어지면 가운데 정렬을 눌러줘.</small>'
      + '    </div>'
      + '  </div>'
      + '</section>';
    document.body.appendChild(modal);

    var style = document.createElement("style");
    style.textContent = ''
      + '.profile-crop-editor.hidden{display:none!important}'
      + '.profile-crop-card{width:min(780px,calc(100vw - 48px))!important;padding:0!important;overflow:hidden!important}'
      + '.profile-crop-card .modal-header{padding:18px 22px;border-bottom:1px solid var(--fix-line,#dde4ee)}'
      + '.profile-crop-grid{display:grid;grid-template-columns:minmax(280px,1fr) minmax(270px,.92fr);gap:20px;padding:22px}'
      + '.profile-crop-stage{position:relative;width:320px;height:320px;max-width:100%;margin:auto;border-radius:12px;background:#0b101a;overflow:hidden;touch-action:none;cursor:grab}'
      + '.profile-crop-stage:active{cursor:grabbing}'
      + '#profileCropCanvas{display:block;width:100%;height:100%}'
      + '.profile-crop-ring{pointer-events:none;position:absolute;inset:34px;border:2px solid rgba(255,255,255,.90);border-radius:50%;box-shadow:0 0 0 999px rgba(0,0,0,.28)}'
      + '.profile-crop-ring:before,.profile-crop-ring:after{content:"";position:absolute;background:rgba(255,255,255,.32)}'
      + '.profile-crop-ring:before{left:50%;top:0;bottom:0;width:1px}.profile-crop-ring:after{top:50%;left:0;right:0;height:1px}'
      + '.profile-crop-controls{display:grid;align-content:start;gap:14px}'
      + '.profile-crop-live{display:grid;grid-template-columns:auto 1fr;gap:12px;align-items:center;padding:13px;border:1px solid var(--fix-line,#dde4ee);border-radius:10px;background:var(--fix-card-soft,#f8fafc)}'
      + '.profile-crop-label{display:grid;gap:7px;font-size:13px;font-weight:900;color:var(--fix-muted,#667085)}'
      + '#profileCropZoom,#profileCropRing,#profileCropLiveSize{width:100%}'
      + '@media(max-width:760px){.profile-crop-grid{grid-template-columns:1fr}.profile-crop-stage{width:280px;height:280px}}';
    document.head.appendChild(style);
    return modal;
  }

  function ringSize() {
    var view = state && state.viewSize ? state.viewSize : 320;
    var ratio = state && state.ringRatio ? state.ringRatio : 0.79;
    return view * ratio;
  }

  function updateRingAndLive() {
    if (!state) return;
    var ring = qs(".profile-crop-ring");
    if (ring) {
      var inset = Math.max(10, (state.viewSize - ringSize()) / 2);
      ring.style.inset = inset + "px";
    }
    var live = qs("#profileCropLive");
    if (live) {
      live.style.width = state.liveSize + "px";
      live.style.height = state.liveSize + "px";
    }
  }

  function drawImageTransform(ctx, size, scaleBase) {
    var img = state.image;
    var view = state.viewSize || 320;
    var fit = Math.max(view / img.naturalWidth, view / img.naturalHeight);
    ctx.translate(size / 2 + state.x * scaleBase, size / 2 + state.y * scaleBase);
    ctx.rotate(state.rotate * Math.PI / 180);
    ctx.scale(fit * state.zoom * scaleBase, fit * state.zoom * scaleBase);
    ctx.drawImage(img, -img.naturalWidth / 2, -img.naturalHeight / 2);
  }

  function drawStageTo(canvas, outSize) {
    if (!state || !state.image || !canvas) return;
    var ctx = canvas.getContext("2d");
    var size = outSize || canvas.width;
    canvas.width = size;
    canvas.height = size;
    var scaleBase = size / (state.viewSize || 320);
    ctx.clearRect(0, 0, size, size);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, size, size);
    ctx.save();
    drawImageTransform(ctx, size, scaleBase);
    ctx.restore();
  }

  function drawCropTo(canvas, outSize) {
    if (!state || !state.image || !canvas) return;
    var ctx = canvas.getContext("2d");
    var size = outSize || canvas.width;
    var view = state.viewSize || 320;
    var crop = ringSize();
    var scaleBase = size / crop;
    canvas.width = size;
    canvas.height = size;
    ctx.clearRect(0, 0, size, size);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, size, size);
    ctx.save();
    ctx.translate(size / 2, size / 2);
    ctx.scale(view / crop, view / crop);
    ctx.translate(-view / 2, -view / 2);
    ctx.restore();
    ctx.save();
    drawImageTransform(ctx, size, scaleBase);
    ctx.restore();
  }

  function draw() {
    var canvas = qs("#profileCropCanvas");
    if (!canvas || !state) return;
    var stage = canvas.parentElement;
    var size = Math.round(stage.getBoundingClientRect().width || 320);
    state.viewSize = size;
    canvas.style.width = size + "px";
    canvas.style.height = size + "px";
    updateRingAndLive();
    drawStageTo(canvas, size);
    var temp = document.createElement("canvas");
    drawCropTo(temp, 160);
    setImage(qs("#profileCropLive"), temp.toDataURL("image/png"));
  }

  function openEditor(src, input, status) {
    var editor = ensureEditor();
    var img = new Image();
    img.onload = function () {
      state = { image: img, input: input, status: status, x: 0, y: 0, zoom: 1, rotate: 0, ringRatio: 0.79, liveSize: 76, dragging: false, lastX: 0, lastY: 0, viewSize: 320 };
      qs("#profileCropZoom").value = "1";
      qs("#profileCropRing").value = String(state.ringRatio);
      qs("#profileCropLiveSize").value = String(state.liveSize);
      editor.classList.remove("hidden");
      draw();
      setStatus(status, "편집 화면에서 원 크기와 위치를 맞춘 뒤 사진 저장을 눌러줘.", true);
    };
    img.onerror = function () { setStatus(status, "이미지를 읽지 못했어. 다른 파일로 시도해줘.", false); };
    img.src = src;
  }

  function closeEditor() {
    var editor = qs("#profileCropEditor");
    if (editor) editor.classList.add("hidden");
  }

  function handleFile(input) {
    var file = input.files && input.files[0];
    var root = rootOf(input);
    var preview = findPreview(root);
    var status = findStatus(root, input);
    if (!file) { setStatus(status, "사진 파일을 선택해줘.", false); return; }
    if (!isAllowedImage(file)) { setStatus(status, "PNG, JPG, JPEG, JPE, WEBP, GIF 이미지만 사용할 수 있어.", false); return; }
    var reader = new FileReader();
    reader.onload = function () {
      var src = String(reader.result || "");
      if (!src) { setStatus(status, "이미지를 읽지 못했어. 다른 파일로 시도해줘.", false); return; }
      setImage(preview, src);
      window.__profilePreviewDataUrl = src;
      openEditor(src, input, status);
    };
    reader.onerror = function () { setStatus(status, "이미지를 읽지 못했어. 다른 파일로 시도해줘.", false); };
    reader.readAsDataURL(file);
  }

  function uploadCropped() {
    if (!state) return;
    var status = qs("#profileCropStatus") || state.status;
    setStatus(status, "프로필 사진 저장 중...", true);
    var out = document.createElement("canvas");
    drawCropTo(out, 512);
    out.toBlob(function (blob) {
      if (!blob) { setStatus(status, "이미지 저장용 파일을 만들지 못했어.", false); return; }
      var body = new FormData();
      body.append("picture", blob, "profile-crop.png");
      fetch("/api/my-account/picture", { method: "POST", body: body })
        .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
        .then(function (result) {
          if (!result.ok || !result.data.ok) throw new Error(result.data.error || "프로필 사진 저장 실패");
          syncAvatar(result.data.picture);
          setStatus(state.status, "프로필 사진이 저장됐어.", true);
          setStatus(status, "프로필 사진이 저장됐어.", true);
          closeEditor();
        })
        .catch(function (err) { setStatus(status, err.message || "프로필 사진 저장 실패", false); });
    }, "image/png", 0.95);
  }

  document.addEventListener("change", function (event) {
    var input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "file") return;
    var id = String(input.id || "").toLowerCase();
    var accept = String(input.accept || "").toLowerCase();
    var name = String(input.name || "").toLowerCase();
    if (id.indexOf("profile") < 0 && name.indexOf("profile") < 0 && accept.indexOf("image") < 0) return;
    event.stopImmediatePropagation();
    handleFile(input);
  }, true);

  document.addEventListener("click", function (event) {
    if (event.target.closest("[data-profile-crop-close],[data-profile-crop-cancel]")) closeEditor();
    if (event.target.closest("[data-profile-center]")) { if (state) { state.x = 0; state.y = 0; draw(); setStatus(qs("#profileCropStatus"), "사진 위치를 가운데로 맞췄어.", true); } }
    if (event.target.closest("[data-profile-rotate-left]")) { if (state) { state.rotate -= 90; draw(); } }
    if (event.target.closest("[data-profile-rotate-right]")) { if (state) { state.rotate += 90; draw(); } }
    if (event.target.closest("[data-profile-crop-save]")) { event.preventDefault(); uploadCropped(); }
  }, true);

  document.addEventListener("click", function (event) {
    var button = event.target.closest("#profilePictureSaveBtn,button");
    if (!button) return;
    var text = (button.textContent || "").trim();
    if (button.id !== "profilePictureSaveBtn" && text.indexOf("사진 저장") < 0) return;
    if (!state) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    uploadCropped();
  }, true);

  document.addEventListener("input", function (event) {
    if (!state || !event.target) return;
    if (event.target.id === "profileCropZoom") { state.zoom = clamp(parseFloat(event.target.value || "1") || 1, 0.6, 3); draw(); }
    if (event.target.id === "profileCropRing") { state.ringRatio = clamp(parseFloat(event.target.value || "0.79") || 0.79, 0.58, 0.94); draw(); }
    if (event.target.id === "profileCropLiveSize") { state.liveSize = clamp(parseFloat(event.target.value || "76") || 76, 56, 112); draw(); }
  });

  document.addEventListener("pointerdown", function (event) {
    var stage = event.target.closest && event.target.closest(".profile-crop-stage");
    if (!stage || !state) return;
    state.dragging = true;
    state.lastX = event.clientX;
    state.lastY = event.clientY;
    stage.setPointerCapture && stage.setPointerCapture(event.pointerId);
  });

  document.addEventListener("pointermove", function (event) {
    if (!state || !state.dragging) return;
    state.x += event.clientX - state.lastX;
    state.y += event.clientY - state.lastY;
    state.lastX = event.clientX;
    state.lastY = event.clientY;
    draw();
  });

  document.addEventListener("pointerup", function () { if (state) state.dragging = false; });

  document.addEventListener("wheel", function (event) {
    var stage = event.target.closest && event.target.closest(".profile-crop-stage");
    if (!stage || !state) return;
    event.preventDefault();
    state.zoom = clamp(state.zoom + (event.deltaY < 0 ? 0.06 : -0.06), 0.6, 3);
    var slider = qs("#profileCropZoom");
    if (slider) slider.value = String(state.zoom);
    draw();
  }, { passive: false });
})();
