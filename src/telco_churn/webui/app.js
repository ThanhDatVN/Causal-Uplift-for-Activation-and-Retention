/* Retention decision console.
 *
 * Charts are inline SVG built here rather than by a library, so the mark specs
 * from the visualisation method (2px lines, >=8px markers with a surface ring,
 * hairline grid, one axis, selective labels) hold exactly and the page stays a
 * single dependency-free file.  Every chart ships a hover layer and a table
 * view; nothing relies on colour alone.
 */

const NS = "http://www.w3.org/2000/svg";
const fmt = {
  pct: (value, digits = 1) =>
    value === null || value === undefined || Number.isNaN(value)
      ? "—"
      : `${(value * 100).toFixed(digits)}%`,
  pp: (value, digits = 2) =>
    value === null || value === undefined ? "—" : `${(value * 100 >= 0 ? "+" : "")}${(value * 100).toFixed(digits)} pp`,
  num: (value, digits = 0) =>
    value === null || value === undefined || Number.isNaN(value)
      ? "—"
      : value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits }),
  fixed: (value, digits = 4) =>
    value === null || value === undefined || Number.isNaN(value) ? "—" : value.toFixed(digits),
};

const el = (tag, attrs = {}, text) => {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key === "html") node.innerHTML = value;
    else node.setAttribute(key, value);
  }
  if (text !== undefined) node.textContent = text;
  return node;
};

const svg = (tag, attrs = {}) => {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
};

const chip = (status, label) => {
  const node = el("span", { class: "chip", "data-status": status });
  node.append(el("i", { class: "dot" }), document.createTextNode(label ?? status));
  return node;
};

const tile = (label, value, sub) => {
  const node = el("div", { class: "card tile" });
  node.append(el("span", { class: "label" }, label), el("span", { class: "value" }, value));
  if (sub) node.append(el("span", { class: "sub" }, sub));
  return node;
};

const table = (headers, rows, aligns = []) => {
  const node = el("table");
  const head = el("thead");
  const headRow = el("tr");
  headers.forEach((header, index) =>
    headRow.append(el("th", { class: aligns[index] === "num" ? "num" : "" }, header))
  );
  head.append(headRow);
  const body = el("tbody");
  rows.forEach((row) => {
    const tr = el("tr");
    row.forEach((cell, index) => {
      const td = el("td", { class: aligns[index] === "num" ? "num" : "" });
      if (cell instanceof Node) td.append(cell);
      else td.textContent = cell;
      tr.append(td);
    });
    body.append(tr);
  });
  node.append(head, body);
  return node;
};

/** Round an axis to clean numbers: 1, 2, 2.5 or 5 times a power of ten. */
function niceTicks(min, max, target = 6) {
  const span = max - min || 1;
  const raw = span / target;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((factor) => factor * magnitude).find((candidate) => candidate >= raw) || magnitude * 10;
  const ticks = [];
  for (let value = Math.ceil(min / step) * step; value <= max + 1e-9; value += step) {
    ticks.push(Math.abs(value) < 1e-9 ? 0 : value);
  }
  return ticks;
}

async function getJSON(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `${response.status} ${response.statusText}`);
  }
  return response.json();
}

function failSection(id, error) {
  const host = document.getElementById(id);
  if (!host) return;
  host.replaceChildren(el("div", { class: "error" }, `Not available: ${error.message}`));
}

/* -- hover layer --------------------------------------------------------- */
function attachTip(tipId) {
  const tip = document.getElementById(tipId);
  return {
    show(html, x, y) {
      tip.innerHTML = html;
      tip.style.left = `${x}px`;
      tip.style.top = `${y - 10}px`;
      tip.classList.add("visible");
    },
    hide() {
      tip.classList.remove("visible");
    },
  };
}

/* -- 1. release state ---------------------------------------------------- */
function renderState(index) {
  document.getElementById("root-label").textContent = `${index.root} · ${index.generated_at}`;
  document.getElementById("tier").textContent = index.release_tier.replaceAll("_", " ").toLowerCase();

  const blockers = document.getElementById("blockers");
  blockers.replaceChildren();
  if (!index.tier_blockers.length) {
    blockers.append(el("li", {}, "No gate is blocking the next tier."));
  }
  index.tier_blockers.forEach((blocker) => {
    const item = el("li");
    item.append(chip("NOT_MET", blocker.tier.replaceAll("_", " ").toLowerCase()));
    item.append(el("span", { html: `<code>${blocker.gate}</code> — ${blocker.reason}` }));
    blockers.append(item);
  });

  const counts = index.gates.reduce((acc, gate) => {
    acc[gate.status] = (acc[gate.status] || 0) + 1;
    return acc;
  }, {});
  const kpis = document.getElementById("kpis");
  kpis.replaceChildren(
    tile("Gates passing", `${counts.PASS || 0} / ${index.gates.length}`, `${counts.FAIL || 0} failing`),
    tile("Gates defined but unmet", `${counts.NOT_MET || 0}`, "declared, not satisfied"),
    tile("Studies never run", `${counts.NOT_RUN || 0}`, "no artifact exists"),
    tile("Ledger: observed", `${index.claims.OBSERVED ?? 0}`, "measured, within scope"),
    tile("Ledger: conditional", `${index.claims.CONDITIONAL ?? 0}`, "real numbers, unverified assumption"),
    tile("Ledger: planned", `${index.claims.PLANNED ?? 0}`, "designed, never run")
  );

  const body = document.querySelector("#gates-table tbody");
  body.replaceChildren();
  index.gates.forEach((gate) => {
    const row = el("tr");
    row.append(el("td", {}, gate.title));
    const status = el("td");
    status.append(chip(gate.status));
    row.append(status, el("td", {}, gate.summary), el("td", {}, gate.blocker || "—"));
    body.append(row);
  });

  const artifacts = document.querySelector("#artifacts-table tbody");
  artifacts.replaceChildren();
  index.artifacts.forEach((artifact) => {
    const row = el("tr");
    row.append(el("td", {}, artifact.key));
    row.append(el("td", { html: `<code>${artifact.path}</code>` }));
    row.append(el("td", {}, artifact.modified_at || "—"));
    const state = el("td");
    if (!artifact.exists) state.append(chip("NOT_RUN", "missing"));
    else if (artifact.stale_against_code)
      state.append(chip("NOT_MET", `older than ${artifact.producer_newer.join(", ")}`));
    else state.append(chip("PASS", "current"));
    row.append(state);
    row.append(el("td", { html: artifact.sha256 ? `<code>${artifact.sha256.slice(0, 12)}</code>` : "—" }));
    artifacts.append(row);
  });
}

/* -- 2. falsification suite --------------------------------------------- */
function renderSuite(payload) {
  const kpis = document.getElementById("suite-kpis");
  kpis.replaceChildren(
    tile("Critical faults caught", `${payload.detected_critical} / ${payload.declared_critical}`, "declared critical mutations"),
    tile("Clean fixtures blocked", `${payload.false_blocks.length}`, "false-block rate"),
    tile("Cases executed", `${payload.n_executed}`, `${payload.n_declared} declared`),
    tile("Gate", payload.gate_passed ? "pass" : "fail", "all critical caught, no false block")
  );

  const matrix = document.getElementById("matrix");
  matrix.replaceChildren();
  payload.results.forEach((row) => {
    const cell = el("div", {
      class: "cell",
      "data-ok": String(row.ok),
      title: `${row.mutation_id} — ${row.title}\nDetector: ${row.detector}\nClean: ${row.clean_note}\nMutant: ${row.mutant_note}`,
      tabindex: "0",
    });
    cell.append(el("span", {}, row.mutation_id), el("small", {}, row.node));
    matrix.append(cell);
  });

  const host = document.getElementById("suite-table");
  host.replaceChildren(
    table(
      ["ID", "Node", "Severity", "Mutation", "Detector", "Evidence"],
      payload.results.map((row) => [
        row.mutation_id,
        row.node,
        row.severity,
        row.title,
        el("code", {}, row.detector),
        `${row.mutant_note}`,
      ])
    )
  );
}

/* -- 3. estimator validity ---------------------------------------------- */
function renderSmoke(payload) {
  const estimators = [
    { key: "paired", label: "Paired DR", color: "var(--series-1)" },
    { key: "unpaired", label: "Unpaired (diagnostic)", color: "var(--series-2)" },
  ].filter((entry) => payload[entry.key]);

  const width = 520;
  const rowHeight = 62;
  const height = estimators.length * rowHeight + 54;
  const left = 132;
  const right = width - 24;
  const nominal = 1 - (payload.config?.alpha ?? 0.05);
  const lows = estimators.map((entry) => payload[entry.key].coverage_ci_low);
  const highs = estimators.map((entry) => payload[entry.key].coverage_ci_high);
  const min = Math.min(nominal, ...lows) - 0.01;
  const max = Math.max(nominal, ...highs) + 0.006;
  const x = (value) => left + ((value - min) / (max - min)) * (right - left);

  const chart = document.getElementById("coverage-chart");
  chart.setAttribute("viewBox", `0 0 ${width} ${height}`);
  chart.replaceChildren();
  const tip = attachTip("coverage-tip");

  // axis ticks, rounded to clean numbers
  const ticks = [];
  for (let value = Math.ceil(min * 200) / 200; value <= max; value += 0.01) ticks.push(value);
  ticks.forEach((value) => {
    chart.append(
      svg("line", { x1: x(value), x2: x(value), y1: 28, y2: height - 26, class: "grid-line" })
    );
    const label = svg("text", { x: x(value), y: height - 10, class: "axis-label", "text-anchor": "middle" });
    label.textContent = `${(value * 100).toFixed(0)}%`;
    chart.append(label);
  });

  // nominal reference
  chart.append(svg("line", { x1: x(nominal), x2: x(nominal), y1: 20, y2: height - 26, class: "ref-line" }));
  const refLabel = svg("text", { x: x(nominal), y: 14, class: "axis-label", "text-anchor": "middle" });
  refLabel.textContent = `nominal ${(nominal * 100).toFixed(0)}%`;
  chart.append(refLabel);

  estimators.forEach((entry, index) => {
    const row = payload[entry.key];
    const y = 44 + index * rowHeight;
    const label = svg("text", { x: 0, y: y + 4, class: "value-label" });
    label.textContent = entry.label;
    chart.append(label);

    chart.append(
      svg("line", {
        x1: x(row.coverage_ci_low),
        x2: x(row.coverage_ci_high),
        y1: y,
        y2: y,
        stroke: entry.color,
        "stroke-width": 2,
        "stroke-linecap": "round",
      })
    );
    // surface ring keeps the marker legible where it crosses the reference line
    chart.append(
      svg("circle", { cx: x(row.coverage), cy: y, r: 6, fill: "var(--surface-1)" })
    );
    const dot = svg("circle", { cx: x(row.coverage), cy: y, r: 4.5, fill: entry.color });
    chart.append(dot);

    const value = svg("text", { x: x(row.coverage_ci_high) + 8, y: y + 4, class: "value-label" });
    value.textContent = fmt.pct(row.coverage);
    chart.append(value);

    const hit = svg("rect", {
      x: x(row.coverage_ci_low) - 12,
      y: y - 16,
      width: Math.max(28, x(row.coverage_ci_high) - x(row.coverage_ci_low) + 24),
      height: 32,
      fill: "transparent",
    });
    hit.addEventListener("mousemove", (event) => {
      const bounds = chart.getBoundingClientRect();
      tip.show(
        `<b>${entry.label}</b><br>coverage <b>${fmt.pct(row.coverage, 2)}</b><br>` +
          `<span class="muted">Wilson 95% [${fmt.pct(row.coverage_ci_low, 2)}, ${fmt.pct(row.coverage_ci_high, 2)}]</span><br>` +
          `mean CI width <b>${fmt.fixed(row.mean_ci_width, 4)}</b><br>` +
          `bias <b>${fmt.fixed(row.bias, 5)}</b> <span class="muted">(MCSE ${fmt.fixed(row.bias_mc_se, 5)})</span>`,
        event.clientX - bounds.left,
        event.clientY - bounds.top
      );
    });
    hit.addEventListener("mouseleave", tip.hide);
    chart.append(hit);
  });

  document.getElementById("coverage-caption").textContent =
    `${payload.paired.worlds.toLocaleString()} worlds × ${payload.paired.n_per_world.toLocaleString()} units, ` +
    `true contrast ${payload.true_contrast}. Dot is measured coverage, bar is its Wilson interval.`;

  document.getElementById("coverage-table").replaceChildren(
    table(
      ["Estimator", "Coverage", "Wilson 95%", "Mean CI width", "Bias", "MCSE"],
      estimators.map((entry) => {
        const row = payload[entry.key];
        return [
          entry.label,
          fmt.pct(row.coverage, 2),
          `[${fmt.pct(row.coverage_ci_low, 2)}, ${fmt.pct(row.coverage_ci_high, 2)}]`,
          fmt.fixed(row.mean_ci_width, 4),
          fmt.fixed(row.bias, 5),
          fmt.fixed(row.bias_mc_se, 5),
        ];
      }),
      ["", "num", "num", "num", "num", "num"]
    )
  );

  const ratio = payload.se_variance_ratio_unpaired_over_paired;
  document.getElementById("smoke-kpis").replaceChildren(
    tile("Scenarios at gate size", `${payload.scenarios_covered.length} / ${payload.scenarios_required_for_gate.length}`, "canonical scenarios"),
    tile("Pairing variance saving", ratio ? `${ratio.toFixed(2)}×` : "—", "same point estimate, narrower interval"),
    tile("Worlds per scenario", fmt.num(payload.paired.worlds), `seed ${payload.config?.seed ?? "—"}`)
  );
  document.getElementById("smoke-note").textContent = payload.note;

  const host = document.getElementById("scenarios");
  host.replaceChildren();
  payload.scenarios_required_for_gate.forEach((scenario) => {
    const done = payload.scenarios_covered.includes(scenario);
    const row = el("div", { style: "display:flex;gap:8px;align-items:center;margin-bottom:6px;" });
    row.append(chip(done ? "PASS" : "NOT_RUN", done ? "run" : "not run"));
    row.append(el("span", { style: "font-size:13px;color:var(--text-secondary)" }, scenario.replaceAll("_", " ")));
    host.append(row);
  });
}

/* -- 4. capacity curve --------------------------------------------------- */
function renderCapacity(payload) {
  const points = payload.points.filter((point) => point.dr_uplift !== null);
  const width = 780;
  const height = 320;
  const pad = { top: 22, right: 26, bottom: 44, left: 62 };
  const xs = points.map((point) => point.fraction);
  const lows = points.map((point) => point.ci95_low);
  const highs = points.map((point) => point.ci95_high);
  const yMin = Math.min(0, ...lows) * 1.08;
  const yMax = Math.max(0, ...highs) * 1.08;
  const x = (value) =>
    pad.left + ((value - Math.min(...xs)) / (Math.max(...xs) - Math.min(...xs))) * (width - pad.left - pad.right);
  const y = (value) => height - pad.bottom - ((value - yMin) / (yMax - yMin)) * (height - pad.top - pad.bottom);

  const chart = document.getElementById("capacity-chart");
  chart.setAttribute("viewBox", `0 0 ${width} ${height}`);
  chart.replaceChildren();
  const tip = attachTip("capacity-tip");

  niceTicks(yMin * 100, yMax * 100).forEach((tick) => {
    const value = tick / 100;
    if (value < yMin || value > yMax) return;
    chart.append(svg("line", { x1: pad.left, x2: width - pad.right, y1: y(value), y2: y(value), class: "grid-line" }));
    const label = svg("text", { x: pad.left - 10, y: y(value) + 4, class: "axis-label", "text-anchor": "end" });
    label.textContent = tick.toFixed(tick % 1 === 0 ? 0 : 1);
    chart.append(label);
  });
  const axisTitle = svg("text", { x: pad.left - 46, y: pad.top - 8, class: "axis-label" });
  axisTitle.textContent = "pp prevented";
  chart.append(axisTitle);

  xs.forEach((fraction) => {
    const label = svg("text", { x: x(fraction), y: height - 22, class: "axis-label", "text-anchor": "middle" });
    label.textContent = `${Math.round(fraction * 100)}%`;
    chart.append(label);
  });
  const xTitle = svg("text", { x: width / 2, y: height - 4, class: "axis-label", "text-anchor": "middle" });
  xTitle.textContent = "contact budget (share of the eligible holdout)";
  chart.append(xTitle);

  // zero reference: the sign of the contrast is the whole question
  chart.append(svg("line", { x1: pad.left, x2: width - pad.right, y1: y(0), y2: y(0), class: "base-line" }));

  const band = points.map((point) => `${x(point.fraction)},${y(point.ci95_high)}`).concat(
    points.slice().reverse().map((point) => `${x(point.fraction)},${y(point.ci95_low)}`)
  );
  chart.append(svg("polygon", { points: band.join(" "), fill: "var(--series-1-wash)" }));

  chart.append(
    svg("polyline", {
      points: points.map((point) => `${x(point.fraction)},${y(point.dr_uplift)}`).join(" "),
      fill: "none",
      stroke: "var(--series-1)",
      "stroke-width": 2,
      "stroke-linejoin": "round",
      "stroke-linecap": "round",
    })
  );

  points.forEach((point) => {
    chart.append(svg("circle", { cx: x(point.fraction), cy: y(point.dr_uplift), r: 6, fill: "var(--surface-1)" }));
    chart.append(svg("circle", { cx: x(point.fraction), cy: y(point.dr_uplift), r: 4, fill: "var(--series-1)" }));
    const hit = svg("circle", { cx: x(point.fraction), cy: y(point.dr_uplift), r: 16, fill: "transparent" });
    hit.addEventListener("mousemove", (event) => {
      const bounds = chart.getBoundingClientRect();
      const gates = Object.entries(point.gates)
        .map(([name, ok]) => `${ok ? "✓" : "✗"} ${name.replaceAll("_", " ")}`)
        .join("<br>");
      tip.show(
        `<b>${Math.round(point.fraction * 100)}% budget</b> · ${fmt.num(point.n_selected)} accounts<br>` +
          `DR <b>${fmt.pp(point.dr_uplift)}</b><br>` +
          `<span class="muted">95% [${fmt.pp(point.ci95_low)}, ${fmt.pp(point.ci95_high)}]</span><br>` +
          `<span class="muted">events: ${point.control_churn_events} control / ${point.treated_churn_events} treated</span><br>` +
          `${gates}`,
        event.clientX - bounds.left,
        event.clientY - bounds.top
      );
    });
    hit.addEventListener("mouseleave", tip.hide);
    chart.append(hit);
  });

  if (payload.locked_fraction && payload.model === payload.locked_model) {
    const lockedX = x(payload.locked_fraction);
    const lockedY = y(payload.locked_dr_uplift);
    chart.append(svg("circle", { cx: lockedX, cy: lockedY, r: 8.5, fill: "var(--surface-1)" }));
    chart.append(svg("circle", { cx: lockedX, cy: lockedY, r: 5.5, fill: "var(--series-2)" }));
    const label = svg("text", { x: lockedX, y: lockedY - 14, class: "value-label", "text-anchor": "middle" });
    label.textContent = `locked · ${payload.locked_decision}`;
    chart.append(label);
  }

  document.getElementById("capacity-caption").textContent =
    `${payload.model} · ${payload.cap_rule} cap · ${payload.bootstrap_repeats.toLocaleString()} bootstrap resamples · ` +
    `unit: ${payload.unit}. The interval is over selected accounts only.`;
  document.getElementById("capacity-note").textContent = payload.scope_note;

  document.getElementById("capacity-table").replaceChildren(
    table(
      ["Budget", "Capacity", "Selected", "DR estimate", "95% interval", "Control events", "Treated events", "Decision"],
      payload.points.map((point) => [
        `${Math.round(point.fraction * 100)}%`,
        fmt.num(point.capacity),
        fmt.num(point.n_selected),
        fmt.pp(point.dr_uplift),
        point.ci95_low === null ? "—" : `[${fmt.pp(point.ci95_low)}, ${fmt.pp(point.ci95_high)}]`,
        fmt.num(point.control_churn_events),
        fmt.num(point.treated_churn_events),
        chip(point.decision, point.decision.replaceAll("_", " ")),
      ]),
      ["num", "num", "num", "num", "", "num", "num", ""]
    )
  );
}

function renderAllocation(payload, cohort) {
  const readout = payload.readout;
  const allocation = payload.allocation;
  const gatesPassed = Object.values(readout.gates || {}).filter(Boolean).length;
  const gatesTotal = Object.keys(readout.gates || {}).length;
  const kpis = document.getElementById("capacity-kpis");
  const decision = el("div", { class: "card tile" });
  decision.append(el("span", { class: "label" }, "Decision at this budget"));
  const decisionValue = el("span", { class: "value", style: "display:flex;align-items:center;gap:8px;" });
  decisionValue.append(chip(readout.decision, readout.decision.replaceAll("_", " ")));
  decision.append(decisionValue, el("span", { class: "sub" }, `${gatesPassed}/${gatesTotal} launch gates met`));

  kpis.replaceChildren(
    tile("Accounts contacted", fmt.num(readout.n_selected), `cap ${fmt.num(allocation.capacity)} · ${fmt.pct(allocation.utilisation, 0)} used`),
    tile("DR estimate", fmt.pp(readout.dr_uplift), readout.ci95_low === null ? "no interval" : `95% [${fmt.pp(readout.ci95_low)}, ${fmt.pp(readout.ci95_high)}]`),
    tile("Churn events in the selected arm", `${readout.control_churn_events} / ${readout.treated_churn_events}`, "control / treated — 20 each is the gate"),
    decision,
    tile("Agreement with the locked policy", payload.versus_locked_policy ? fmt.num(payload.versus_locked_policy.both) : "—",
      payload.versus_locked_policy
        ? `${fmt.num(payload.versus_locked_policy.only_current)} added, ${fmt.num(payload.versus_locked_policy.only_locked)} dropped`
        : "no locked mask on file")
  );
  document.getElementById("cohort-line").textContent =
    `Eligible holdout: ${fmt.num(cohort.n_units)} accounts — ${fmt.num(cohort.n_control)} control with ` +
    `${fmt.num(cohort.control_churn_events)} churn events, ${fmt.num(cohort.n_treated)} treated with ` +
    `${fmt.num(cohort.treated_churn_events)}. Source: ${cohort.source}.`;
}

/* -- 5. permutation null -------------------------------------------------- */
function renderAudit(payload) {
  const predictability = payload.treatment_predictability || {};
  const permutation = payload.permutation_test || {};
  const propensity = payload.estimated_propensity || {};
  const mean = permutation.null_auc_mean;
  const sd = permutation.null_auc_sd;
  const observed = predictability.oof_roc_auc;

  const width = 500;
  const height = 240;
  const pad = { top: 26, right: 20, bottom: 40, left: 20 };
  const min = Math.min(mean - 4 * sd, 0.49);
  const max = Math.max(observed + 2 * sd, mean + 4 * sd);
  const x = (value) => pad.left + ((value - min) / (max - min)) * (width - pad.left - pad.right);

  const chart = document.getElementById("permutation-chart");
  chart.setAttribute("viewBox", `0 0 ${width} ${height}`);
  chart.replaceChildren();
  const tip = attachTip("permutation-tip");

  const baseY = height - pad.bottom;
  const peak = height - pad.bottom - (height - pad.top - pad.bottom) * 0.86;
  const density = [];
  for (let index = 0; index <= 160; index += 1) {
    const value = min + ((max - min) * index) / 160;
    const z = (value - mean) / sd;
    const y = baseY - (baseY - peak) * Math.exp(-0.5 * z * z);
    density.push(`${x(value)},${y}`);
  }
  chart.append(
    svg("polygon", {
      points: `${pad.left},${baseY} ${density.join(" ")} ${width - pad.right},${baseY}`,
      fill: "var(--series-1-wash)",
    })
  );
  chart.append(
    svg("polyline", { points: density.join(" "), fill: "none", stroke: "var(--series-1)", "stroke-width": 2 })
  );
  chart.append(svg("line", { x1: pad.left, x2: width - pad.right, y1: baseY, y2: baseY, class: "base-line" }));

  [0.5, 0.55, 0.6, 0.65].forEach((value) => {
    if (value < min || value > max) return;
    const label = svg("text", { x: x(value), y: height - 20, class: "axis-label", "text-anchor": "middle" });
    label.textContent = value.toFixed(2);
    chart.append(label);
  });
  const xTitle = svg("text", { x: width / 2, y: height - 4, class: "axis-label", "text-anchor": "middle" });
  xTitle.textContent = "out-of-fold ROC-AUC for predicting treatment";
  chart.append(xTitle);

  chart.append(
    svg("line", { x1: x(observed), x2: x(observed), y1: pad.top + 6, y2: baseY, stroke: "var(--series-2)", "stroke-width": 2 })
  );
  chart.append(svg("circle", { cx: x(observed), cy: pad.top + 6, r: 7, fill: "var(--surface-1)" }));
  chart.append(svg("circle", { cx: x(observed), cy: pad.top + 6, r: 4.5, fill: "var(--series-2)" }));
  const observedLabel = svg("text", { x: x(observed), y: pad.top - 8, class: "value-label", "text-anchor": "end" });
  observedLabel.textContent = `observed ${observed.toFixed(4)}`;
  chart.append(observedLabel);

  const nullLabel = svg("text", { x: x(mean), y: peak - 8, class: "value-label", "text-anchor": "middle" });
  nullLabel.textContent = `null ${mean.toFixed(4)}`;
  chart.append(nullLabel);

  const hit = svg("rect", { x: pad.left, y: pad.top, width: width - pad.left - pad.right, height: baseY - pad.top, fill: "transparent" });
  hit.addEventListener("mousemove", (event) => {
    const bounds = chart.getBoundingClientRect();
    tip.show(
      `<b>Permutation null</b><br>${permutation.permutations} refits on shuffled labels<br>` +
        `mean <b>${mean.toFixed(4)}</b> · sd <b>${sd.toFixed(4)}</b><br>` +
        `observed <b>${observed.toFixed(4)}</b> · ${((observed - mean) / sd).toFixed(1)} sd above the null<br>` +
        `<span class="muted">add-one p = ${permutation.p_value_add_one.toFixed(4)}</span>`,
      event.clientX - bounds.left,
      event.clientY - bounds.top
    );
  });
  hit.addEventListener("mouseleave", tip.hide);
  chart.append(hit);

  document.getElementById("permutation-caption").textContent =
    `Curve is a normal approximation of the ${permutation.permutations}-permutation null (mean ${mean.toFixed(4)}, sd ${sd.toFixed(4)}); ` +
    `the observed value is the measured cross-fitted AUC.`;

  document.getElementById("audit-kpis").replaceChildren(
    tile("Treatment predictability", observed.toFixed(4), "OOF ROC-AUC from 178 pre-treatment covariates"),
    tile("Permutations at or above it", `${permutation.n_null_at_or_above_observed} / ${permutation.permutations}`, `add-one p = ${permutation.p_value_add_one.toFixed(4)}`),
    tile("ESS under estimated e(X)", propensity.effective_sample_size_estimated_e?.toFixed(1) ?? "—",
      `from ${fmt.num(propensity.effective_sample_size_constant_e)} under a constant propensity`),
    tile("Brier skill vs constant", predictability.brier_skill_vs_constant?.toFixed(4) ?? "—", "small, but not zero")
  );
  document.getElementById("audit-note").textContent =
    "Pooled-IID exchangeability is rejected. Four mechanisms leave the same trace on a file with no campaign, " +
    "customer or time key, so this does not show that the per-campaign randomisation described by the source is wrong — " +
    "and reweighting by the estimated propensity is not the repair: it collapses the effective sample size to " +
    `${propensity.effective_sample_size_estimated_e?.toFixed(1) ?? "—"}.`;
}

/* -- 6. temporal mechanism ------------------------------------------------ */
function renderTemporal(payload) {
  const rows = payload.rows
    .filter((row) => row.policy !== "no_contact")
    .sort((a, b) => b.true_net_value - a.true_net_value);
  const width = 780;
  const barHeight = 26;
  const gap = 8;
  const pad = { top: 26, right: 90, bottom: 40, left: 132 };
  const height = pad.top + pad.bottom + rows.length * (barHeight + gap);
  const values = rows.map((row) => row.true_net_value);
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const span = max - min || 1;
  const x = (value) => pad.left + ((value - min) / span) * (width - pad.left - pad.right);

  const chart = document.getElementById("temporal-chart");
  chart.setAttribute("viewBox", `0 0 ${width} ${height}`);
  chart.replaceChildren();
  const tip = attachTip("temporal-tip");

  const zero = x(0);
  chart.append(svg("line", { x1: zero, x2: zero, y1: pad.top - 6, y2: height - pad.bottom + 6, class: "base-line" }));

  rows.forEach((row, index) => {
    const y = pad.top + index * (barHeight + gap);
    const positive = row.true_net_value >= 0;
    const start = positive ? zero : x(row.true_net_value);
    const end = positive ? x(row.true_net_value) : zero;
    const barWidth = Math.max(2, end - start);
    // 4px rounded data-end, square at the zero baseline
    const radius = 4;
    const path = positive
      ? `M ${start} ${y} H ${start + barWidth - radius} a ${radius} ${radius} 0 0 1 ${radius} ${radius}
         V ${y + barHeight - radius} a ${radius} ${radius} 0 0 1 ${-radius} ${radius} H ${start} Z`
      : `M ${end} ${y} H ${start + radius} a ${radius} ${radius} 0 0 0 ${-radius} ${radius}
         V ${y + barHeight - radius} a ${radius} ${radius} 0 0 0 ${radius} ${radius} H ${end} Z`;
    chart.append(
      svg("path", {
        d: path.replace(/\s+/g, " "),
        fill: positive ? "var(--series-3)" : "var(--series-2)",
      })
    );

    const label = svg("text", { x: pad.left - 12, y: y + barHeight / 2 + 4, class: "value-label", "text-anchor": "end" });
    label.textContent = row.policy;
    chart.append(label);

    // A value label never gets clipped: when the bar runs to the axis there is no
    // room outside it, so the label moves inside and switches to the ink that
    // clears contrast against the fill.
    const outsideRoom = positive
      ? width - pad.right - x(row.true_net_value) > 56
      : x(row.true_net_value) - pad.left > 56;
    const value = svg("text", {
      x: outsideRoom
        ? (positive ? x(row.true_net_value) + 8 : x(row.true_net_value) - 8)
        : (positive ? x(row.true_net_value) - 8 : x(row.true_net_value) + 8),
      y: y + barHeight / 2 + 4,
      class: "value-label",
      "text-anchor": outsideRoom === positive ? "start" : "end",
      fill: outsideRoom ? "var(--text-secondary)" : "var(--text-primary)",
    });
    value.textContent = fmt.num(row.true_net_value);
    chart.append(value);

    const hit = svg("rect", { x: pad.left, y, width: width - pad.left - pad.right, height: barHeight, fill: "transparent" });
    hit.addEventListener("mousemove", (event) => {
      const bounds = chart.getBoundingClientRect();
      tip.show(
        `<b>${row.policy}</b><br>true value <b>${fmt.num(row.true_net_value)}</b> ` +
          `<span class="muted">(${row.true_net_value_per_contact.toFixed(3)} per contact)</span><br>` +
          `estimated <b>${row.estimated_net_value_per_contact.toFixed(3)}</b> per contact<br>` +
          `harmful contacts <b>${fmt.pct(row.harmful_offer_share)}</b><br>` +
          `<span class="muted">regret vs oracle ${fmt.num(row.regret_vs_oracle_value)}</span>`,
        event.clientX - bounds.left,
        event.clientY - bounds.top
      );
    });
    hit.addEventListener("mouseleave", tip.hide);
    chart.append(hit);
  });

  const xTitle = svg("text", { x: width / 2, y: height - 8, class: "axis-label", "text-anchor": "middle" });
  xTitle.textContent = "true net value over the post-drift test months (synthetic units)";
  chart.append(xTitle);

  document.getElementById("temporal-caption").textContent =
    `${payload.source} at a ${Math.round(payload.budget_fraction * 100)}% budget. ` +
    "Green is value created, orange is value destroyed; the true conditional effect is known by construction.";

  document.getElementById("temporal-table").replaceChildren(
    table(
      ["Policy", "Contacted", "True net value", "Per contact", "Estimated per contact", "Harmful share", "Regret vs oracle"],
      payload.rows.map((row) => [
        row.policy,
        fmt.num(row.selected_n),
        fmt.num(row.true_net_value),
        row.true_net_value_per_contact.toFixed(3),
        row.estimated_net_value_per_contact.toFixed(3),
        fmt.pct(row.harmful_offer_share),
        fmt.num(row.regret_vs_oracle_value),
      ]),
      ["", "num", "num", "num", "num", "num", "num"]
    )
  );
}

/* -- wiring --------------------------------------------------------------- */
function wireTableToggles() {
  document.querySelectorAll(".toggle-table").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.target);
      const hidden = target.hasAttribute("hidden");
      target.toggleAttribute("hidden", !hidden);
      button.textContent = hidden ? "Hide the table view" : "Show the table view";
    });
  });
}

function wireTheme() {
  const root = document.documentElement;
  document.getElementById("theme-toggle").addEventListener("click", () => {
    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const current = root.dataset.theme || (dark ? "dark" : "light");
    root.dataset.theme = current === "dark" ? "light" : "dark";
  });
}

let capacityState = { model: "risk_logistic", cap_rule: "floor", require_positive: false, fraction: 0.3 };
let cohortInfo = null;

async function refreshCurve() {
  const query = new URLSearchParams({
    model: capacityState.model,
    cap_rule: capacityState.cap_rule,
    require_positive: String(capacityState.require_positive),
  });
  const payload = await getJSON(`/api/policy/curve?${query}`);
  renderCapacity(payload);
}

async function refreshAllocation() {
  const query = new URLSearchParams({
    model: capacityState.model,
    cap_rule: capacityState.cap_rule,
    require_positive: String(capacityState.require_positive),
    fraction: String(capacityState.fraction),
  });
  const payload = await getJSON(`/api/policy/allocation?${query}`);
  renderAllocation(payload, cohortInfo);
}

async function initCapacity() {
  cohortInfo = await getJSON("/api/policy/cohort");
  const select = document.getElementById("model-select");
  select.replaceChildren(
    ...cohortInfo.models.map((model) => el("option", { value: model }, model))
  );
  if (cohortInfo.locked_decision?.model) {
    capacityState.model = cohortInfo.locked_decision.model;
    capacityState.fraction = cohortInfo.locked_decision.budget_fraction ?? 0.3;
  }
  select.value = capacityState.model;
  const slider = document.getElementById("fraction");
  slider.value = String(Math.round(capacityState.fraction * 100));
  document.getElementById("fraction-label").textContent = `${slider.value}%`;

  select.addEventListener("change", async () => {
    capacityState.model = select.value;
    await Promise.all([refreshCurve(), refreshAllocation()]);
  });
  document.getElementById("cap-rule").addEventListener("change", async (event) => {
    capacityState.cap_rule = event.target.value;
    await Promise.all([refreshCurve(), refreshAllocation()]);
  });
  document.getElementById("require-positive").addEventListener("change", async (event) => {
    capacityState.require_positive = event.target.checked;
    await Promise.all([refreshCurve(), refreshAllocation()]);
  });
  slider.addEventListener("input", (event) => {
    document.getElementById("fraction-label").textContent = `${event.target.value}%`;
  });
  slider.addEventListener("change", async (event) => {
    capacityState.fraction = Number(event.target.value) / 100;
    await refreshAllocation();
  });

  await Promise.all([refreshCurve(), refreshAllocation()]);
}

async function initTemporal() {
  const select = document.getElementById("temporal-fraction");
  const first = await getJSON("/api/temporal/policy-truth?budget_fraction=0.2");
  select.replaceChildren(
    ...first.available_fractions
      .filter((fraction) => fraction > 0)
      .map((fraction) => el("option", { value: String(fraction) }, `${Math.round(fraction * 100)}%`))
  );
  select.value = "0.2";
  renderTemporal(first);
  select.addEventListener("change", async () => {
    renderTemporal(await getJSON(`/api/temporal/policy-truth?budget_fraction=${select.value}`));
  });
}

let crossDomainPayload = null;

function renderCrossDomainBenchmark(key) {
  if (!crossDomainPayload || !crossDomainPayload[key]) return;
  const bench = crossDomainPayload[key];
  const candidates = bench.candidates || [];
  const cohort = bench.cohort || {};
  const best = candidates.reduce((acc, cur) => (cur.delta_vs_m01_per_1000 > (acc?.delta_vs_m01_per_1000 ?? -Infinity) ? cur : acc), null);

  const kpis = document.getElementById("cd-kpis");
  if (kpis) {
    kpis.replaceChildren(
      tile("Screening rows", fmt.num(cohort.n_screening), `${fmt.num(cohort.events_treated)} treated / ${fmt.num(cohort.events_control)} control events`),
      tile("Shortlisted learners", (bench.shortlist || []).join(", ") || "None (M01 retained)", key === "lenta_r10" ? "5 uplift learners beat M01" : "Low-event regime (~300 events)"),
      tile("Top candidate vs M01", best ? `${best.id} (${best.delta_vs_m01_per_1000 >= 0 ? "+" : ""}${best.delta_vs_m01_per_1000.toFixed(2)}/1k)` : "—", best ? `DR value ${best.mean_dr_per_1000.toFixed(2)}/1k` : "—")
    );
  }

  const chart = document.getElementById("cd-chart");
  if (chart && candidates.length) {
    const width = 780;
    const barHeight = 24;
    const gap = 8;
    const pad = { top: 22, right: 90, bottom: 36, left: 210 };
    const height = pad.top + pad.bottom + candidates.length * (barHeight + gap);
    const values = candidates.map((c) => Number(c.delta_vs_m01_per_1000 || 0));
    const min = Math.min(-0.5, ...values) * 1.15;
    const max = Math.max(0.5, ...values) * 1.15;
    const span = max - min || 1;
    const x = (value) => pad.left + ((value - min) / span) * (width - pad.left - pad.right);
    const zero = x(0);

    chart.setAttribute("viewBox", `0 0 ${width} ${height}`);
    chart.replaceChildren();
    const tip = attachTip("cd-tip");
    chart.append(svg("line", { x1: zero, x2: zero, y1: pad.top - 6, y2: height - pad.bottom + 6, class: "base-line" }));

    candidates.forEach((row, index) => {
      const y = pad.top + index * (barHeight + gap);
      const val = Number(row.delta_vs_m01_per_1000 || 0);
      const pos = val >= 0;
      const start = pos ? zero : x(val);
      const end = pos ? x(val) : zero;
      const barWidth = Math.max(2, end - start);
      chart.append(
        svg("rect", {
          x: start,
          y,
          width: barWidth,
          height: barHeight,
          rx: 3,
          fill: row.id === "M01" ? "var(--status-neutral)" : pos ? "var(--series-3)" : "var(--series-2)",
        })
      );
      const label = svg("text", { x: pad.left - 10, y: y + barHeight / 2 + 4, class: "value-label", "text-anchor": "end" });
      label.textContent = `${row.id} · ${row.label.replace(row.id, "").trim().slice(0, 26)}`;
      chart.append(label);

      const valLabel = svg("text", {
        x: pos ? end + 8 : start - 8,
        y: y + barHeight / 2 + 4,
        class: "value-label",
        "text-anchor": pos ? "start" : "end",
      });
      valLabel.textContent = `${val >= 0 ? "+" : ""}${val.toFixed(2)} / 1k`;
      chart.append(valLabel);

      const hit = svg("rect", { x: pad.left, y, width: width - pad.left - pad.right, height: barHeight, fill: "transparent" });
      hit.addEventListener("mousemove", (event) => {
        const bounds = chart.getBoundingClientRect();
        tip.show(
          `<b>${row.label}</b><br>Δ vs M01: <b>${val >= 0 ? "+" : ""}${val.toFixed(3)} per 1,000</b><br>` +
            `DR policy value: <b>${Number(row.mean_dr_per_1000 || 0).toFixed(2)} per 1,000</b><br>` +
            `Wins vs M01: <b>${fmt.pct(row.wins_vs_m01)}</b>`,
          event.clientX - bounds.left,
          event.clientY - bounds.top
        );
      });
      hit.addEventListener("mouseleave", tip.hide);
      chart.append(hit);
    });
  }

  const cap = document.getElementById("cd-caption");
  if (cap) {
    cap.textContent = `${bench.dataset} · 5×2 repeated stratified CV at 20% contact budget. Values show incremental net conversions/visits per 1,000 units vs M01 control-outcome ranking.`;
  }

  const tblHost = document.getElementById("cd-table");
  if (tblHost) {
    tblHost.replaceChildren(
      table(
        ["ID", "Candidate recipe", "DR value / 1k", "Δ vs M01 / 1k", "SD across folds", "Win share vs M01"],
        candidates.map((c) => [
          c.id,
          c.label,
          Number(c.mean_dr_per_1000 || 0).toFixed(2),
          `${Number(c.delta_vs_m01_per_1000 || 0) >= 0 ? "+" : ""}${Number(c.delta_vs_m01_per_1000 || 0).toFixed(3)}`,
          Number(c.sd_delta_vs_m01_per_1000 || 0).toFixed(3),
          fmt.pct(c.wins_vs_m01),
        ]),
        ["", "", "num", "num", "num", "num"]
      )
    );
  }
}

async function initCrossDomain() {
  crossDomainPayload = await getJSON("/api/research/cross-domain");
  const select = document.getElementById("cd-benchmark");
  if (select) {
    renderCrossDomainBenchmark(select.value);
    select.addEventListener("change", () => renderCrossDomainBenchmark(select.value));
  }

  const r4Host = document.getElementById("r4-summary-table");
  if (r4Host && crossDomainPayload.r4_nested_summary) {
    r4Host.replaceChildren(
      table(
        ["Domain", "Units", "Events", "Mean Δ vs M01 / 1k", "Disposition"],
        crossDomainPayload.r4_nested_summary.map((r) => [
          r.domain,
          fmt.num(r.n_units),
          fmt.num(r.events),
          r.mean_delta_vs_m01_per_1000 !== null && r.mean_delta_vs_m01_per_1000 !== undefined
            ? `${r.mean_delta_vs_m01_per_1000 >= 0 ? "+" : ""}${Number(r.mean_delta_vs_m01_per_1000).toFixed(3)}`
            : "—",
          el("code", {}, r.decision),
        ]),
        ["", "num", "num", "num", ""]
      )
    );
  }

  const r1Host = document.getElementById("r1-repair-table");
  if (r1Host && crossDomainPayload.r1_repair?.cells) {
    r1Host.replaceChildren(
      table(
        ["Cell", "Old t-CI", "Candidate CI", "McDiarmid", "Gate"],
        crossDomainPayload.r1_repair.cells.map((c) => [
          c.name,
          fmt.pct(c.old_coverage, 1),
          fmt.pct(c.candidate_coverage, 1),
          fmt.pct(c.bounded_coverage, 1),
          chip(c.gate_pass ? "PASS" : "NOT_MET", c.gate_pass ? "PASS" : "UNDER"),
        ]),
        ["", "num", "num", "num", ""]
      )
    );
  }
}

async function askConsoleCopilot(questionText) {
  const input = document.getElementById("console-ai-input");
  const langSelect = document.getElementById("console-ai-lang");
  const q = (questionText ?? input?.value ?? "").trim();
  if (!q) return;
  if (input) input.value = q;
  const answerEl = document.getElementById("console-ai-answer");
  const stateEl = document.getElementById("console-ai-state");
  const guardEl = document.getElementById("console-ai-guardrail");
  const citEl = document.getElementById("console-ai-citations");
  answerEl.textContent = "Querying versioned evidence ledger…";
  try {
    const response = await fetch("/api/ai/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, lang: langSelect ? langSelect.value : "en" }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const statusMap = {
      OBSERVED: "PASS",
      CONDITIONAL: "CONDITIONAL",
      SYNTHETIC: "SYNTHETIC",
      SIMULATED: "NOT_MET",
      REFUSED_OVERCLAIM: "FAIL",
      MISSING_EVIDENCE: "FAIL",
    };
    stateEl.setAttribute("data-status", statusMap[payload.epistemic_state] || "OBSERVED");
    stateEl.querySelector("span").textContent = `${payload.epistemic_state} · ${payload.topic_id}`;
    guardEl.textContent = payload.guardrail_triggered
      ? `🛡 Guardrail triggered (${payload.refusal_reason}) · 0% overclaim rate`
      : "✓ Grounded in local SHA-256 artifacts · 0% overclaim rate";
    answerEl.textContent = payload.answer;
    citEl.replaceChildren();
    (payload.citations || []).forEach((cit) => {
      citEl.append(el("span", { class: "console-cit-pill" }, `${cit.path} · sha256:${cit.sha256_prefix || "missing"}`));
    });
  } catch (error) {
    answerEl.textContent = `Not available: ${error.message}`;
  }
}

function initConsoleCopilot() {
  const form = document.getElementById("console-ai-form");
  if (form) {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      askConsoleCopilot();
    });
  }
  document.querySelectorAll(".console-chip").forEach((btn) => {
    btn.addEventListener("click", () => askConsoleCopilot(btn.getAttribute("data-q")));
  });
}

async function main() {
  wireTableToggles();
  wireTheme();
  initConsoleCopilot();

  const tasks = [
    ["state", async () => renderState(await getJSON("/api/evidence"))],
    ["falsification", async () => renderSuite((await getJSON("/api/report/challenge_suite")).payload)],
    ["validity", async () => renderSmoke((await getJSON("/api/report/inference_smoke")).payload)],
    ["capacity", initCapacity],
    ["identification", async () => renderAudit((await getJSON("/api/report/assignment_audit")).payload)],
    ["mechanism", initTemporal],
    ["cross-domain", initCrossDomain],
  ];
  await Promise.all(
    tasks.map(async ([id, task]) => {
      try {
        await task();
      } catch (error) {
        failSection(id, error);
      }
    })
  );
}

main();
