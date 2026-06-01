(function () {
  var allowedExt = ["png", "jpg", "jpeg", "jpe", "webp", "gif"];

  function findPreview(root) {
    return (root || document).querySelector("#profilePicturePreview,.profile-preview,.profile-preview-surface,.profile-crop-preview,.crop-preview");
  }

  function findStatus(root, input) {
    return (root || document).querySelector("#profilePictureStatus,.profile-status,.crop-status") || (input && input.parentElement ? input.parentElement.querySelector("small") : null);
  }

  function extensionOf(file) {
    var name = String((file && file.name) || "").toLowerCase();
    var dot = name.lastIndexOf(".");
    return dot >= 0 ? name.slice(dot + 1) : "";
  }

  function isAllowedImage(file) {
    if (!file) return false;
    var type = String(file.type || "").toLowerCase();
    var ext = extensionOf(file);
    if (allowedExt.indexOf(ext) >= 0) return true;
    return type.indexOf("image/") === 0;
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

  function showPreview(input) {
    var file = input.files && input.files[0];
    var root = input.closest("#myAccountModal,.modal-backdrop,.modal,.modal-card") || document;
    var preview = findPreview(root);
    var status = findStatus(root, input);

    if (!file) {
      if (status) status.textContent = "사진 파일을 선택해줘.";
      return;
    }
    if (!isAllowedImage(file)) {
      if (status) status.textContent = "PNG, JPG, JPEG, JPE, WEBP, GIF 이미지만 사용할 수 있어.";
      return;
    }

    var reader = new FileReader();
    reader.onload = function () {
      var src = String(reader.result || "");
      if (!src) {
        if (status) status.textContent = "이미지를 읽지 못했어. 다른 파일로 시도해줘.";
        return;
      }
      setImage(preview, src);
      window.__profilePreviewDataUrl = src;
      if (status) status.textContent = "미리보기 완료. 사진 저장을 눌러줘.";
    };
    reader.onerror = function () {
      if (status) status.textContent = "이미지를 읽지 못했어. 다른 파일로 시도해줘.";
    };
    reader.readAsDataURL(file);
  }

  document.addEventListener("change", function (event) {
    var input = event.target;
    if (!(input instanceof HTMLInputElement)) return;
    if (input.type !== "file") return;
    var id = String(input.id || "").toLowerCase();
    var accept = String(input.accept || "").toLowerCase();
    var name = String(input.name || "").toLowerCase();
    if (id.indexOf("profile") < 0 && name.indexOf("profile") < 0 && accept.indexOf("image") < 0) return;
    showPreview(input);
  }, true);
})();
