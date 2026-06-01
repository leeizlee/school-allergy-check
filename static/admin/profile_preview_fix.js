(function () {
  function findPreview(root) {
    return (root || document).querySelector("#profilePicturePreview,.profile-preview,.profile-preview-surface,.profile-crop-preview,.crop-preview");
  }

  function findStatus(root, input) {
    return (root || document).querySelector("#profilePictureStatus,.profile-status,.crop-status") || (input && input.parentElement ? input.parentElement.querySelector("small") : null);
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
    if (!file.type || file.type.indexOf("image/") !== 0) {
      if (status) status.textContent = "이미지 파일만 사용할 수 있어.";
      return;
    }

    var url = URL.createObjectURL(file);
    if (preview) {
      preview.innerHTML = "";
      var img = document.createElement("img");
      img.src = url;
      img.alt = "프로필 미리보기";
      img.style.width = "100%";
      img.style.height = "100%";
      img.style.objectFit = "cover";
      img.style.borderRadius = "inherit";
      preview.appendChild(img);
    }
    if (status) status.textContent = "미리보기 완료. 사진 저장을 눌러줘.";
  }

  document.addEventListener("change", function (event) {
    var input = event.target;
    if (!(input instanceof HTMLInputElement)) return;
    if (input.type !== "file") return;
    var id = String(input.id || "").toLowerCase();
    var accept = String(input.accept || "").toLowerCase();
    if (id.indexOf("profile") < 0 && accept.indexOf("image") < 0) return;
    showPreview(input);
  }, true);
})();
