(function () {
  function data() {
    try {
      return JSON.parse(document.getElementById("adminChartData")?.textContent || "{}") || {};
    } catch (error) {
      return {};
    }
  }

  function empty(ctx, width, height) {
    ctx.fillStyle = "#98a2b3";
    ctx.font = "13px Segoe UI";
    ctx.textAlign = "center";
    ctx.fillText("표시할 데이터가 없습니다", width / 2, height / 2);
    ctx.textAlign = "left";
  }

  function line(canvas, chartData, area) {
    const ctx = canvas.getContext("2d");
    const width = canvas.clientWidth || 640;
    const height = Number(canvas.getAttribute("height")) || 220;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    ctx.scale(ratio, ratio);
    ctx.clearRect(0, 0, width, height);

    const labels = Array.isArray(chartData.labels) ? chartData.labels : [];
    const values = Array.isArray(chartData.values) ? chartData.values.map((value) => Number(value || 0)) : [];
    const max = Math.max(...values, 1);
    const padding = { left: 34, right: 18, top: 18, bottom: 30 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    ctx.strokeStyle = "#e8edf4";
    ctx.fillStyle = "#738198";
    ctx.font = "11px Segoe UI";
    for (let i = 0; i <= 4; i += 1) {
      const y = padding.top + chartHeight - (chartHeight * i) / 4;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
      ctx.fillText(String(Math.round((max * i) / 4)), 4, y + 4);
    }

    if (!values.some(Boolean)) {
      empty(ctx, width, height);
      return;
    }

    const points = values.map((value, index) => ({
      x: padding.left + (chartWidth * index) / Math.max(values.length - 1, 1),
      y: padding.top + chartHeight - (chartHeight * value) / max,
    }));

    if (area) {
      const gradient = ctx.createLinearGradient(0, padding.top, 0, height - padding.bottom);
      gradient.addColorStop(0, "rgba(91,141,239,.28)");
      gradient.addColorStop(1, "rgba(75,185,159,0)");
      ctx.beginPath();
      points.forEach((point, index) => (index ? ctx.lineTo(point.x, point.y) : ctx.moveTo(point.x, point.y)));
      ctx.lineTo(points[points.length - 1].x, height - padding.bottom);
      ctx.lineTo(points[0].x, height - padding.bottom);
      ctx.closePath();
      ctx.fillStyle = gradient;
      ctx.fill();
    }

    ctx.beginPath();
    points.forEach((point, index) => (index ? ctx.lineTo(point.x, point.y) : ctx.moveTo(point.x, point.y)));
    ctx.strokeStyle = "#287fdb";
    ctx.lineWidth = 3;
    ctx.stroke();

    points.forEach((point) => {
      ctx.beginPath();
      ctx.arc(point.x, point.y, 3, 0, Math.PI * 2);
      ctx.fillStyle = "#4bb99f";
      ctx.fill();
    });

    labels.forEach((label, index) => {
      if (points[index] && index % Math.ceil(labels.length / 7 || 1) === 0) {
        ctx.fillStyle = "#738198";
        ctx.fillText(label, points[index].x - 12, height - 10);
      }
    });
  }

  function redraw() {
    const all = data();
    document.querySelectorAll("canvas.admin-chart.line,canvas.admin-chart.area").forEach((canvas) => {
      try {
        line(canvas, all[canvas.dataset.chart] || {}, canvas.classList.contains("area"));
      } catch (error) {
        const ctx = canvas.getContext("2d");
        if (ctx) empty(ctx, canvas.clientWidth || 320, Number(canvas.getAttribute("height")) || 180);
      }
    });
  }

  function applyStudentFilters() {
    const active = document.querySelector(".js-student-filter.active")?.dataset.filter || "all";
    const query = (document.getElementById("studentSearchInput")?.value || "").trim().toLowerCase();
    let visibleCount = 0;

    document.querySelectorAll(".student-data-row").forEach((row) => {
      const hasAllergy = row.dataset.hasAllergy === "1";
      const hasRfid = row.dataset.hasRfid === "1";
      const matchesState =
        active === "all" ||
        (active === "allergy" && hasAllergy) ||
        (active === "no-allergy" && !hasAllergy) ||
        (active === "rfid" && hasRfid) ||
        (active === "no-rfid" && !hasRfid);
      const matchesQuery = !query || (row.dataset.search || "").includes(query);
      const isVisible = matchesState && matchesQuery;

      row.style.display = "";
      row.hidden = !isVisible;
      if (isVisible) visibleCount += 1;
    });

    const counter = document.getElementById("studentResultCount");
    if (counter) counter.textContent = String(visibleCount);
  }

  function installStudentFilters() {
    const buttons = document.querySelectorAll(".js-student-filter");
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        buttons.forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        applyStudentFilters();
      });
    });

    const input = document.getElementById("studentSearchInput");
    if (input) {
      window.filterStudentRows = applyStudentFilters;
      input.addEventListener("input", applyStudentFilters);
    }
  }

  function installUploadName() {
    const input = document.getElementById("mealFileInput");
    const label = document.getElementById("mealFileName");
    if (!input || !label) return;

    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (!file) {
        label.textContent = "선택된 파일 없음";
        return;
      }
      label.textContent = `${file.name} · ${Math.max(1, Math.round(file.size / 1024))}KB`;
      label.classList.remove("muted");
      label.classList.add("info");
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    installStudentFilters();
    installUploadName();
    setTimeout(redraw, 40);
  });
  window.addEventListener("resize", () => setTimeout(redraw, 160));
})();
