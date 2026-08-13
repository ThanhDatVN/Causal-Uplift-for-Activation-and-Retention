/* Causal Targeting Lab — frontend.
 *
 * App chỉ hiển thị số do API trả về. Nó không tự tính lại metric thống kê; phần
 * duy nhất tính ở client là quy đổi kịch bản value/cost, và phép quy đổi đó được
 * ghi rõ ngay cạnh kết quả.
 */
(function () {
  "use strict";

  const state = {
    bundle: null,
    budget: 0.1,
    audience: 1000000,
    value: 1,
    cost: 0.0005,
    policyModel: null,
    decileModel: null,
    colorMap: null,
    colorOrder: null,
  };

  const el = (id) => document.getElementById(id);

  /* --------------------------------------------------------------- format */

  const nf = (digits) =>
    new Intl.NumberFormat("vi-VN", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });

  function fmt(value, digits = 6) {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return nf(digits).format(value);
  }

  function fmtInt(value) {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(value);
  }

  function fmtPercent(value, digits = 0) {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return `${nf(digits).format(value * 100)}%`;
  }

  /* Thang số ở đây trải từ 1e-5 (giá trị tăng thêm trên mỗi khách hàng) tới 1e6
   * (quy mô population), nên một định dạng cố định sẽ hoặc mất hết chữ số có
   * nghĩa ở đầu nhỏ, hoặc thừa bốn chữ số thập phân ở đầu lớn. */
  function fmtSci(value, digits = 2) {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    if (value === 0) return "0";
    const magnitude = Math.abs(value);
    if (magnitude < 0.001) return value.toExponential(digits);
    if (magnitude < 1) return nf(4).format(value);
    if (magnitude < 1000) return nf(2).format(value);
    return fmtInt(value);
  }

  function shortHash(value) {
    return value ? `${String(value).slice(0, 12)}…` : "—";
  }

  /* ----------------------------------------------------------------- table */

  function buildTable(target, columns, rows, options = {}) {
    const node = typeof target === "string" ? el(target) : target;
    if (!node) return;
    if (!rows || !rows.length) {
      node.innerHTML =
        `<tbody><tr><td>${options.empty || "Chưa có artifact cho bảng này."}</td></tr></tbody>`;
      return;
    }
    const head = columns.map((c) => `<th>${c.title}</th>`).join("");
    const body = rows
      .map((row) => {
        const cls = options.rowClass ? options.rowClass(row) : "";
        const cells = columns
          .map((c) => `<td>${c.render ? c.render(row) : row[c.key] ?? "—"}</td>`)
          .join("");
        return `<tr class="${cls}">${cells}</tr>`;
      })
      .join("");
    node.innerHTML = `<thead><tr>${head}</tr></thead><tbody>${body}</tbody>`;
  }

  function statTile(label, value, sub, tone) {
    return `<div class="stat ${tone || ""}"><div class="label">${label}</div>
      <div class="value">${value}</div><div class="sub">${sub || ""}</div></div>`;
  }

  function ciChip(low, high) {
    if (low === null || low === undefined || high === null || high === undefined) {
      return '<span class="chip neutral">không có CI</span>';
    }
    if (low > 0) return '<span class="chip good">CI &gt; 0</span>';
    if (high < 0) return '<span class="chip warn">CI &lt; 0</span>';
    return '<span class="chip neutral">CI chứa 0</span>';
  }

  /* ------------------------------------------------------------------ tabs */

  function activateTab(name) {
    const tab = document.querySelector(`.tab[data-panel="${name}"]`);
    const panel = el(`panel-${name}`);
    if (!tab || !panel) return false;
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("is-active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("is-active"));
    tab.classList.add("is-active");
    panel.classList.add("is-active");
    window.Charts.redrawAll();
    return true;
  }

  function initTabs() {
    document.querySelectorAll(".tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        const name = tab.dataset.panel;
        activateTab(name);
        // Deep link để chia sẻ đúng tab và để acceptance test chụp từng panel.
        history.replaceState(null, "", `#${name}`);
      });
    });
    window.addEventListener("hashchange", () => {
      activateTab(location.hash.replace("#", ""));
    });
  }

  function applyInitialTab() {
    const requested =
      new URLSearchParams(location.search).get("tab") ||
      location.hash.replace("#", "");
    if (requested) activateTab(requested);
  }

  function initTheme() {
    const stored = localStorage.getItem("ctl-theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const theme = stored || (prefersDark ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", theme);
    el("themeLabel").textContent = theme === "dark" ? "Sáng" : "Tối";
    el("themeToggle").addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme");
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("ctl-theme", next);
      el("themeLabel").textContent = next === "dark" ? "Sáng" : "Tối";
      // Mỗi mode có bộ hex riêng đã validate cho surface của nó, nên bảng màu
      // theo model phải dựng lại chứ không chỉ vẽ lại bằng hex cũ.
      state.colorMap = null;
      if (state.bundle) {
        renderModels(state.bundle);
        renderBudgetChart(state.bundle);
        drawDeciles(state.bundle);
      }
      window.Charts.redrawAll();
    });
  }

  /* -------------------------------------------------------------- overview */

  function renderMeta(meta) {
    el("subtitle").textContent =
      `Champion ${meta.champion} · dữ liệu ${fmtInt(meta.data.rows)} dòng · ` +
      `outcome ${meta.data.outcome}, loại ${meta.data.excluded_post_treatment.join("/")} khỏi feature.`;
    const s2 = meta.sprints.sprint2;
    const s3 = meta.sprints.sprint3;
    el("metaGrid").innerHTML = [
      ["Champion", meta.champion],
      ["Sprint 2 run", s2.run_id || "—"],
      ["Sprint 3 run", s3.run_id || "chưa chạy"],
      ["Confirmation", fmtInt(s3.confirmation_rows || s2.confirmation_rows)],
      ["Data SHA-256", shortHash(meta.data.sha256)],
    ]
      .map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`)
      .join("");

    el("footerText").textContent =
      `Schema ${meta.schema_version} · sinh lúc ${meta.generated_utc} · ` +
      "mọi con số truy được về artifact liệt kê ở tab Bằng chứng.";
  }

  function renderOverview(bundle) {
    const meta = bundle.meta;
    const s3 = meta.sprints.sprint3;
    const models = bundle.models.sprint3_confirmation || [];
    const champion = models.find((m) => m.model === meta.champion);
    const policyRows = bundle.policy_comparison.rows || [];
    const championPolicy =
      policyRows.find((r) => r.policy === `${meta.champion} top-k`) ||
      policyRows.find((r) => String(r.policy).startsWith(meta.champion));

    const tiles = [
      statTile(
        "Champion",
        meta.champion,
        s3.status === "not_run" ? "chốt ở Sprint 2" : "sau promotion rule Sprint 3",
      ),
      statTile(
        "policy_area_dr",
        champion ? fmtSci(champion.policy_area_dr) : "—",
        "metric chính, retrospective confirmation",
      ),
      statTile(
        "Qini",
        champion ? fmt(champion.qini_score, 4) : "—",
        "giữ để so với Sprint 1–2",
      ),
      statTile(
        "Challenger được promote",
        (s3.promoted_challengers || []).length
          ? s3.promoted_challengers.join(", ")
          : "không có",
        (s3.promoted_challengers || []).length
          ? "đạt đủ 3 điều kiện"
          : "chưa challenger nào đạt CI > 0",
        (s3.promoted_challengers || []).length ? "good" : "",
      ),
    ];
    if (championPolicy) {
      tiles.push(
        statTile(
          "DR net / khách hàng",
          fmtSci(championPolicy.dr_net_scenario_value_per_customer),
          `budget ${fmtPercent(championPolicy.budget_fraction)} · CI [${fmtSci(
            championPolicy.dr_ci_low,
          )}; ${fmtSci(championPolicy.dr_ci_high)}]`,
        ),
      );
    }
    el("overviewStats").innerHTML = tiles.join("");

    const evidence = bundle.evidence;
    const rule = evidence.promotion_rule || {};
    el("championBlock").innerHTML =
      `<p class="hint">${meta.champion_selection_note}</p><ul>` +
      Object.entries(rule)
        .map(([key, text]) => `<li><code>${key}</code>: ${text}</li>`)
        .join("") +
      "</ul>";

    const sprints = meta.sprints;
    el("sprintBlock").innerHTML = `<div class="table-scroll"><table>
      <thead><tr><th>Sprint</th><th>Trạng thái</th><th>Rows</th></tr></thead>
      <tbody>
        <tr><td>Sprint 1</td><td>${sprints.sprint1.status}</td><td>${fmtInt(sprints.sprint1.test_rows)}</td></tr>
        <tr><td>Sprint 2</td><td>${sprints.sprint2.status}</td><td>${fmtInt(sprints.sprint2.confirmation_rows)}</td></tr>
        <tr><td>Sprint 3</td><td>${sprints.sprint3.status}</td><td>${fmtInt(sprints.sprint3.confirmation_rows)}</td></tr>
        <tr><td>Causal Forest</td><td>${meta.causal_forest.status}</td><td>—</td></tr>
      </tbody></table></div>
      <p class="hint" style="margin-top:10px">${sprints.sprint3.evidence_note || ""}</p>`;

    buildTable(
      "hierarchyTable",
      [
        { title: "Mức bằng chứng", key: "level" },
        { title: "Rows", render: (r) => fmtInt(r.rows) },
        { title: "Được dùng để", key: "use" },
      ],
      evidence.evidence_hierarchy,
    );
  }

  /* ---------------------------------------------------------------- models */

  function renderModels(bundle) {
    const rows = bundle.models.sprint3_confirmation || [];
    const champion = bundle.meta.champion;
    const colors = window.Charts.palette();

    if (rows.length) {
      el("modelChartHint").textContent =
        "policy_area_dr là trung bình conversion tăng thêm trên mỗi khách hàng ở dải " +
        "budget 1–30%, chấm bằng doubly robust signal. Cao hơn là tốt hơn.";
      // Một series duy nhất: champion lấy slot màu 1, phần còn lại dùng xám chìm.
      // Dùng hue categorical thứ hai cho "không phải champion" sẽ ngụ ý một danh
      // tính mà biểu đồ không hề mã hóa.
      window.Charts.render("modelBarChart", "bar", {
        items: rows.map((r) => ({
          label: r.model,
          value: r.policy_area_dr,
          color: r.model === champion ? colors.series[0] : colors.muted,
          emphasis: r.model === champion,
          extra: [
            ["AUTOC", fmtSci(r.autoc_dr)],
            ["Qini", fmt(r.qini_score, 4)],
          ],
        })),
        valueLabel: "policy_area_dr",
        formatValue: (v) => fmtSci(v),
        labelWidth: 170,
      });
      el("modelBarCaption").innerHTML =
        `Cột đậm là champion hiện hành (${champion}). Nguồn: ` +
        `<code>${bundle.models.sources.sprint3_confirmation}</code>.`;
    } else {
      el("modelChartHint").textContent =
        "Chưa có kết quả Sprint 3; bảng dưới hiển thị confirmation Sprint 2.";
      el("modelBarCaption").textContent = "";
    }

    const sprint3Columns = [
      { title: "Model", key: "model" },
      { title: "policy_area_dr", render: (r) => fmtSci(r.policy_area_dr) },
      { title: "AUTOC", render: (r) => fmtSci(r.autoc_dr) },
      { title: "AUTOC adjusted", render: (r) => fmtSci(r.autoc_dr_adjusted) },
      { title: "Qini", render: (r) => fmt(r.qini_score, 6) },
      { title: "AUUC", render: (r) => fmt(r.auuc_score, 6) },
      { title: "EUCE", render: (r) => fmtSci(r.uplift_calibration_error) },
      { title: "Score âm", render: (r) => fmtPercent(r.negative_score_fraction, 1) },
    ];
    const sprint2Columns = [
      { title: "Model", key: "model" },
      { title: "Nhãn", key: "model_label" },
      { title: "Qini", render: (r) => fmt(r.qini_score, 6) },
      { title: "AUUC", render: (r) => fmt(r.auuc_score, 6) },
      { title: "EUCE", render: (r) => fmtSci(r.uplift_calibration_error) },
    ];
    buildTable(
      "modelTable",
      rows.length ? sprint3Columns : sprint2Columns,
      rows.length ? rows : bundle.models.sprint2_confirmation,
      { rowClass: (r) => (r.model === champion ? "is-champion" : "") },
    );

    const pairwise =
      bundle.pairwise.sprint3_policy_area || bundle.pairwise.sprint2_qini || [];
    if (bundle.pairwise.sprint3_policy_area) {
      buildTable(
        "pairwiseTable",
        [
          { title: "A", key: "model_a" },
          { title: "B", key: "model_b" },
          { title: "Δ policy_area", render: (r) => fmtSci(r.policy_area_difference) },
          {
            title: "CI 95%",
            render: (r) =>
              `[${fmtSci(r.policy_area_ci_low)}; ${fmtSci(r.policy_area_ci_high)}]`,
          },
          {
            title: "Kết luận",
            render: (r) => ciChip(r.policy_area_ci_low, r.policy_area_ci_high),
          },
          { title: "Δ AUTOC", render: (r) => fmtSci(r.autoc_difference) },
          { title: "P(Δ>0)", render: (r) => fmt(r.policy_area_probability_positive, 3) },
        ],
        pairwise,
      );
    } else {
      buildTable(
        "pairwiseTable",
        [
          { title: "A", key: "model_a" },
          { title: "B", key: "model_b" },
          { title: "Δ Qini", render: (r) => fmt(r.observed_difference, 6) },
          { title: "CI 95%", render: (r) => `[${fmt(r.ci_low, 6)}; ${fmt(r.ci_high, 6)}]` },
          { title: "Kết luận", render: (r) => ciChip(r.ci_low, r.ci_high) },
        ],
        pairwise,
      );
    }

    const oof = bundle.models.oof_finalist || bundle.models.oof_screen || [];
    const oofSource =
      bundle.models.sources.oof_finalist || bundle.models.sources.oof_screen;
    el("oofHint").innerHTML = oof.length
      ? `Cross-fitting 3 fold trên development pool. Mọi dòng chỉ được chấm bởi model ` +
        `không fit trên dòng đó. Nguồn: <code>${oofSource}</code>.`
      : "Chưa có kết quả OOF.";
    buildTable(
      "oofTable",
      [
        { title: "Candidate", key: "candidate" },
        {
          title: "Trạng thái",
          render: (r) =>
            r.status === "failed"
              ? `<span class="chip warn">${r.failure_reason || "failed"}</span>`
              : `<span class="chip neutral">${r.status}</span>`,
        },
        { title: "Pool", render: (r) => fmtPercent(r.pool_fraction, 0) },
        { title: "policy_area_dr", render: (r) => fmtSci(r.policy_area_dr) },
        { title: "AUTOC", render: (r) => fmtSci(r.autoc_dr) },
        { title: "Qini", render: (r) => fmt(r.qini_score, 6) },
        { title: "DR risk", render: (r) => fmtSci(r.doubly_robust_risk) },
        { title: "Fit (s)", render: (r) => fmt(r.fit_seconds, 1) },
        { title: "Peak RSS (GB)", render: (r) => fmt(r.peak_process_rss_gb, 2) },
      ],
      oof,
    );
  }

  /* ---------------------------------------------------------------- policy */

  function budgetCurveSeries(bundle) {
    const rows = bundle.budget_curve.rows || [];
    const grouped = new Map();
    rows.forEach((row) => {
      if (!grouped.has(row.model)) grouped.set(row.model, []);
      grouped.get(row.model).push(row);
    });
    return grouped;
  }

  /* Màu bám theo tên model, không bám theo thứ tự hiển thị. Nếu gán màu theo vị
   * trí sau khi sắp xếp, việc đổi model trong ô chọn sẽ sơn lại các đường còn lại
   * và người đọc vừa học "X-Renormalized màu cam" sẽ bị dẫn sai. Bảng màu được
   * khóa một lần theo thứ tự chữ cái của toàn bộ model có trong artifact. */
  function modelColorMap(bundle) {
    if (state.colorMap) return state.colorMap;
    const colors = window.Charts.palette();
    const names = Array.from(budgetCurveSeries(bundle).keys())
      .filter((name) => !name.startsWith("Expected random"))
      .sort();
    const map = new Map();
    names.forEach((name, index) => {
      map.set(name, colors.series[index % colors.series.length]);
    });
    state.colorMap = map;
    state.colorOrder = names;
    return map;
  }

  function renderPolicyControls(bundle) {
    const grouped = budgetCurveSeries(bundle);
    const names = Array.from(grouped.keys()).filter(
      (n) => !n.startsWith("Expected random"),
    );
    const select = el("policyModel");
    select.innerHTML = names.map((n) => `<option value="${n}">${n}</option>`).join("");
    const champion = bundle.meta.champion;
    const preferred =
      names.find((n) => n === champion) ||
      names.find((n) => n.startsWith(champion)) ||
      names[0];
    select.value = preferred;
    state.policyModel = preferred;
  }

  function renderBudgetChart(bundle) {
    const grouped = budgetCurveSeries(bundle);
    const colors = window.Charts.palette();
    const champion = bundle.meta.champion;
    const names = Array.from(grouped.keys()).filter(
      (n) => !n.startsWith("Expected random"),
    );
    // Ưu tiên champion, rồi các model còn lại theo giá trị tại budget lớn nhất.
    names.sort((a, b) => {
      if (a === state.policyModel) return -1;
      if (b === state.policyModel) return 1;
      const av = grouped.get(a).slice(-1)[0].gross_value_per_customer;
      const bv = grouped.get(b).slice(-1)[0].gross_value_per_customer;
      return bv - av;
    });
    const shown = names.slice(0, 4);
    const colorFor = modelColorMap(bundle);
    const series = shown.map((name) => ({
      label: name,
      color: colorFor.get(name) || colors.series[0],
      // Chỉ model đang chọn hiển thị dải CI và direct label; các model còn lại vẽ
      // đường trơn và dựa vào legend.
      band: name === state.policyModel,
      emphasis: name === state.policyModel,
      points: grouped
        .get(name)
        .map((r) => ({
          x: r.budget_fraction,
          y: r.gross_value_per_customer,
          low: r.ci_low,
          high: r.ci_high,
        }))
        .sort((a, b) => a.x - b.x),
    }));
    const random = grouped.get("Expected random (stochastic policy)");
    if (random) {
      series.push({
        label: "Random kỳ vọng",
        color: colors.muted,
        dashed: true,
        points: random
          .map((r) => ({ x: r.budget_fraction, y: r.gross_value_per_customer }))
          .sort((a, b) => a.x - b.x),
      });
    }

    el("budgetCaption").innerHTML =
      `<div class="legend">${series
        .map(
          (s) =>
            `<span class="legend-item"><span class="legend-swatch ${
              s.dashed ? "dashed" : ""
            }" style="${s.dashed ? "" : `background:${s.color}`}"></span>${s.label}</span>`,
        )
        .join("")}</div>` +
      `Nguồn: <code>${bundle.budget_curve.source}</code> · ` +
      `mức bằng chứng <code>${bundle.budget_curve.evidence_class}</code>.` +
      (names.length > shown.length
        ? ` Hiển thị ${shown.length}/${names.length} model; xem đủ ở bảng bên dưới.`
        : "");

    window.Charts.render("budgetChart", "line", {
      series,
      height: 340,
      yZero: true,
      xLabel: "Budget",
      xTicks: [0.01, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3],
      formatX: (v) => `${(v * 100).toFixed(0)}%`,
      formatY: (v) => fmtSci(v, 1),
      formatValue: (v) => fmtSci(v, 2),
    });

    const rows = bundle.budget_curve.rows || [];
    buildTable(
      "budgetTable",
      [
        { title: "Model", key: "model" },
        { title: "Budget", render: (r) => fmtPercent(r.budget_fraction, 0) },
        { title: "Gross / khách hàng", render: (r) => fmtSci(r.gross_value_per_customer) },
        { title: "CI 95%", render: (r) => `[${fmtSci(r.ci_low)}; ${fmtSci(r.ci_high)}]` },
        { title: "Chi phí hòa vốn", render: (r) => fmtSci(r.break_even_contact_cost) },
      ],
      rows,
    );
  }

  async function runSimulation() {
    const body = {
      budget_fraction: state.budget,
      audience: state.audience,
      value_per_conversion: state.value,
      contact_cost: state.cost,
      model: state.policyModel,
    };
    let result;
    try {
      const response = await fetch("/api/policy/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(await response.text());
      result = await response.json();
    } catch (error) {
      el("policyDetail").innerHTML =
        `<p class="status-line error">Không mô phỏng được: ${error.message}</p>`;
      return;
    }

    const positive = result.net_scenario_value_per_customer > 0;
    el("policyStats").innerHTML = [
      statTile(
        "Conversion tăng thêm",
        fmtInt(result.total_incremental_conversions),
        `CI [${fmtInt(result.total_incremental_conversions_ci_low)}; ${fmtInt(
          result.total_incremental_conversions_ci_high,
        )}] trên ${fmtInt(state.audience)} khách hàng`,
      ),
      statTile(
        "Giá trị ròng kịch bản",
        fmtSci(result.total_net_scenario_value, 2),
        `${fmtSci(result.net_scenario_value_per_customer)} / khách hàng`,
        positive ? "good" : "critical",
      ),
      statTile(
        "Số khách được target",
        fmtInt(result.targeted_customers),
        `chi phí liên hệ ${fmtSci(result.total_contact_cost, 2)}`,
      ),
      statTile(
        "Chi phí hòa vốn",
        fmtSci(result.break_even_contact_cost),
        "trên mỗi contact, cùng đơn vị với giá trị nhập",
      ),
    ].join("");

    el("policyDetail").innerHTML = `
      ${result.guardrail_warning ? `<p class="status-line warning">${result.guardrail_warning}</p>` : ""}
      <p class="hint" style="margin-top:14px">
        Model <code>${result.model}</code> · mức bằng chứng
        <code>${result.evidence_class}</code> · nguồn <code>${result.source}</code>.
      </p>
      <p class="hint">
        Công thức: giá trị ròng trên mỗi khách hàng =
        <code>value × G(b) − b × cost</code>, với <code>G(b)</code> là conversion tăng
        thêm trên mỗi khách hàng khi target top <code>b</code>, ước lượng bằng doubly
        robust signal. ${result.interpretation}
      </p>`;
  }

  function initPolicyControls() {
    const slider = el("budgetSlider");
    const sync = () => {
      state.budget = Number(slider.value) / 100;
      el("budgetText").textContent = slider.value;
      runSimulation();
    };
    slider.addEventListener("input", () => {
      el("budgetText").textContent = slider.value;
    });
    slider.addEventListener("change", sync);

    [
      ["audience", "audience", (v) => Math.max(1, Math.round(v))],
      ["conversionValue", "value", (v) => Math.max(1e-9, v)],
      ["contactCost", "cost", (v) => Math.max(0, v)],
    ].forEach(([id, key, clamp]) => {
      el(id).addEventListener("change", () => {
        const raw = Number(el(id).value);
        state[key] = clamp(Number.isFinite(raw) ? raw : state[key]);
        el(id).value = state[key];
        runSimulation();
      });
    });

    el("policyModel").addEventListener("change", () => {
      state.policyModel = el("policyModel").value;
      renderBudgetChart(state.bundle);
      runSimulation();
    });

    document.querySelectorAll("[data-scenario]").forEach((button) => {
      button.addEventListener("click", () => {
        const scenario = button.dataset.scenario;
        if (scenario === "low") {
          state.cost = 0.00025;
          state.budget = 0.2;
        } else if (scenario === "high") {
          state.cost = 0.001;
          state.budget = 0.05;
        } else if (scenario === "none") {
          state.budget = 0.01;
        } else {
          state.cost = 0.0005;
          state.budget = 0.1;
          state.value = 1;
          state.audience = 1000000;
        }
        el("contactCost").value = state.cost;
        el("conversionValue").value = state.value;
        el("audience").value = state.audience;
        slider.value = Math.round(state.budget * 100);
        el("budgetText").textContent = slider.value;
        runSimulation();
      });
    });
  }

  function renderSensitivity(bundle) {
    const rows = bundle.sensitivity.rows || [];
    const champion = bundle.meta.champion;
    const relevant = rows.filter(
      (r) => String(r.policy).startsWith(champion) || r.policy === "Treat none",
    );
    const budgets = Array.from(new Set(relevant.map((r) => r.budget_fraction))).sort(
      (a, b) => a - b,
    );
    const costs = Array.from(
      new Set(relevant.map((r) => r.contact_cost_assumption)),
    ).sort((a, b) => a - b);
    const lookup = new Map();
    relevant.forEach((r) => {
      if (r.policy === "Treat none") return;
      lookup.set(`${r.budget_fraction}|${r.contact_cost_assumption}`, r);
    });
    const columns = [{ title: "Budget", render: (r) => fmtPercent(r.budget, 0) }].concat(
      costs.map((cost) => ({
        title: `cost ${fmtSci(cost, 2)}`,
        render: (r) => {
          const hit = lookup.get(`${r.budget}|${cost}`);
          if (!hit) return "—";
          const net = hit.net_scenario_value_per_customer_dr;
          const cls = net > 0 ? "good" : "warn";
          return `<span class="chip ${cls}">${fmtSci(net)}</span>`;
        },
      })),
    );
    buildTable(
      "sensitivityTable",
      columns,
      budgets.map((budget) => ({ budget })),
      { empty: "Chưa có bảng độ nhạy." },
    );
  }

  /* -------------------------------------------------------------- segments */

  function renderSegments(bundle) {
    const rows = bundle.deciles.rows || [];
    const models = Array.from(new Set(rows.map((r) => r.model)));
    const select = el("decileModel");
    select.innerHTML = models.map((m) => `<option value="${m}">${m}</option>`).join("");
    state.decileModel =
      models.find((m) => m === bundle.meta.champion) || models[0] || null;
    if (state.decileModel) select.value = state.decileModel;
    select.addEventListener("change", () => {
      state.decileModel = select.value;
      drawDeciles(bundle);
    });
    drawDeciles(bundle);

    const diagnostics = bundle.diagnostics;
    el("balanceNote").textContent = diagnostics.balance_note || "";
    buildTable(
      "armTable",
      [
        { title: "Treatment", render: (r) => (r.treatment === 1 ? "Treated" : "Control") },
        { title: "Rows", render: (r) => fmtInt(r.row_count) },
        { title: "Conversion rate", render: (r) => fmtSci(r.conversion_rate) },
        { title: "Conversions", render: (r) => fmtInt(r.conversion_count) },
      ],
      diagnostics.arm_summary,
    );
    buildTable(
      "balanceTable",
      [
        { title: "Feature", key: "feature" },
        { title: "Mean treated", render: (r) => fmt(r.mean_treatment, 4) },
        { title: "Mean control", render: (r) => fmt(r.mean_control, 4) },
        { title: "|SMD|", render: (r) => fmt(r.abs_smd, 4) },
      ],
      diagnostics.balance_smd,
    );
  }

  function drawDeciles(bundle) {
    const rows = (bundle.deciles.rows || []).filter(
      (r) => r.model === state.decileModel,
    );
    if (!rows.length) return;
    const colors = window.Charts.palette();
    window.Charts.render("decileChart", "bar", {
      items: rows
        .sort((a, b) => a.decile - b.decile)
        .map((r) => ({
          label: `Decile ${r.decile}`,
          value: r.decile_observed_uplift_rate,
          low: r.decile_uplift_ci_low,
          high: r.decile_uplift_ci_high,
          color: r.decile === 1 ? colors.series[0] : colors.muted,
          emphasis: r.decile === 1,
          extra: [
            ["Rows", fmtInt(r.n_decile)],
            ["Tích lũy", fmtSci(r.cumulative_observed_uplift_rate)],
          ],
        })),
      valueLabel: "Uplift quan sát",
      formatValue: (v) => fmtSci(v, 2),
      labelWidth: 100,
      height: 340,
    });
    el("decileCaption").innerHTML =
      "Thanh ngang là khoảng tin cậy 95% của uplift trong decile. " +
      `Nguồn: <code>${bundle.deciles.source}</code>. ${bundle.deciles.note}`;
    buildTable(
      "decileTable",
      [
        { title: "Decile", key: "decile" },
        { title: "Rows", render: (r) => fmtInt(r.n_decile) },
        { title: "Mean score", render: (r) => fmtSci(r.mean_score_decile) },
        { title: "Uplift", render: (r) => fmtSci(r.decile_observed_uplift_rate) },
        {
          title: "CI 95%",
          render: (r) =>
            `[${fmtSci(r.decile_uplift_ci_low)}; ${fmtSci(r.decile_uplift_ci_high)}]`,
        },
        {
          title: "Incremental tích lũy",
          render: (r) => fmtInt(r.estimated_incremental_conversions_cumulative),
        },
        {
          title: "Tỷ trọng",
          render: (r) => fmtPercent(r.share_of_full_incremental_estimate, 1),
        },
      ],
      rows,
    );
  }

  /* --------------------------------------------------------------- scoring */

  function renderScoreResult(result) {
    const preview = result.scores.slice(0, 200).map((score, index) => ({
      index: index + 1,
      score,
      percentile: result.population_percentile[index],
      targeted: result.targeted[index],
    }));
    el("scoreResult").innerHTML = `
      <div class="stat-row" style="margin-top:16px">
        ${statTile("Model", result.model, result.family)}
        ${statTile("Số dòng", fmtInt(result.n_rows), `${fmtInt(result.n_targeted)} được target`)}
        ${statTile("Ngưỡng score", fmtSci(result.score_threshold), `cơ sở: ${result.threshold_basis}`)}
        ${statTile("Budget", fmtPercent(result.budget_fraction, 0), "top-k theo score")}
      </div>
      <p class="hint">${result.score_note} Scorer fit trên: <code>${result.fitted_on || "—"}</code>.</p>
      <details open><summary>200 dòng đầu</summary><div class="table-scroll"><table id="scoreTable"></table></div></details>`;
    buildTable(
      "scoreTable",
      [
        { title: "#", key: "index" },
        { title: "Score", render: (r) => fmtSci(r.score) },
        { title: "Phân vị population", render: (r) => `${fmt(r.percentile, 1)}%` },
        {
          title: "Quyết định",
          render: (r) =>
            r.targeted
              ? '<span class="chip good">target</span>'
              : '<span class="chip neutral">bỏ qua</span>',
        },
      ],
      preview,
    );
  }

  function setScoreStatus(message, kind) {
    const node = el("scoreStatus");
    node.textContent = message;
    node.className = `status-line ${kind || ""}`;
  }

  function initScoring(bundle) {
    el("scoringHint").innerHTML = bundle.scorer_available
      ? "Scorer champion đã fit trên development pool và được nạp sẵn. Score là điểm ưu " +
        "tiên để xếp hạng, không phải xác suất conversion cá nhân."
      : '<span class="chip warn">Chưa có scorer</span> Chạy ' +
        "<code>scripts/build_champion_scorer.py</code> để bật tính năng này.";

    el("scoreCsvBtn").addEventListener("click", async () => {
      const file = el("csvInput").files[0];
      if (!file) {
        setScoreStatus("Chưa chọn file CSV.", "error");
        return;
      }
      setScoreStatus("Đang chấm điểm…");
      const form = new FormData();
      form.append("file", file);
      try {
        const response = await fetch(
          `/api/score/csv?budget_fraction=${state.budget}`,
          { method: "POST", body: form },
        );
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || "lỗi không xác định");
        setScoreStatus(`Đã chấm ${fmtInt(payload.n_rows)} dòng.`, "ok");
        renderScoreResult(payload);
      } catch (error) {
        setScoreStatus(`Lỗi: ${error.message}`, "error");
      }
    });

    el("scoreManualBtn").addEventListener("click", async () => {
      const text = el("manualRows").value.trim();
      if (!text) {
        setScoreStatus("Chưa nhập dòng nào.", "error");
        return;
      }
      const rows = text
        .split("\n")
        .map((line) => line.split(",").map((v) => Number(v.trim())))
        .filter((row) => row.length > 1);
      if (!rows.length || rows.some((r) => r.length !== bundle.feature_names.length)) {
        setScoreStatus(
          `Mỗi dòng phải có đúng ${bundle.feature_names.length} giá trị.`,
          "error",
        );
        return;
      }
      setScoreStatus("Đang chấm điểm…");
      try {
        const response = await fetch("/api/score", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rows, budget_fraction: state.budget }),
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || "lỗi không xác định");
        setScoreStatus(`Đã chấm ${fmtInt(payload.n_rows)} dòng.`, "ok");
        renderScoreResult(payload);
      } catch (error) {
        setScoreStatus(`Lỗi: ${error.message}`, "error");
      }
    });

    el("sampleCsvBtn").addEventListener("click", () => {
      const header = bundle.feature_names.join(",");
      const lines = [header];
      for (let i = 0; i < 20; i += 1) {
        lines.push(
          bundle.feature_names
            .map(() => (Math.random() * 20 - 2).toFixed(4))
            .join(","),
        );
      }
      const blob = new Blob([lines.join("\n")], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "sample_features.csv";
      link.click();
      URL.revokeObjectURL(url);
      setScoreStatus(
        "Đã tải CSV mẫu. Giá trị là số ngẫu nhiên để kiểm tra định dạng, không phải " +
          "khách hàng thật.",
      );
    });
  }

  /* -------------------------------------------------------------- evidence */

  async function renderEvidence(bundle) {
    el("limitationList").innerHTML = bundle.evidence.limitations
      .map((item) => `<li>${item}</li>`)
      .join("");
    el("assumptionList").innerHTML = bundle.evidence.assumptions
      .map((item) => `<li>${item}</li>`)
      .join("");
    buildTable(
      "artifactTable",
      [
        { title: "Artifact", key: "name" },
        { title: "Đường dẫn", render: (r) => `<code>${r.path}</code>` },
        {
          title: "Trạng thái",
          render: (r) =>
            r.available
              ? '<span class="chip good">có</span>'
              : '<span class="chip neutral">chưa có</span>',
        },
      ],
      bundle.meta.artifacts,
    );

    el("registryHint").innerHTML = bundle.registry.source
      ? `${fmtInt(bundle.registry.row_count)} run đã ghi. Nguồn: <code>${bundle.registry.source}</code>.`
      : "Chưa có registry.";
    buildTable(
      "registryTable",
      [
        { title: "Candidate", key: "candidate" },
        {
          title: "Trạng thái",
          render: (r) =>
            r.status === "failed"
              ? `<span class="chip warn">${r.failure_reason || "failed"}</span>`
              : `<span class="chip neutral">${r.status}</span>`,
        },
        { title: "Pool", render: (r) => fmtPercent(r.pool_fraction, 0) },
        { title: "Rows", render: (r) => fmtInt(r.n_rows) },
        { title: "Conv. control", render: (r) => fmtInt(r.n_conversion_control) },
        { title: "policy_area_dr", render: (r) => fmtSci(r.policy_area_dr) },
        { title: "Fit (s)", render: (r) => fmt(r.fit_seconds, 1) },
        { title: "Config", render: (r) => `<code>${r.config_hash || "—"}</code>` },
      ],
      bundle.registry.rows,
    );

    try {
      const response = await fetch("/api/export");
      const payload = await response.json();
      el("exportActions").innerHTML = Object.entries(payload.datasets)
        .map(([key, value]) =>
          value.available
            ? `<a class="btn" href="${value.url}" download>${key}.csv</a>`
            : `<span class="btn" style="opacity:.45;cursor:not-allowed">${key} (chưa có)</span>`,
        )
        .join("");
    } catch (error) {
      el("exportActions").innerHTML =
        `<span class="status-line error">Không tải được danh sách export: ${error.message}</span>`;
    }
  }

  /* ------------------------------------------------------------------ boot */

  async function boot() {
    initTheme();
    initTabs();
    try {
      const response = await fetch("/api/bundle");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      state.bundle = await response.json();
    } catch (error) {
      el("subtitle").textContent = `Không tải được dữ liệu: ${error.message}`;
      return;
    }
    const bundle = state.bundle;
    renderMeta(bundle.meta);
    renderOverview(bundle);
    renderModels(bundle);
    renderPolicyControls(bundle);
    renderBudgetChart(bundle);
    renderSensitivity(bundle);
    initPolicyControls();
    renderSegments(bundle);
    initScoring(bundle);
    await renderEvidence(bundle);
    await runSimulation();
    applyInitialTab();
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
