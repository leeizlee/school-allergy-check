(function () {
  "use strict";

  var pendingStudentPictureData = "";
  var currentStudentPicture = "";
  var currentStudentRowIndex = 0;

  function isImageFile(file) {
    if (!file) return false;
    if ((file.type || "").indexOf("image/") === 0) return true;
    return /\.(png|jpe?g|jpe|webp|gif)$/i.test(file.name || "");
  }

  function initialForStudent() {
    var input = document.getElementById("editStudentName");
    var name = input ? String(input.value || "").trim() : "";
    return name ? name.slice(0, 1) : "학";
  }

  function setStudentPreview(src) {
    var preview = document.querySelector("#studentEditModal #studentProfilePreview");
    if (!preview) return;
    preview.innerHTML = "";
    if (src) {
      var image = document.createElement("img");
      image.src = src;
      image.alt = "학생 프로필 미리보기";
      preview.appendChild(image);
    } else {
      preview.textContent = initialForStudent();
    }
  }

  function resetStudentPicture() {
    pendingStudentPictureData = "";
    currentStudentPicture = "";
    currentStudentRowIndex = 0;
  }

  function ensureStudentProfileCard() {
    var modal = document.getElementById("studentEditModal");
    var modalCard = modal && modal.querySelector(".modal");
    if (!modalCard) return;
    var card = modalCard.querySelector(".student-profile-upload-card");
    if (!card) {
      card = document.createElement("section");
      card.className = "student-profile-upload-card";
      card.innerHTML = ""
        + '<div class="student-profile-preview" id="studentProfilePreview"></div>'
        + '<div class="student-profile-copy"><strong>학생 프로필 사진</strong><small>사진은 학생정보 저장 전까지 임시 미리보기로만 유지됩니다. 저장 시 원형 아바타에 맞게 자동으로 잘립니다.</small></div>'
        + '<div class="student-profile-actions"><label class="btn btn-light student-profile-file">사진 선택<input id="studentProfilePictureInput" type="file" accept="image/png,image/jpeg,image/jpg,image/jpe,image/webp,image/gif"></label><small class="student-profile-status" id="studentProfilePictureStatus">PNG, JPG, WEBP, GIF · 최대 3MB</small></div>';
      var hiddenInput = modalCard.querySelector("#editStudentRowIndex");
      if (hiddenInput) hiddenInput.insertAdjacentElement("afterend", card);
      else modalCard.insertBefore(card, modalCard.querySelector(".form-group"));

      var fileInput = card.querySelector("#studentProfilePictureInput");
      fileInput.addEventListener("change", function () {
        var file = fileInput.files && fileInput.files[0];
        var status = card.querySelector("#studentProfilePictureStatus");
        if (!file) return;
        if (!isImageFile(file)) {
          status.textContent = "이미지 파일만 선택할 수 있어.";
          fileInput.value = "";
          return;
        }
        if (file.size > 3 * 1024 * 1024) {
          status.textContent = "학생 프로필 사진은 3MB 이하로 선택해줘.";
          fileInput.value = "";
          return;
        }
        var reader = new FileReader();
        reader.onload = function () {
          pendingStudentPictureData = String(reader.result || "");
          setStudentPreview(pendingStudentPictureData);
          status.textContent = "새 사진을 임시 적용했어. 학생정보 저장을 눌러야 반영돼.";
        };
        reader.onerror = function () {
          pendingStudentPictureData = "";
          setStudentPreview(currentStudentPicture);
          status.textContent = "사진을 읽지 못했어. 다른 파일로 시도해줘.";
        };
        reader.readAsDataURL(file);
        fileInput.value = "";
      });
    }
    setStudentPreview(pendingStudentPictureData || currentStudentPicture);
    var status = card.querySelector("#studentProfilePictureStatus");
    if (status) status.textContent = "PNG, JPG, WEBP, GIF · 최대 3MB";
  }

  async function readJsonResponse(res, fallback) {
    var contentType = res.headers.get("content-type") || "";
    if (contentType.indexOf("application/json") < 0) {
      var text = await res.text();
      throw new Error(text && text.indexOf("<") !== 0 ? text : fallback);
    }
    var data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || fallback);
    return data;
  }

  async function uploadPendingStudentPicture(rowIndex) {
    if (!pendingStudentPictureData) return null;
    var body = new FormData();
    body.append("picture_data", pendingStudentPictureData);
    var res = await fetch("/api/admin/student/" + encodeURIComponent(rowIndex) + "/picture", {
      method: "POST",
      body: body
    });
    return readJsonResponse(res, "학생 프로필 사진 저장에 실패했어.");
  }

  function wrapStudentEditModal() {
    if (typeof window.openStudentEditModal !== "function") return;

    var previousOpen = window.openStudentEditModal;
    window.openStudentEditModal = function (rowIndex, rfidId, name, studentId, allergyCodesText, picture) {
      pendingStudentPictureData = "";
      currentStudentPicture = String(picture || "");
      currentStudentRowIndex = Number(rowIndex || 0);
      previousOpen.apply(this, arguments);
      setTimeout(ensureStudentProfileCard, 0);
    };

    var previousClose = window.closeStudentEditModal;
    window.closeStudentEditModal = function () {
      resetStudentPicture();
      if (typeof previousClose === "function") return previousClose.apply(this, arguments);
    };

    window.saveStudentEdit = async function () {
      var rowIndex = Number(document.getElementById("editStudentRowIndex").value);
      var newRfidId = document.getElementById("editStudentRfidId").value.trim();
      var newName = document.getElementById("editStudentName").value.trim();
      var newId = window.updateEditStudentNumberPreview();
      var newPw = document.getElementById("editStudentPw").value.trim();
      var grade = document.getElementById("editStudentGrade").value.trim();
      var classNo = document.getElementById("editStudentClassNo").value.trim();
      var studentSeq = document.getElementById("editStudentSeq").value.trim();
      var allergies = typeof editStudentAllergies !== "undefined" ? editStudentAllergies : [];
      var saveButton = document.querySelector('#studentEditModal button[onclick="saveStudentEdit()"]');
      if (saveButton) saveButton.disabled = true;

      try {
        var res = await fetch("/api/student/update", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            row_index: rowIndex,
            new_rfid_id: newRfidId,
            new_name: newName,
            new_id: newId,
            grade: grade,
            class_no: classNo,
            student_seq: studentSeq,
            new_pw: newPw,
            allergy_codes: allergies
          })
        });
        await readJsonResponse(res, "학생 수정에 실패했어.");
        await uploadPendingStudentPicture(rowIndex);
        alert("학생 정보가 수정됐어.");
        window.location.reload();
      } catch (err) {
        alert(err.message || "학생 수정에 실패했어.");
        if (saveButton) saveButton.disabled = false;
      }
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wrapStudentEditModal);
  } else {
    wrapStudentEditModal();
  }
})();
