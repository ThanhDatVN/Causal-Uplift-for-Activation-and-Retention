/* Canvas chart helpers — không phụ thuộc thư viện ngoài.
 *
 * Quy ước hình học theo mark spec: line 2px, marker 8px, cột bo góc 4px ở đầu dữ
 * liệu và neo vào baseline, khe 2px màu surface giữa hai cột kề nhau, lưới và
 * trục ở mức chìm. Màu đọc từ CSS custom property nên đổi theme là vẽ lại đúng
 * bộ màu đã validate cho surface tương ứng.
 */
(function (global) {
  "use strict";

  const registry = [];

  function cssVar(name, fallback) {
    const value = getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
    return value || fallback;
  }

  function palette() {
    return {
      surface: cssVar("--surface-1", "#fcfcfb"),
      page: cssVar("--page", "#f9f9f7"),
      text: cssVar("--text-primary", "#0b0b0b"),
      secondary: cssVar("--text-secondary", "#52514e"),
      muted: cssVar("--text-muted", "#898781"),
      grid: cssVar("--grid", "#e1e0d9"),
      axis: cssVar("--axis", "#c3c2b7"),
      series: [
        cssVar("--series-1", "#2a78d6"),
        cssVar("--series-2", "#eb6834"),
        cssVar("--series-3", "#1baf7a"),
        cssVar("--series-4", "#eda100"),
        cssVar("--series-5", "#e87ba4"),
      ],
    };
  }

  function withAlpha(hex, alpha) {
    const clean = hex.replace("#", "");
    const full =
      clean.length === 3
        ? clean.split("").map((c) => c + c).join("")
        : clean;
    const value = parseInt(full, 16);
    const r = (value >> 16) & 255;
    const g = (value >> 8) & 255;
    const b = value & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function niceTicks(min, max, count) {
    if (!isFinite(min) || !isFinite(max)) return [0, 1];
    if (min === max) {
      const pad = Math.abs(min) || 1;
      min -= pad * 0.5;
      max += pad * 0.5;
    }
    const rawStep = (max - min) / Math.max(count, 1);
    const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
    const normalized = rawStep / magnitude;
    const step =
      (normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10) *
      magnitude;
    const start = Math.floor(min / step) * step;
    const ticks = [];
    for (let value = start; value <= max + step * 0.5; value += step) {
      ticks.push(Number(value.toFixed(12)));
    }
    return ticks;
  }

  function setupCanvas(canvas, height) {
    const ratio = global.devicePixelRatio || 1;
    const width = canvas.parentElement.clientWidth || 640;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    return { ctx, width, height };
  }

  const tooltipElement = () => document.getElementById("tooltip");

  function showTooltip(x, y, html) {
    const node = tooltipElement();
    if (!node) return;
    node.innerHTML = html;
    node.style.left = `${x}px`;
    node.style.top = `${y}px`;
    node.classList.add("is-visible");
  }

  function hideTooltip() {
    const node = tooltipElement();
    if (node) node.classList.remove("is-visible");
  }

  /* ------------------------------------------------------------------ line */

  function drawLineChart(canvas, config) {
    const height = config.height || 320;
    const { ctx, width } = setupCanvas(canvas, height);
    const colors = palette();
    const pad = { top: 16, right: 18, bottom: 40, left: 68 };
    const plotWidth = width - pad.left - pad.right;
    const plotHeight = height - pad.top - pad.bottom;
    if (plotWidth <= 20 || plotHeight <= 20) return;

    const series = config.series.filter((s) => s.points && s.points.length);
    if (!series.length) return;

    let xMin = Infinity;
    let xMax = -Infinity;
    let yMin = Infinity;
    let yMax = -Infinity;
    series.forEach((s) => {
      s.points.forEach((p) => {
        xMin = Math.min(xMin, p.x);
        xMax = Math.max(xMax, p.x);
        yMin = Math.min(yMin, p.low != null ? p.low : p.y, p.y);
        yMax = Math.max(yMax, p.high != null ? p.high : p.y, p.y);
      });
    });
    if (config.yZero) yMin = Math.min(yMin, 0);
    const yTicks = niceTicks(yMin, yMax, 5);
    const yLo = yTicks[0];
    const yHi = yTicks[yTicks.length - 1];

    const sx = (x) => pad.left + ((x - xMin) / (xMax - xMin || 1)) * plotWidth;
    const sy = (y) => pad.top + plotHeight - ((y - yLo) / (yHi - yLo || 1)) * plotHeight;

    // Lưới ngang ở mức chìm; không vẽ lưới dọc để đường dữ liệu nổi hơn.
    ctx.lineWidth = 1;
    ctx.strokeStyle = colors.grid;
    ctx.fillStyle = colors.muted;
    ctx.font = "11px ui-monospace, Consolas, monospace";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    yTicks.forEach((tick) => {
      const y = Math.round(sy(tick)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(pad.left + plotWidth, y);
      ctx.stroke();
      ctx.fillText(config.formatY ? config.formatY(tick) : String(tick), pad.left - 8, y);
    });

    ctx.strokeStyle = colors.axis;
    ctx.beginPath();
    ctx.moveTo(pad.left, pad.top);
    ctx.lineTo(pad.left, pad.top + plotHeight);
    ctx.lineTo(pad.left + plotWidth, pad.top + plotHeight);
    ctx.stroke();

    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const xTicks = config.xTicks || niceTicks(xMin, xMax, 6);
    xTicks.forEach((tick) => {
      if (tick < xMin || tick > xMax) return;
      ctx.fillText(
        config.formatX ? config.formatX(tick) : String(tick),
        sx(tick),
        pad.top + plotHeight + 8,
      );
    });
    if (config.xLabel) {
      ctx.fillStyle = colors.secondary;
      ctx.fillText(config.xLabel, pad.left + plotWidth / 2, height - 14);
    }

    // Dải CI vẽ trước để đường và marker nằm trên. Chỉ vẽ dải cho series được
    // đánh dấu ``band``: bốn dải mờ chồng nhau tạo thành một mảng màu không đọc
    // được và che mất chính các đường dữ liệu.
    series.forEach((s, index) => {
      const color = s.color || colors.series[index % colors.series.length];
      const hasBand = s.points.some((p) => p.low != null && p.high != null);
      if (!hasBand || s.dashed || s.band === false) return;
      ctx.beginPath();
      s.points.forEach((p, i) => {
        const x = sx(p.x);
        const y = sy(p.high != null ? p.high : p.y);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      for (let i = s.points.length - 1; i >= 0; i -= 1) {
        const p = s.points[i];
        ctx.lineTo(sx(p.x), sy(p.low != null ? p.low : p.y));
      }
      ctx.closePath();
      ctx.fillStyle = withAlpha(color, 0.14);
      ctx.fill();
    });

    series.forEach((s, index) => {
      const color = s.color || colors.series[index % colors.series.length];
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.setLineDash(s.dashed ? [6, 5] : []);
      ctx.beginPath();
      s.points.forEach((p, i) => {
        const x = sx(p.x);
        const y = sy(p.y);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.setLineDash([]);

      if (!s.dashed) {
        s.points.forEach((p) => {
          ctx.beginPath();
          ctx.arc(sx(p.x), sy(p.y), 4, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
          // Vòng 2px màu surface để marker chồng nhau vẫn tách được.
          ctx.lineWidth = 2;
          ctx.strokeStyle = colors.surface;
          ctx.stroke();
        });
      }

      // Direct label chỉ cho series được nhấn và cho đường tham chiếu. Ở đây các
      // đường hội tụ về phía budget lớn, nên gắn nhãn cho mọi series sẽ chồng
      // chữ lên nhau ở mép phải; legend đã mang danh tính cho phần còn lại.
      const wantsLabel = s.emphasis === true || s.dashed === true;
      if (wantsLabel && s.label) {
        const last = s.points[s.points.length - 1];
        ctx.fillStyle = colors.secondary;
        ctx.font = "600 11px system-ui, sans-serif";
        ctx.textAlign = "right";
        ctx.textBaseline = "bottom";
        ctx.fillText(s.label, sx(last.x) - 2, sy(last.y) - 8);
      }
    });

    canvas._chart = { config, sx, sy, pad, plotWidth, plotHeight, series, xMin, xMax, colors };
    attachLineHover(canvas);
  }

  function attachLineHover(canvas) {
    if (canvas._hoverBound) return;
    canvas._hoverBound = true;
    canvas.addEventListener("mousemove", (event) => {
      const state = canvas._chart;
      if (!state) return;
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      if (x < state.pad.left || x > state.pad.left + state.plotWidth) {
        hideTooltip();
        return;
      }
      const dataX =
        state.xMin +
        ((x - state.pad.left) / state.plotWidth) * (state.xMax - state.xMin);
      let nearest = null;
      state.series.forEach((s) => {
        s.points.forEach((p) => {
          const distance = Math.abs(p.x - dataX);
          if (!nearest || distance < nearest.distance) {
            nearest = { distance, x: p.x };
          }
        });
      });
      if (!nearest) return;
      const format = state.config.formatValue || ((v) => v.toFixed(6));
      const rows = state.series
        .map((s, index) => {
          const point = s.points.find((p) => p.x === nearest.x);
          if (!point) return "";
          const color = s.color || state.colors.series[index % state.colors.series.length];
          const ci =
            point.low != null && point.high != null && !s.dashed
              ? ` <span style="color:var(--text-muted)">[${format(point.low)}; ${format(point.high)}]</span>`
              : "";
          return `<div class="tt-row"><span class="tt-key"><span class="tt-swatch" style="background:${color}"></span>${s.label}</span><span>${format(point.y)}${ci}</span></div>`;
        })
        .join("");
      const title = state.config.formatX
        ? state.config.formatX(nearest.x)
        : String(nearest.x);
      showTooltip(
        event.clientX,
        event.clientY,
        `<div class="tt-title">${state.config.xLabel || ""} ${title}</div>${rows}`,
      );
    });
    canvas.addEventListener("mouseleave", hideTooltip);
  }

  /* ------------------------------------------------------------------- bar */

  function drawBarChart(canvas, config) {
    const items = config.items.filter((item) => isFinite(item.value));
    const height = config.height || Math.max(180, items.length * 30 + 56);
    const { ctx, width } = setupCanvas(canvas, height);
    const colors = palette();
    const labelWidth = config.labelWidth || 150;
    // Lề phải phải chứa nhãn giá trị đặt sau đầu thanh CI, không chỉ sau đầu cột.
    const pad = { top: 12, right: 78, bottom: 32, left: labelWidth };
    const plotWidth = width - pad.left - pad.right;
    const plotHeight = height - pad.top - pad.bottom;
    if (!items.length || plotWidth <= 20) return;

    let vMin = 0;
    let vMax = 0;
    items.forEach((item) => {
      vMin = Math.min(vMin, item.low != null ? item.low : item.value, item.value);
      vMax = Math.max(vMax, item.high != null ? item.high : item.value, item.value);
    });
    const ticks = niceTicks(vMin, vMax, 4);
    const lo = ticks[0];
    const hi = ticks[ticks.length - 1];
    const sx = (v) => pad.left + ((v - lo) / (hi - lo || 1)) * plotWidth;

    ctx.font = "11px ui-monospace, Consolas, monospace";
    ctx.strokeStyle = colors.grid;
    ctx.fillStyle = colors.muted;
    ctx.lineWidth = 1;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ticks.forEach((tick) => {
      const x = Math.round(sx(tick)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(x, pad.top);
      ctx.lineTo(x, pad.top + plotHeight);
      ctx.stroke();
      ctx.fillText(
        config.formatValue ? config.formatValue(tick) : String(tick),
        x,
        pad.top + plotHeight + 7,
      );
    });

    const zeroX = Math.round(sx(0)) + 0.5;
    ctx.strokeStyle = colors.axis;
    ctx.beginPath();
    ctx.moveTo(zeroX, pad.top);
    ctx.lineTo(zeroX, pad.top + plotHeight);
    ctx.stroke();

    const slot = plotHeight / items.length;
    const barHeight = Math.min(18, Math.max(8, slot - 10));
    const rects = [];
    items.forEach((item, index) => {
      const centerY = pad.top + slot * index + slot / 2;
      const top = centerY - barHeight / 2;
      const x0 = sx(0);
      const x1 = sx(item.value);
      const left = Math.min(x0, x1);
      const barWidth = Math.max(1, Math.abs(x1 - x0));
      const color = item.color || colors.series[0];
      const radius = Math.min(4, barWidth / 2);

      ctx.beginPath();
      // Bo góc chỉ ở đầu dữ liệu; đầu neo vào baseline giữ góc vuông.
      if (x1 >= x0) {
        ctx.moveTo(left, top);
        ctx.lineTo(left + barWidth - radius, top);
        ctx.arcTo(left + barWidth, top, left + barWidth, top + radius, radius);
        ctx.lineTo(left + barWidth, top + barHeight - radius);
        ctx.arcTo(left + barWidth, top + barHeight, left + barWidth - radius, top + barHeight, radius);
        ctx.lineTo(left, top + barHeight);
      } else {
        ctx.moveTo(left + barWidth, top);
        ctx.lineTo(left + radius, top);
        ctx.arcTo(left, top, left, top + radius, radius);
        ctx.lineTo(left, top + barHeight - radius);
        ctx.arcTo(left, top + barHeight, left + radius, top + barHeight, radius);
        ctx.lineTo(left + barWidth, top + barHeight);
      }
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();

      if (item.low != null && item.high != null) {
        ctx.strokeStyle = colors.text;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(sx(item.low), centerY);
        ctx.lineTo(sx(item.high), centerY);
        ctx.moveTo(sx(item.low), centerY - 4);
        ctx.lineTo(sx(item.low), centerY + 4);
        ctx.moveTo(sx(item.high), centerY - 4);
        ctx.lineTo(sx(item.high), centerY + 4);
        ctx.stroke();
      }

      ctx.fillStyle = item.emphasis ? colors.text : colors.secondary;
      ctx.font = item.emphasis
        ? "600 12px system-ui, sans-serif"
        : "12px system-ui, sans-serif";
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.fillText(item.label, pad.left - 10, centerY);

      ctx.fillStyle = colors.secondary;
      ctx.font = "11px ui-monospace, Consolas, monospace";
      ctx.textAlign = "left";
      // Neo nhãn sau đầu phải của *cả* cột lẫn thanh CI. Neo vào đầu cột thôi thì
      // với cột ngắn mà CI rộng, thanh CI sẽ vẽ đè lên chữ.
      const labelAnchor = Math.max(
        x0,
        x1,
        item.high != null ? sx(item.high) : -Infinity,
      );
      ctx.fillText(
        config.formatValue ? config.formatValue(item.value) : String(item.value),
        labelAnchor + 8,
        centerY,
      );

      rects.push({ item, top: top - 4, bottom: top + barHeight + 4, color });
    });

    canvas._bars = { rects, config, colors };
    attachBarHover(canvas);
  }

  function attachBarHover(canvas) {
    if (canvas._barHoverBound) return;
    canvas._barHoverBound = true;
    canvas.addEventListener("mousemove", (event) => {
      const state = canvas._bars;
      if (!state) return;
      const rect = canvas.getBoundingClientRect();
      const y = event.clientY - rect.top;
      const hit = state.rects.find((r) => y >= r.top && y <= r.bottom);
      if (!hit) {
        hideTooltip();
        return;
      }
      const format = state.config.formatValue || ((v) => String(v));
      const item = hit.item;
      const ci =
        item.low != null && item.high != null
          ? `<div class="tt-row"><span class="tt-key">95% CI</span><span>[${format(item.low)}; ${format(item.high)}]</span></div>`
          : "";
      const extra = (item.extra || [])
        .map(
          (row) =>
            `<div class="tt-row"><span class="tt-key">${row[0]}</span><span>${row[1]}</span></div>`,
        )
        .join("");
      showTooltip(
        event.clientX,
        event.clientY,
        `<div class="tt-title"><span class="tt-swatch" style="background:${hit.color};display:inline-block;margin-right:5px"></span>${item.label}</div>` +
          `<div class="tt-row"><span class="tt-key">${state.config.valueLabel || "Giá trị"}</span><span>${format(item.value)}</span></div>${ci}${extra}`,
      );
    });
    canvas.addEventListener("mouseleave", hideTooltip);
  }

  /* -------------------------------------------------------------- registry */

  /* ------------------------------------------------------------- forest */

  /* Forest plot cho chenh lech ghep cap. Bang so noi cung mot dieu, nhung khi
   * co 8 dong thi "moi khoang tin cay deu cat duong 0" phai doc tung dong moi
   * thay. O dang hinh thi thay ngay. Duong 0 la nhan vat chinh, khong phai truc. */
  function drawForestChart(canvas, config) {
    const items = config.items.filter(
      (item) => isFinite(item.value) && isFinite(item.low) && isFinite(item.high),
    );
    const height = config.height || Math.max(180, items.length * 34 + 64);
    const { ctx, width } = setupCanvas(canvas, height);
    const colors = palette();
    const labelWidth = config.labelWidth || 168;
    const pad = { top: 14, right: 96, bottom: 34, left: labelWidth };
    const plotWidth = width - pad.left - pad.right;
    const plotHeight = height - pad.top - pad.bottom;
    if (!items.length || plotWidth <= 20) return;

    let vMin = 0;
    let vMax = 0;
    items.forEach((item) => {
      vMin = Math.min(vMin, item.low);
      vMax = Math.max(vMax, item.high);
    });
    const ticks = niceTicks(vMin, vMax, 4);
    const lo = ticks[0];
    const hi = ticks[ticks.length - 1];
    const sx = (v) => pad.left + ((v - lo) / (hi - lo || 1)) * plotWidth;

    ctx.font = "11px ui-monospace, Consolas, monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ticks.forEach((tick) => {
      const x = Math.round(sx(tick)) + 0.5;
      ctx.strokeStyle = colors.grid;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, pad.top);
      ctx.lineTo(x, pad.top + plotHeight);
      ctx.stroke();
      ctx.fillStyle = colors.muted;
      ctx.fillText(
        config.formatValue ? config.formatValue(tick) : String(tick),
        x,
        pad.top + plotHeight + 8,
      );
    });

    // Duong 0 duoc ve dam hon moi duong luoi khac: no la nguong quyet dinh.
    const zeroX = Math.round(sx(0)) + 0.5;
    ctx.strokeStyle = colors.text;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(zeroX, pad.top - 4);
    ctx.lineTo(zeroX, pad.top + plotHeight + 2);
    ctx.stroke();

    const slot = plotHeight / items.length;
    const rects = [];
    items.forEach((item, index) => {
      const centerY = Math.round(pad.top + slot * index + slot / 2) + 0.5;
      // Tach ve hai phia mang y nghia nguoc nhau: ben phai moc 0 la challenger
      // thang, ben trai la thua ro. Dung mot mau cho ca hai se doc sai.
      const better = item.low > 0;
      const worse = item.high < 0;
      const separated = better || worse;
      const color = better ? colors.series[2] : worse ? colors.series[1] : colors.muted;

      ctx.strokeStyle = color;
      ctx.lineWidth = separated ? 2 : 1.5;
      ctx.beginPath();
      ctx.moveTo(sx(item.low), centerY);
      ctx.lineTo(sx(item.high), centerY);
      ctx.moveTo(sx(item.low), centerY - 5);
      ctx.lineTo(sx(item.low), centerY + 5);
      ctx.moveTo(sx(item.high), centerY - 5);
      ctx.lineTo(sx(item.high), centerY + 5);
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(sx(item.value), centerY, separated ? 5 : 4, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = colors.surface;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.fillStyle = separated ? colors.text : colors.secondary;
      ctx.font = separated
        ? "600 12px system-ui, sans-serif"
        : "12px system-ui, sans-serif";
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.fillText(item.label, pad.left - 12, centerY);

      ctx.fillStyle = colors.secondary;
      ctx.font = "11px ui-monospace, Consolas, monospace";
      ctx.textAlign = "left";
      ctx.fillText(
        config.formatValue ? config.formatValue(item.value) : String(item.value),
        Math.max(sx(item.high), sx(item.value)) + 10,
        centerY,
      );

      rects.push({ item, top: centerY - slot / 2, bottom: centerY + slot / 2, color });
    });

    canvas._bars = { rects, config, colors };
    attachBarHover(canvas);
  }

  function render(canvasId, type, config) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const existing = registry.findIndex((entry) => entry.canvasId === canvasId);
    const entry = { canvasId, type, config };
    if (existing >= 0) registry[existing] = entry;
    else registry.push(entry);
    if (type === "line") drawLineChart(canvas, config);
    else if (type === "forest") drawForestChart(canvas, config);
    else drawBarChart(canvas, config);
  }

  function redrawAll() {
    registry.forEach((entry) => {
      const canvas = document.getElementById(entry.canvasId);
      if (!canvas || !canvas.offsetParent) return;
      if (entry.type === "line") drawLineChart(canvas, entry.config);
      else if (entry.type === "forest") drawForestChart(canvas, entry.config);
      else drawBarChart(canvas, entry.config);
    });
  }

  let resizeTimer = null;
  global.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(redrawAll, 120);
  });

  global.Charts = {
    render,
    redrawAll,
    palette,
    withAlpha,
    hideTooltip,
  };
})(window);
