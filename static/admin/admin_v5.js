(function () {
  function chartData() {
    const node = document.getElementById("adminChartData");
    if (!node) return {};
    try {
      return JSON.parse(node.textContent || "{}") || {};
    } catch (error) {
      return {};
    }
  }

  function apiError(message) {
    const text = String(message || "요청 처리 중 오류가 발생했습니다.");
    const host = document.querySelector("main.page") || document.body;
    let banner = document.getElementById("adminApiErrorBanner");

    if (!banner) {
      banner = document.createElement("div");
      banner.id = "adminApiErrorBanner";
      banner.className = "admin-error-banner";
      banner.innerHTML = '<strong>요청 실패</strong><span></span><button type="button" aria-label="닫기">×</button>';
      banner.querySelector("button").addEventListener("click", () => banner.remove());
      host.prepend(banner);
    }

    banner.querySelector("span").textContent = text;
  }

  function empty(ctx, width, height) {
    ctx.fillStyle = "#98a2b3";
    ctx.font = "13px Segoe UI";
    ctx.textAlign = "center";
    ctx.fillText("표시할 데이터가 없습니다", width / 2, height / 2);
    ctx.textAlign = "left";
  }

  function sized(canvas) {
    const width = canvas.clientWidth || 640;
    const height = Number(canvas.getAttribute("height")) || 220;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    const ctx = canvas.getContext("2d");
    ctx.scale(ratio, ratio);
    ctx.clearRect(0, 0, width, height);
    return { ctx, width, height };
  }

  function bar(canvas, data) {
    const { ctx, width, height } = sized(canvas);
    const labels = Array.isArray(data.labels) ? data.labels : [];
    const values = Array.isArray(data.values) ? data.values.map((value) => Number(value || 0)) : [];
    const max = Math.max(...values, 1);
    const padding = { left: 34, right: 18, top: 18, bottom: 30 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    ctx.strokeStyle = "#e8edf4";
    ctx.lineWidth = 1;
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

    const gap = 4;
    const barWidth = Math.max(4, chartWidth / Math.max(values.length, 1) - gap);
    values.forEach((value, index) => {
      const x = padding.left + index * (barWidth + gap);
      const barHeight = (chartHeight * value) / max;
      const y = padding.top + chartHeight - barHeight;
      const gradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
      gradient.addColorStop(0, "#5b8def");
      gradient.addColorStop(1, "#4bb99f");
      ctx.fillStyle = gradient;
      ctx.fillRect(x, y, barWidth, barHeight || 2);

      if (labels[index] && index % Math.ceil(labels.length / 8 || 1) === 0) {
        ctx.fillStyle = "#738198";
        ctx.fillText(labels[index], x, height - 10);
      }
    });
  }

  function donut(canvas, data) {
    const { ctx, width, height } = sized(canvas);
    const values = Array.isArray(data.values) ? data.values.map((value) => Number(value || 0)) : [];
    const labels = Array.isArray(data.labels) ? data.labels : [];
    const colors = data.colors || ["#47b881", "#e55353", "#f0ad4e", "#6c7ae0"];
    const total = values.reduce((sum, value) => sum + value, 0);

    if (!total) {
      empty(ctx, width, height);
      return;
    }

    const centerX = width * 0.38;
    const centerY = height * 0.48;
    const radius = Math.min(width, height) * 0.29;
    let angle = -Math.PI / 2;

    values.forEach((value, index) => {
      const slice = (Math.PI * 2 * value) / total;
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius, angle, angle + slice);
      ctx.lineWidth = 22;
      ctx.strokeStyle = colors[index % colors.length];
      ctx.stroke();
      angle += slice;
    });

    ctx.fillStyle = "#111827";
    ctx.font = "700 24px Segoe UI";
    ctx.textAlign = "center";
    ctx.fillText(String(total), centerX, centerY + 8);
    ctx.textAlign = "left";
    ctx.font = "12px Segoe UI";
    labels.forEach((label, index) => {
      const y = 48 + index * 24;
      ctx.fillStyle = colors[index % colors.length];
      ctx.fillRect(width * 0.66, y - 9, 9, 9);
      ctx.fillStyle = "#475467";
      ctx.fillText(`${label} ${values[index] || 0}`, width * 0.66 + 16, y);
    });
  }

  function renderCharts() {
    const data = chartData();
    document.querySelectorAll("canvas.admin-chart").forEach((canvas) => {
      if (canvas.classList.contains("line") || canvas.classList.contains("area")) return;
      try {
        const chart = data[canvas.dataset.chart] || {};
        canvas.classList.contains("donut") ? donut(canvas, chart) : bar(canvas, chart);
      } catch (error) {
        const ctx = canvas.getContext("2d");
        if (ctx) empty(ctx, canvas.clientWidth || 320, Number(canvas.getAttribute("height")) || 180);
      }
    });
  }

  function installFetchGuard() {
    if (!window.fetch || window.__adminV5FetchGuard) return;
    window.__adminV5FetchGuard = true;
    window.showAdminApiError = apiError;
    const nativeFetch = window.fetch.bind(window);

    window.fetch = async (...args) => {
      let response;
      try {
        response = await nativeFetch(...args);
      } catch (error) {
        apiError("네트워크 요청에 실패했습니다. 연결 상태를 확인한 뒤 다시 시도해 주세요.");
        throw error;
      }

      const originalJson = response.json.bind(response);
      response.json = async () => {
        const type = response.headers.get("content-type") || "";
        const text = await response.clone().text();
        let payload = null;

        if (type.includes("application/json")) {
          try {
            payload = JSON.parse(text);
          } catch (error) {
            payload = null;
          }
        }

        if (!response.ok) {
          const message = payload?.error || payload?.message || `서버 오류 ${response.status}`;
          apiError(message);
          return { ok: false, error: message, status: response.status };
        }

        if (payload !== null) return payload;

        if (/^\s*</.test(text)) {
          const message = "서버가 JSON 대신 HTML 페이지를 반환했습니다. 로그인 상태나 서버 오류를 확인해 주세요.";
          apiError(message);
          return { ok: false, error: message, status: response.status };
        }

        try {
          return JSON.parse(text);
        } catch (error) {
          try {
            return await originalJson();
          } catch (jsonError) {
            const message = "서버 응답을 JSON으로 해석할 수 없습니다.";
            apiError(message);
            return { ok: false, error: message, status: response.status };
          }
        }
      };

      return response;
    };
  }

  function installTableFilters() {
    document.querySelectorAll(".js-table-filter").forEach((input) => {
      input.addEventListener("input", () => {
        const target = document.querySelector(input.dataset.target || "");
        if (!target) return;
        const query = input.value.trim().toLowerCase();
        target.querySelectorAll("tbody tr").forEach((row) => {
          row.hidden = Boolean(query) && !row.textContent.toLowerCase().includes(query);
        });
      });
    });
  }

  installFetchGuard();
  document.addEventListener("DOMContentLoaded", () => {
    installTableFilters();
    renderCharts();
    document.getElementById("sidebarToggle")?.addEventListener("click", () => document.body.classList.toggle("sidebar-collapsed"));
  });
  window.addEventListener("resize", () => {
    clearTimeout(window.__adminV5ResizeTimer);
    window.__adminV5ResizeTimer = setTimeout(renderCharts, 120);
  });
})();
