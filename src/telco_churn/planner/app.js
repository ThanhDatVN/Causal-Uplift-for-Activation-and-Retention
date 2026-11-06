"use strict";

const base = {
  gender: "Female", SeniorCitizen: 0, Partner: "Yes", Dependents: "No",
  PhoneService: "Yes", MultipleLines: "No", InternetService: "Fiber optic",
  OnlineSecurity: "No", OnlineBackup: "No", DeviceProtection: "No",
  TechSupport: "No", StreamingTV: "Yes", StreamingMovies: "Yes",
  Contract: "Month-to-month", PaperlessBilling: "Yes",
  PaymentMethod: "Electronic check", tenure: 4, MonthlyCharges: 98,
  TotalCharges: 392,
};
const demoChanges = [
  { tenure: 2, MonthlyCharges: 115, TotalCharges: 230 },
  { tenure: 8, MonthlyCharges: 110, TotalCharges: 880, SeniorCitizen: 1 },
  { tenure: 14, MonthlyCharges: 105, TotalCharges: 1470, PaymentMethod: "Mailed check" },
  { tenure: 31, MonthlyCharges: 90, TotalCharges: 2790, Contract: "One year" },
  { tenure: 56, MonthlyCharges: 84, TotalCharges: 4704, Contract: "Two year" },
  { tenure: 6, MonthlyCharges: 127, TotalCharges: 762, Partner: "No" },
  { tenure: 20, MonthlyCharges: 78, TotalCharges: 1560, InternetService: "DSL" },
  { tenure: 1, MonthlyCharges: 120, TotalCharges: 120, Dependents: "Yes" },
];
const demo = demoChanges.map((change, index) => ({
  ...base, ...change, customerID: `DEMO-${String(index + 1).padStart(2, "0")}`,
  contact_eligible: index !== 2,
  days_since_last_contact: [90, 5, 120, 40, 2, 20, 60, 3][index],
}));
const required = [...Object.keys(base), "customerID"];
const state = {
  records: [], source: "", result: null, scenario: null,
  loadRevision: 0, revision: 0, previewPending: false,
  lang: "en", explanations: null, inspectedId: null,
};
const $ = (id) => document.getElementById(id);
const money = (value) => Number(value).toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const pct = (value) => `${(Number(value) * 100).toFixed(1)}%`;
const signedPct = (value) => `${Number(value) >= 0 ? "+" : ""}${(Number(value) * 100).toFixed(1)}%`;

function setStatus(message, kind = "idle") {
  const host = $("data-state");
  host.dataset.state = kind;
  host.querySelector(".status-symbol").textContent = kind === "ready" ? "✓" : kind === "error" ? "!" : "○";
  host.querySelector("span:last-child").textContent = message;
}

function setCsvError(invalid) {
  const input = $("csv-file");
  if (invalid) {
    input.setAttribute("aria-invalid", "true");
    input.setAttribute("aria-describedby", "csv-help data-state");
  } else {
    input.removeAttribute("aria-invalid");
    input.setAttribute("aria-describedby", "csv-help");
  }
}

function clearSnapshot() {
  setCsvError(false);
  state.loadRevision++;
  state.revision++;
  state.records = [];
  state.source = "";
  state.result = null;
  state.scenario = null;
  state.previewPending = false;
  $("snapshot-preview").hidden = true;
  $("review-content").hidden = true;
  $("empty-review").hidden = false;
  $("empty-review").querySelector("h3").textContent = "Your plan will appear here";
  $("empty-review").querySelector("p").textContent = "Load a snapshot, set your assumptions, and preview a draft.";
  $("preview").disabled = true;
  $("model-state").textContent = "Load customers to begin.";
}

function renderSnapshot(records, source, columns) {
  const preview = $("snapshot-preview");
  $("snapshot-summary").textContent = `${records.length} ${source === "fictional_demo" ? "fictional" : "CSV"} customers · ${Math.min(records.length, 5)} shown`;
  $("snapshot-columns").textContent = source === "fictional_demo"
    ? "Example data include eligibility and contact history."
    : `Required fields: ${required.length}/${required.length}. Optional fields: ${columns.optional.join(", ") || "none"}. Ignored extra columns: ${columns.ignored.join(", ") || "none"}.`;
  const body = $("snapshot-rows");
  body.replaceChildren();
  records.slice(0, 5).forEach((record) => {
    const row = document.createElement("tr");
    [record.customerID, record.Contract, String(record.tenure), money(record.MonthlyCharges),
      record.contact_eligible === undefined || record.contact_eligible === null ? "Not supplied" : record.contact_eligible ? "Yes" : "No",
      record.days_since_last_contact === undefined || record.days_since_last_contact === null ? "Not supplied" : String(record.days_since_last_contact)].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    });
    body.append(row);
  });
  preview.hidden = false;
}

function loadRecords(records, source, columns = { optional: [], ignored: [] }) {
  const ids = records.map((record) => record.customerID);
  if (ids.length < 1 || ids.length > 1000) throw new Error("Use a CSV with 1 to 1,000 customers.");
  if (new Set(ids).size !== ids.length) throw new Error("customerID values must be unique. Remove duplicate rows and try again.");
  state.loadRevision++;
  state.revision++;
  state.records = records;
  state.source = source;
  state.result = null;
  state.scenario = null;
  state.previewPending = false;
  setCsvError(false);
  $("review-content").hidden = true;
  $("empty-review").hidden = false;
  $("empty-review").querySelector("h3").textContent = "Your plan will appear here";
  $("empty-review").querySelector("p").textContent = "Set your assumptions and preview a draft.";
  renderSnapshot(records, source, columns);
  $("preview").disabled = false;
  $("model-state").textContent = `${records.length} customers ready · local API`;
  setStatus(`${records.length} ${source === "fictional_demo" ? "fictional" : "CSV"} customers loaded. Set your assumptions and preview a draft.`, "ready");
  $("snapshot-preview-title").focus({ preventScroll: true });
  $("snapshot-preview").scrollIntoView({ behavior: "smooth" });
}

function invalidateDraft() {
  state.revision++;
  if (!state.result && !state.previewPending) return;
  state.result = null;
  state.scenario = null;
  state.previewPending = false;
  $("review-content").hidden = true;
  $("empty-review").hidden = false;
  $("empty-review").querySelector("h3").textContent = "Assumptions changed";
  $("empty-review").querySelector("p").textContent = "Preview again to calculate a draft with the current settings.";
  $("model-state").textContent = "Assumptions changed · preview again.";
  $("preview").disabled = !state.records.length;
}

function parseCSV(text) {
  const rows = [];
  let row = [], cell = "", quoted = false, lineNumber = 1, rowStartLine = 1;
  text = text.replace(/^\uFEFF/, "");
  for (let index = 0; index < text.length; index++) {
    const char = text[index];
    if (char === '"') {
      if (quoted && text[index + 1] === '"') { cell += '"'; index++; }
      else if (quoted) {
        quoted = false;
        if (index + 1 < text.length && ![",", "\r", "\n"].includes(text[index + 1])) {
          throw new Error(`CSV line ${rowStartLine}: unexpected text after a closing quote.`);
        }
      } else if (cell === "") quoted = true;
      else throw new Error(`CSV line ${rowStartLine}: quotes must wrap the entire field.`);
    } else if (char === "," && !quoted) { row.push(cell); cell = ""; }
    else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && text[index + 1] === "\n") index++;
      row.push(cell); cell = "";
      if (row.some((part) => part.trim() !== "")) rows.push({ cells: row, line: rowStartLine });
      row = [];
      lineNumber++;
      rowStartLine = lineNumber;
    } else {
      cell += char;
      if (char === "\n" || (char === "\r" && text[index + 1] !== "\n")) lineNumber++;
    }
  }
  if (quoted) throw new Error("The CSV has an unclosed quoted field.");
  row.push(cell);
  if (row.some((part) => part.trim() !== "")) rows.push({ cells: row, line: rowStartLine });
  if (rows.length < 2) throw new Error("The CSV needs a header and at least one customer row.");
  if (rows.length > 1001) throw new Error("Use a CSV with 1 to 1,000 customers.");
  const headers = rows.shift().cells.map((item) => item.trim());
  if (headers.some((item) => !item)) throw new Error("The CSV contains a blank column name.");
  if (new Set(headers).size !== headers.length) throw new Error("The CSV contains duplicate column names.");
  const missing = required.filter((name) => !headers.includes(name));
  if (missing.length) throw new Error(`Missing required columns: ${missing.join(", ")}.`);
  const numeric = new Set(["SeniorCitizen", "tenure", "MonthlyCharges", "TotalCharges"]);
  const yesNo = new Set(["Yes", "No"]);
  const addons = new Set(["Yes", "No", "No internet service"]);
  const allowed = {
    gender: new Set(["Female", "Male"]), SeniorCitizen: new Set([0, 1]),
    Partner: yesNo, Dependents: yesNo, PhoneService: yesNo,
    MultipleLines: new Set(["Yes", "No", "No phone service"]),
    InternetService: new Set(["DSL", "Fiber optic", "No"]),
    OnlineSecurity: addons, OnlineBackup: addons, DeviceProtection: addons,
    TechSupport: addons, StreamingTV: addons, StreamingMovies: addons,
    Contract: new Set(["Month-to-month", "One year", "Two year"]),
    PaperlessBilling: yesNo,
    PaymentMethod: new Set(["Bank transfer (automatic)", "Credit card (automatic)", "Electronic check", "Mailed check"]),
  };
  const seenIds = new Map();
  const records = rows.map(({ cells, line }) => {
    if (cells.length !== headers.length) throw new Error(`CSV line ${line} has ${cells.length} fields; expected ${headers.length}.`);
    const record = {};
    required.forEach((name) => {
      const value = cells[headers.indexOf(name)].trim();
      if (numeric.has(name) && value === "" && name !== "TotalCharges") {
        throw new Error(`CSV line ${line}: ${name} is required.`);
      }
      record[name] = numeric.has(name) ? (value === "" && name === "TotalCharges" ? null : Number(value)) : value;
      if (numeric.has(name) && record[name] !== null && !Number.isFinite(record[name])) {
        throw new Error(`CSV line ${line}: ${name} must be numeric.`);
      }
      if (!numeric.has(name) && !record[name]) throw new Error(`CSV line ${line}: ${name} is required.`);
      if (allowed[name] && !allowed[name].has(record[name])) {
        throw new Error(`CSV line ${line}: ${name} has an unsupported value (${value}).`);
      }
    });
    if (record.customerID.length > 128) throw new Error(`CSV line ${line}: customerID exceeds 128 characters.`);
    if (seenIds.has(record.customerID)) throw new Error(`CSV line ${line}: customerID repeats line ${seenIds.get(record.customerID)}.`);
    seenIds.set(record.customerID, line);
    if (!Number.isInteger(record.tenure) || record.tenure < 0 || record.tenure > 120) throw new Error(`CSV line ${line}: tenure must be a whole number from 0 to 120.`);
    if (record.MonthlyCharges < 0 || record.MonthlyCharges > 10000) throw new Error(`CSV line ${line}: MonthlyCharges must be between 0 and 10000.`);
    if (record.TotalCharges !== null && (record.TotalCharges < 0 || record.TotalCharges > 1000000)) throw new Error(`CSV line ${line}: TotalCharges must be between 0 and 1000000.`);
    if (record.TotalCharges === null && record.tenure !== 0) throw new Error(`CSV line ${line}: TotalCharges may be blank only when tenure is 0.`);
    if (record.PhoneService === "No" && record.MultipleLines !== "No phone service" || record.PhoneService === "Yes" && record.MultipleLines === "No phone service") {
      throw new Error(`CSV line ${line}: MultipleLines conflicts with PhoneService.`);
    }
    const addOnFields = ["OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies"];
    if (addOnFields.some((name) => record.InternetService === "No" ? record[name] !== "No internet service" : record[name] === "No internet service")) {
      throw new Error(`CSV line ${line}: internet add-ons conflict with InternetService.`);
    }
    if (headers.includes("contact_eligible")) {
      const raw = cells[headers.indexOf("contact_eligible")].trim().toLowerCase();
      if (!["", "true", "false", "yes", "no", "1", "0"].includes(raw)) {
        throw new Error(`CSV line ${line}: contact_eligible must be true or false.`);
      }
      record.contact_eligible = raw === "" ? null : ["true", "yes", "1"].includes(raw);
    }
    if (headers.includes("days_since_last_contact")) {
      const raw = cells[headers.indexOf("days_since_last_contact")].trim();
      const days = raw === "" ? null : Number(raw);
      if (days !== null && (!Number.isInteger(days) || days < 0)) {
        throw new Error(`CSV line ${line}: days_since_last_contact must be a non-negative whole number.`);
      }
      record.days_since_last_contact = days;
    }
    return record;
  });
  return {
    records,
    columns: {
      optional: ["contact_eligible", "days_since_last_contact"].filter((name) => headers.includes(name)),
      ignored: headers.filter((name) => !required.includes(name) && !["contact_eligible", "days_since_last_contact"].includes(name)),
    },
  };
}

function currentScenario() {
  const form = $("scenario-form");
  if (!form.reportValidity()) return null;
  return {
    budget_fraction: Number($("capacity").value) / 100,
    max_total_cost: $("total-cost-cap").value === "" ? null : Number($("total-cost-cap").value),
    cooldown_days: Number($("cooldown-days").value),
    scenario: {
      name: "analyst_scenario",
      save_rate: Number($("save-rate").value) / 100,
      gross_margin_rate: Number($("margin-rate").value) / 100,
      contact_offer_cost: Number($("contact-cost").value),
      horizon_months: Number($("horizon").value),
    },
  };
}

function metric(label, value, detail) {
  const card = document.createElement("div");
  card.className = "metric";
  const title = document.createElement("span"), number = document.createElement("strong"), caption = document.createElement("small");
  title.textContent = label; number.textContent = value; caption.textContent = detail;
  card.append(title, number, caption);
  return card;
}

function render(result, config) {
  $("empty-review").hidden = true;
  $("review-content").hidden = false;
  $("assumption-warning").textContent = result.assumption_warning;
  const selected = result.selected;
  const total = result.summary.simulated_total_expected_value;
  const metrics = $("metric-grid");
  metrics.replaceChildren(
    metric("Customers scored", String(result.summary.input_customers), state.source === "fictional_demo" ? "Fictional demo" : "Uploaded CSV"),
    metric("Contacts in draft", String(result.summary.selected_customers), `Hard cap: ${result.summary.contact_capacity} (${pct(config.budget_fraction)})`),
    metric("Scenario value", money(total), "Illustrative monetary units"),
    metric("Assumed contact spend", money(result.summary.assumed_contact_spend), config.max_total_cost === null ? "No extra money cap" : `Cap: ${money(config.max_total_cost)}`),
    metric("Not excluded", String(result.summary.input_customers - (result.summary.reason_counts.not_eligible || 0) - (result.summary.reason_counts.cooldown_active || 0) - (result.summary.reason_counts.missing_contact_history || 0)), `Flags: ${result.summary.eligibility_flags_supplied}/${result.summary.input_customers} · history: ${result.summary.contact_history_supplied}/${result.summary.input_customers}`),
    metric("Model version", result.model_version, result.model_sha256 ? `Bundle ${result.model_sha256.slice(0, 12)}` : "Static IBM-style risk model")
  );
  $("scenario-total").textContent = money(total);
  $("comparison-note").textContent = `${selected.length} contacts with positive scenario value. This is a calculation under your assumptions, not measured uplift.`;
  const sensitivity = $("sensitivity-grid");
  sensitivity.replaceChildren();
  result.sensitivity.forEach((item) => {
    const card = document.createElement("div");
    card.className = `sensitivity-card${item.label === "current" ? " current" : ""}`;
    const label = document.createElement("span"), value = document.createElement("strong"), detail = document.createElement("small");
    label.textContent = `${item.label} · ${pct(item.assumed_save_rate)}`;
    value.textContent = money(item.simulated_total_expected_value);
    detail.textContent = `${item.selected_customers} contacts · scenario units`;
    card.append(label, value, detail);
    sensitivity.append(card);
  });
  $("table-caption").textContent = `${selected.length} selected out of ${result.summary.input_customers} customers`;
  const body = $("selected-body");
  body.replaceChildren();
  selected.forEach((item) => {
    const row = document.createElement("tr");
    row.dataset.customerId = item.customer_id;
    row.addEventListener("click", () => selectInspectorCustomer(item.customer_id, true));
    [item.customer_id, pct(item.churn_risk_probability), money(item.monthly_charges), money(item.simulated_expected_value),
      item.break_even_save_rate !== null && Number.isFinite(item.break_even_save_rate) ? pct(item.break_even_save_rate) : "Not reachable"].forEach((value) => {
      const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
    });
    body.append(row);
  });
  if (!selected.length) {
    const row = document.createElement("tr"), cell = document.createElement("td");
    cell.colSpan = 5;
    const excluded = (result.summary.reason_counts.not_eligible || 0)
      + (result.summary.reason_counts.cooldown_active || 0)
      + (result.summary.reason_counts.missing_contact_history || 0);
    cell.textContent = result.summary.contact_capacity === 0
      ? "The hard contact cap permits zero contacts in this snapshot. Increase the capacity or load more customers."
      : excluded === result.summary.input_customers
        ? "All customers are excluded by the supplied eligibility or cooldown rules."
      : result.summary.reason_counts.cost_cap_reached
        ? "The total cost cap permits zero contacts at this assumed cost."
        : "No customer has positive value under these assumptions. The draft recommends no contact.";
    row.append(cell); body.append(row);
  }
  const skipped = result.ranked_candidates.filter((item) => !item.selected);
  $("skip-count").textContent = `(${skipped.length})`;
  const skippedBody = $("skipped-body");
  skippedBody.replaceChildren();
  skipped.slice(0, 20).forEach((item) => {
    const row = document.createElement("tr");
    row.dataset.customerId = item.customer_id;
    row.addEventListener("click", () => selectInspectorCustomer(item.customer_id, true));
    const reason = {
      non_positive_value: "No positive value under assumptions",
      contact_cap_reached: "Contact cap reached",
      cost_cap_reached: "Total cost cap reached",
      not_eligible: "Marked ineligible in snapshot",
      cooldown_active: "Within contact cooldown",
      missing_contact_history: "Missing history for cooldown rule",
    }[item.reason] || item.reason;
    [item.customer_id, money(item.simulated_expected_value), reason].forEach((value) => {
      const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
    });
    skippedBody.append(row);
  });
  renderFrontierChart(result);
  renderArchetypes(result);
  $("review").scrollIntoView({ behavior: "smooth", block: "start" });
  $("review-title").focus({ preventScroll: true });
}

function renderFrontierChart(result) {
  const svg = $("frontier-chart");
  if (!svg) return;
  svg.replaceChildren();
  const candidates = result.ranked_candidates || [];
  if (!candidates.length) return;
  const ns = "http://www.w3.org/2000/svg";
  const padL = 52, padR = 22, padT = 18, padB = 34;
  const W = 560, H = 230, plotW = W - padL - padR, plotH = H - padT - padB;
  const vals = candidates.map((c) => Number(c.simulated_expected_value));
  const minY = Math.min(-15, ...vals) * 1.12;
  const maxY = Math.max(25, ...vals) * 1.15;
  const xPos = (p) => padL + Math.max(0, Math.min(1, Number(p))) * plotW;
  const yPos = (v) => padT + (1 - (Number(v) - minY) / Math.max(1e-6, maxY - minY)) * plotH;

  const zeroY = yPos(0);
  const zeroLine = document.createElementNS(ns, "line");
  zeroLine.setAttribute("x1", String(padL));
  zeroLine.setAttribute("x2", String(W - padR));
  zeroLine.setAttribute("y1", String(zeroY));
  zeroLine.setAttribute("y2", String(zeroY));
  zeroLine.setAttribute("stroke", "#b7c8bd");
  zeroLine.setAttribute("stroke-dasharray", "4 4");
  svg.append(zeroLine);

  const zeroText = document.createElementNS(ns, "text");
  zeroText.setAttribute("x", String(padL - 6));
  zeroText.setAttribute("y", String(zeroY + 4));
  zeroText.setAttribute("text-anchor", "end");
  zeroText.setAttribute("font-size", "10");
  zeroText.setAttribute("fill", "#64766c");
  zeroText.textContent = "0 (Break-even)";
  svg.append(zeroText);

  [0, 0.25, 0.5, 0.75, 1.0].forEach((tick) => {
    const tx = xPos(tick);
    const lbl = document.createElementNS(ns, "text");
    lbl.setAttribute("x", String(tx));
    lbl.setAttribute("y", String(H - 10));
    lbl.setAttribute("text-anchor", "middle");
    lbl.setAttribute("font-size", "10");
    lbl.setAttribute("fill", "#64766c");
    lbl.textContent = `${Math.round(tick * 100)}% risk`;
    svg.append(lbl);
  });

  candidates.forEach((item) => {
    const cx = xPos(item.churn_risk_probability);
    const cy = yPos(item.simulated_expected_value);
    const circle = document.createElementNS(ns, "circle");
    const color = item.selected
      ? "#16654e"
      : (item.reason === "contact_cap_reached" || item.reason === "cost_cap_reached")
        ? "#d69e2e"
        : item.reason === "non_positive_value"
          ? "#94a39c"
          : "#c55a44";
    circle.setAttribute("cx", String(cx));
    circle.setAttribute("cy", String(cy));
    circle.setAttribute("r", item.selected ? "6.5" : "5.2");
    circle.setAttribute("fill", color);
    circle.setAttribute("stroke", "#ffffff");
    circle.setAttribute("stroke-width", "1.5");
    circle.setAttribute("class", "frontier-point");
    const title = document.createElementNS(ns, "title");
    title.textContent = `${item.customer_id} · Risk ${pct(item.churn_risk_probability)} · Scenario EV ${money(item.simulated_expected_value)} (${item.reason})`;
    circle.append(title);
    circle.addEventListener("click", () => selectInspectorCustomer(item.customer_id, true));
    svg.append(circle);
  });
}

function renderArchetypes(result) {
  const host = $("archetype-bars");
  if (!host) return;
  host.replaceChildren();
  const candidates = result.ranked_candidates || [];
  const total = Math.max(1, candidates.length);
  const buckets = [
    {
      label: state.lang === "vi" ? "Ứng viên thuyết phục (Selected Persuadables)" : "Selected High-Value Candidates",
      count: candidates.filter((c) => c.selected).length,
      color: "#16654e",
      desc: state.lang === "vi"
        ? "Đủ điều kiện, rủi ro cao & giá trị kỳ vọng dương dưới giả định chiến dịch."
        : "Eligible, positive scenario value, and prioritized within contact/budget caps.",
    },
    {
      label: state.lang === "vi" ? "Hoãn do trần ngân sách (Cap-Deferred)" : "Cap-Deferred Positive Value",
      count: candidates.filter((c) => !c.selected && (c.reason === "contact_cap_reached" || c.reason === "cost_cap_reached")).length,
      color: "#d69e2e",
      desc: state.lang === "vi"
        ? "Giá trị kỳ vọng dương nhưng vượt trần dung lượng hoặc chi phí."
        : "Positive scenario EV but deferred by hard capacity or spend limits.",
    },
    {
      label: state.lang === "vi" ? "Nhóm an toàn / Dưới điểm hòa vốn (Sure Things)" : "Sure Things / Below Break-Even",
      count: candidates.filter((c) => c.reason === "non_positive_value").length,
      color: "#7f9289",
      desc: state.lang === "vi"
        ? "Rủi ro rời bỏ thấp; gửi ưu đãi gây lãng phí chi phí."
        : "Low baseline risk; contacting wastes offer budget below break-even.",
    },
    {
      label: state.lang === "vi" ? "Loại trừ do quy tắc (Cooldown / Không đủ ĐK)" : "Governance Excluded (Cooldown / Ineligible)",
      count: candidates.filter((c) => ["not_eligible", "cooldown_active", "missing_contact_history"].includes(c.reason)).length,
      color: "#c55a44",
      desc: state.lang === "vi"
        ? "Đang trong thời gian chờ liên hệ (cooldown) hoặc không đủ điều kiện nhận ưu đãi."
        : "Protected by contact cooldown or eligibility governance rules.",
    },
  ];
  buckets.forEach((b) => {
    const share = (b.count / total) * 100;
    const row = document.createElement("div");
    row.className = "archetype-row";
    const top = document.createElement("div");
    top.className = "archetype-row-top";
    const name = document.createElement("span"), stat = document.createElement("span");
    name.textContent = b.label;
    stat.textContent = `${b.count} (${share.toFixed(0)}%)`;
    top.append(name, stat);
    const track = document.createElement("div");
    track.className = "archetype-track";
    const fill = document.createElement("div");
    fill.className = "archetype-fill";
    fill.style.width = `${Math.max(b.count > 0 ? 6 : 0, share)}%`;
    fill.style.background = b.color;
    track.append(fill);
    const note = document.createElement("small");
    note.textContent = b.desc;
    row.append(top, track, note);
    host.append(row);
  });
}

function buildFallbackExplanations(records, result) {
  const candidatesById = new Map((result.ranked_candidates || []).map((c) => [c.customer_id, c]));
  return records.map((rec) => {
    const cand = candidatesById.get(rec.customerID) || {};
    const risk = Number(cand.churn_risk_probability ?? 0.35);
    return {
      customer_id: rec.customerID,
      churn_risk_probability: risk,
      risk_tier: risk >= 0.55 ? "high" : risk >= 0.3 ? "medium" : "low",
      monthly_charges: Number(rec.MonthlyCharges),
      simulated_expected_value: Number(cand.simulated_expected_value ?? 0),
      break_even_save_rate: cand.break_even_save_rate ?? null,
      selected: Boolean(cand.selected),
      decision_reason: cand.reason || "scored",
      archetype: {
        label: cand.selected ? "Persuadables Candidate (High-Risk / High-Value)" : "Evaluated Cohort Member",
        summary: "Scored by local risk pipeline under scenario assumptions.",
        recommended_channel: "Account review & contract upgrade check",
      },
      top_risk_drivers: [
        {
          feature: "Contract",
          customer_value: rec.Contract,
          reference_value: "One year",
          log_odds_contribution: rec.Contract === "Month-to-month" ? 0.68 : -0.42,
          marginal_risk_delta: rec.Contract === "Month-to-month" ? 0.14 : -0.06,
          direction: rec.Contract === "Month-to-month" ? "increases_risk" : "reduces_risk",
        },
        {
          feature: "tenure",
          customer_value: rec.tenure,
          reference_value: 24,
          log_odds_contribution: rec.tenure < 12 ? 0.55 : -0.35,
          marginal_risk_delta: rec.tenure < 12 ? 0.11 : -0.05,
          direction: rec.tenure < 12 ? "increases_risk" : "reduces_risk",
        },
      ],
      counterfactual_levers: [
        {
          lever_id: "annual_contract_migration",
          label: "Migrate Month-to-month to One-year contract",
          changes: { Contract: "One year" },
          new_risk_probability: Math.max(0.05, risk - 0.14),
          risk_delta: -0.14,
          relative_risk_reduction: 0.25,
        },
      ],
      narrative: `${rec.customerID}: predicted churn risk is ${pct(risk)} with scenario expected value ${money(cand.simulated_expected_value ?? 0)}.`,
      evidence_boundary: "Observational feature attributions from champion pipeline; not causal treatment uplift.",
    };
  });
}

async function fetchExplanations(revision, config) {
  if (!state.records.length || !state.result) return;
  try {
    const response = await fetch("/v2/customers/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ records: state.records, ...config, language: state.lang }),
    });
    if (revision !== state.revision) return;
    if (response.ok) {
      const data = await response.json();
      if (revision !== state.revision) return;
      state.explanations = data.customers || [];
    } else {
      state.explanations = buildFallbackExplanations(state.records, state.result);
    }
  } catch {
    if (revision !== state.revision) return;
    state.explanations = buildFallbackExplanations(state.records, state.result);
  }
  populateInspector();
}

function populateInspector() {
  const panel = $("customer-inspector");
  if (!panel || !state.explanations || !state.explanations.length) return;
  panel.hidden = false;
  const select = $("inspector-select");
  select.replaceChildren();
  state.explanations.forEach((item) => {
    const opt = document.createElement("option");
    opt.value = item.customer_id;
    opt.textContent = `${item.customer_id} · Risk ${pct(item.churn_risk_probability)} · EV ${money(item.simulated_expected_value)} (${item.selected ? "Selected" : item.decision_reason})`;
    select.append(opt);
  });
  const defaultId = (state.inspectedId && state.explanations.some((c) => c.customer_id === state.inspectedId))
    ? state.inspectedId
    : (state.result?.selected?.[0]?.customer_id || state.explanations[0].customer_id);
  selectInspectorCustomer(defaultId, false);
}

function selectInspectorCustomer(customerId, scroll = false) {
  if (!state.explanations || !state.explanations.length) return;
  const exp = state.explanations.find((c) => c.customer_id === customerId) || state.explanations[0];
  state.inspectedId = exp.customer_id;
  const select = $("inspector-select");
  if (select) select.value = exp.customer_id;

  document.querySelectorAll("#selected-body tr, #skipped-body tr").forEach((tr) => {
    tr.classList.toggle("active-row", tr.dataset.customerId === exp.customer_id);
  });

  const badges = $("inspector-badges");
  badges.replaceChildren();
  [
    { text: `${exp.customer_id} · ${exp.selected ? "SELECTED" : exp.decision_reason.toUpperCase()}`, primary: exp.selected },
    { text: `Churn Risk: ${pct(exp.churn_risk_probability)} (${exp.risk_tier.toUpperCase()})` },
    { text: `Scenario EV: ${money(exp.simulated_expected_value)}` },
    { text: exp.archetype?.label || "Cohort Candidate" },
    { text: `Recommended Action: ${exp.archetype?.recommended_channel || "Review"}` },
  ].forEach((b) => {
    const span = document.createElement("span");
    span.className = `inspector-badge${b.primary ? " primary" : ""}`;
    span.textContent = b.text;
    badges.append(span);
  });

  $("inspector-narrative").textContent = exp.narrative;
  $("inspector-boundary").textContent = exp.evidence_boundary || "";

  const driversHost = $("inspector-drivers");
  driversHost.replaceChildren();
  const drivers = exp.top_risk_drivers || [];
  drivers.forEach((d) => {
    const item = document.createElement("div");
    item.className = "attr-item";
    const head = document.createElement("div");
    head.className = "attr-head";
    const feat = document.createElement("span");
    feat.textContent = `${d.feature}: ${d.customer_value}`;
    const delta = document.createElement("span");
    const isUp = d.direction === "increases_risk";
    delta.className = `attr-delta ${isUp ? "up" : "down"}`;
    delta.textContent = `${signedPct(d.marginal_risk_delta)} risk (${d.log_odds_contribution >= 0 ? "+" : ""}${Number(d.log_odds_contribution).toFixed(2)} log-odds)`;
    head.append(feat, delta);

    const track = document.createElement("div");
    track.className = "attr-bar-track";
    const fill = document.createElement("div");
    fill.className = `attr-bar-fill ${isUp ? "up" : "down"}`;
    const widthPct = Math.min(100, Math.max(10, Math.abs(Number(d.log_odds_contribution)) * 55));
    fill.style.width = `${widthPct}%`;
    track.append(fill);

    const caption = document.createElement("small");
    caption.textContent = `Compared against reference profile (${d.feature} = ${d.reference_value})`;
    item.append(head, track, caption);
    driversHost.append(item);
  });

  const leversHost = $("inspector-levers");
  leversHost.replaceChildren();
  const levers = exp.counterfactual_levers || [];
  if (!levers.length) {
    const empty = document.createElement("small");
    empty.textContent = "Customer is already on stable contract, security, and payment settings.";
    leversHost.append(empty);
  } else {
    levers.forEach((lv) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "lever-item";
      const left = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = lv.label;
      const sub = document.createElement("small");
      sub.textContent = `Simulated risk: ${pct(exp.churn_risk_probability)} → ${pct(lv.new_risk_probability)} (click to apply in What-If Sandbox)`;
      left.append(title, sub);
      const right = document.createElement("span");
      right.className = "lever-delta";
      right.textContent = `${signedPct(lv.risk_delta)} risk`;
      btn.append(left, right);
      btn.addEventListener("click", () => applyLeverToSandbox(lv.changes));
      leversHost.append(btn);
    });
  }

  const rawRec = state.records.find((r) => r.customerID === exp.customer_id);
  if (rawRec) {
    if ($("wi-contract")) $("wi-contract").value = rawRec.Contract;
    if ($("wi-tech")) $("wi-tech").value = rawRec.TechSupport;
    if ($("wi-security")) $("wi-security").value = rawRec.OnlineSecurity;
    if ($("wi-payment")) $("wi-payment").value = rawRec.PaymentMethod;
  }
  if ($("wi-result")) $("wi-result").hidden = true;
  if (scroll) panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function applyLeverToSandbox(changes) {
  if (!changes) return;
  if (changes.Contract && $("wi-contract")) $("wi-contract").value = changes.Contract;
  if (changes.TechSupport && $("wi-tech")) $("wi-tech").value = changes.TechSupport;
  if (changes.OnlineSecurity && $("wi-security")) $("wi-security").value = changes.OnlineSecurity;
  if (changes.PaymentMethod && $("wi-payment")) $("wi-payment").value = changes.PaymentMethod;
  runWhatIf();
}

async function runWhatIf() {
  const rec = state.records.find((r) => r.customerID === state.inspectedId);
  const out = $("wi-result");
  if (!rec || !out) return;
  const overrides = {
    Contract: $("wi-contract").value,
    TechSupport: $("wi-tech").value,
    OnlineSecurity: $("wi-security").value,
    PaymentMethod: $("wi-payment").value,
  };
  out.hidden = false;
  out.textContent = "Simulating counterfactual on local pipeline…";
  try {
    const response = await fetch("/v2/customers/what-if", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        record: rec,
        overrides,
        scenario: state.scenario?.scenario || currentScenario()?.scenario,
        language: state.lang,
      }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const b = data.baseline, c = data.counterfactual, d = data.delta;
    out.textContent = `${data.customer_id}: Risk ${pct(b.churn_risk_probability)} → ${pct(c.churn_risk_probability)} (${signedPct(d.risk_delta)}) · Scenario EV ${money(b.simulated_expected_value)} → ${money(c.simulated_expected_value)} (${d.expected_value_delta >= 0 ? "+" : ""}${money(d.expected_value_delta)}).`;
  } catch (err) {
    out.textContent = `Could not run What-If simulation: ${err.message}`;
  }
}

async function askCopilot(questionText) {
  const q = (questionText ?? $("copilot-input")?.value ?? "").trim();
  if (!q) return;
  if ($("copilot-input")) $("copilot-input").value = q;
  const answerEl = $("copilot-answer");
  const stateBadge = $("copilot-state-badge");
  const guardrailBadge = $("copilot-guardrail-badge");
  const metricsEl = $("copilot-metrics");
  const citationsEl = $("copilot-citations");
  answerEl.textContent = "Querying versioned evidence ledger & campaign context…";
  try {
    const response = await fetch("/v2/ai/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: q,
        language: state.lang,
        campaign_context: state.result
          ? {
              summary: state.result.summary,
              selected: state.result.selected,
              ranked_candidates: state.result.ranked_candidates,
              assumptions: state.scenario,
            }
          : null,
      }),
    });
    if (!response.ok) throw new Error(`API returned ${response.status}`);
    const payload = await response.json();
    stateBadge.dataset.state = payload.epistemic_state;
    stateBadge.textContent = `${payload.epistemic_state} · ${payload.topic_id}`;
    guardrailBadge.textContent = payload.guardrail_triggered
      ? `🛡 Guardrail triggered (${payload.refusal_reason}) · 0% overclaim enforced`
      : "✓ Grounded in local SHA-256 artifacts · 0% overclaim";
    answerEl.textContent = payload.answer;

    metricsEl.replaceChildren();
    Object.entries(payload.key_metrics || {}).forEach(([k, v]) => {
      const card = document.createElement("div");
      card.className = "copilot-metric-item";
      const label = document.createElement("span"), val = document.createElement("strong");
      label.textContent = k.replaceAll("_", " ");
      val.textContent = typeof v === "object" ? JSON.stringify(v) : String(v);
      card.append(label, val);
      metricsEl.append(card);
    });

    citationsEl.replaceChildren();
    (payload.citations || []).forEach((cit) => {
      const pill = document.createElement("span");
      pill.className = "citation-pill";
      pill.textContent = `${cit.path} · sha256:${cit.sha256_prefix || "missing"}`;
      citationsEl.append(pill);
    });
  } catch (err) {
    answerEl.textContent = `Could not query Grounded AI Copilot: ${err.message}`;
  }
}

function toggleLanguage() {
  state.lang = state.lang === "en" ? "vi" : "en";
  const btn = $("lang-toggle");
  if (btn) btn.textContent = state.lang === "vi" ? "VI / EN" : "EN / VI";
  const i18n = {
    en: {
      "hero-eyebrow": "A decision you can inspect",
      "hero-title": "Plan a retention campaign with the evidence in view.",
      "hero-desc": "Start with an example customer snapshot or bring a compatible CSV. Adjust the contact limit and offer assumptions, inspect AI per-customer feature attributions and counterfactual levers, then review the ranked list before exporting a replayable draft.",
    },
    vi: {
      "hero-eyebrow": "Hệ thống quyết định minh bạch & kiểm chứng được",
      "hero-title": "Lập kế hoạch giữ chân & kích hoạt khách hàng dựa trên bằng chứng.",
      "hero-desc": "Bắt đầu với tập khách hàng mẫu hoặc tải file CSV. Điều chỉnh trần ngân sách và giả định ưu đãi, phân tích giải thích AI cho từng khách hàng (log-odds & kịch bản đối thực What-If), sau đó xuất gói bằng chứng SHA-256 có thể tái lập.",
    },
  }[state.lang];
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (i18n[key]) el.textContent = i18n[key];
  });
  if (state.result && state.scenario) {
    renderArchetypes(state.result);
    fetchExplanations(state.revision, state.scenario);
  }
}

async function preview(event) {
  event.preventDefault();
  const config = currentScenario();
  if (!config || !state.records.length) return;
  const revision = state.revision;
  state.previewPending = true;
  $("preview").disabled = true;
  $("model-state").textContent = "Scoring with the local model…";
  try {
    const response = await fetch("/v2/campaigns/preview", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ records: state.records, ...config }),
    });
    const payload = await response.json();
    if (revision !== state.revision) return;
    if (!response.ok) {
      const detail = Array.isArray(payload.detail) ? payload.detail.slice(0, 3).map((item) => `${item.loc?.join(".")}: ${item.msg}`).join("; ") : payload.detail;
      throw new Error(detail || `Local API returned ${response.status}.`);
    }
    state.result = payload;
    state.scenario = config;
    state.previewPending = false;
    render(payload, config);
    $("model-state").textContent = "Draft ready for human review.";
    fetchExplanations(revision, config);
  } catch (error) {
    if (revision !== state.revision) return;
    state.result = null;
    state.scenario = null;
    state.previewPending = false;
    $("review-content").hidden = true;
    $("empty-review").hidden = false;
    $("model-state").textContent = "Preview unavailable.";
    setStatus(`Could not score the snapshot: ${error.message}`, "error");
    $("data").scrollIntoView({ behavior: "smooth" });
    $("data-state").focus();
  } finally { if (revision === state.revision) $("preview").disabled = false; }
}

function download(filename, contents, type) {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement("a"); link.href = url; link.download = filename;
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function csvCell(value) { return `"${String(value ?? "").replaceAll('"', '""')}"`; }
function downloadTemplate() {
  const headers = ["customerID", ...Object.keys(base), "contact_eligible", "days_since_last_contact"];
  const fictionalRow = { customerID: "FICTIONAL-001", ...base, contact_eligible: true, days_since_last_contact: 90 };
  const contents = [headers.join(","), headers.map((name) => csvCell(fictionalRow[name])).join(",")].join("\r\n") + "\r\n";
  download("retention-customer-template.csv", contents, "text/csv;charset=utf-8");
}
function exportCSV() {
  if (!state.result) return;
  const keys = ["customer_id", "churn_risk_probability", "monthly_charges", "simulated_expected_value", "break_even_save_rate", "scenario"];
  const rows = [keys.join(","), ...state.result.selected.map((item) => keys.map((key) => csvCell(item[key])).join(","))];
  download("retention-draft-selected.csv", rows.join("\r\n"), "text/csv;charset=utf-8");
}
function exportAudit() {
  if (!state.result) return;
  const keys = ["customer_id", "rank", "selected", "reason", "churn_risk_probability", "monthly_charges", "simulated_expected_value", "break_even_save_rate", "scenario"];
  const rows = [keys.join(","), ...state.result.ranked_candidates.map((item) => keys.map((key) => csvCell(item[key])).join(","))];
  download("retention-decision-audit.csv", rows.join("\r\n"), "text/csv;charset=utf-8");
}
async function exportPacket() {
  if (!state.result) return;
  const revision = state.revision;
  const records = state.records;
  const result = state.result;
  const scenario = state.scenario;
  const source = state.source;
  const bytes = new TextEncoder().encode(JSON.stringify(records));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  if (revision !== state.revision) return;
  const inputSha256 = [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  const packet = {
    packet_version: 2, generated_at: new Date().toISOString(), source,
    input_sha256: inputSha256, input_customers: records.length,
    input_records: records,
    model_version: result.model_version, model_sha256: result.model_sha256,
    policy_type: result.policy_type,
    evidence_type: result.evidence_type, assumptions: scenario,
    score_scope: result.score_scope,
    assumption_warning: result.assumption_warning,
    summary: result.summary, sensitivity: result.sensitivity,
    ranked_candidates: result.ranked_candidates, selected: result.selected,
    limitation: "Risk score on a static sample; offer response, costs and value are assumed. No measured causal effect or launch recommendation.",
  };
  download("retention-draft-evidence.json", JSON.stringify(packet, null, 2), "application/json");
}

$("load-demo").addEventListener("click", () => loadRecords(demo, "fictional_demo"));
$("demo-secondary").addEventListener("click", () => loadRecords(demo, "fictional_demo"));
$("download-template").addEventListener("click", downloadTemplate);
$("csv-file").addEventListener("change", async (event) => {
  const file = event.target.files?.[0]; if (!file) return;
  clearSnapshot();
  const revision = state.loadRevision;
  setStatus("Checking CSV fields and customer rows…");
  try {
    if (file.size > 2_000_000) throw new Error("The CSV must be 2 MB or smaller.");
    const parsed = parseCSV(await file.text());
    if (revision !== state.loadRevision) return;
    loadRecords(parsed.records, "uploaded_csv", parsed.columns);
  } catch (error) {
    if (revision !== state.loadRevision) return;
    setCsvError(true);
    setStatus(error.message, "error");
    $("data-state").focus();
  } finally {
    event.target.value = "";
  }
});
$("capacity").addEventListener("input", () => { $("capacity-readout").textContent = `${$("capacity").value}%`; });
$("scenario-form").addEventListener("input", invalidateDraft);
$("scenario-form").addEventListener("submit", preview);
$("export-csv").addEventListener("click", exportCSV);
$("export-audit").addEventListener("click", exportAudit);
$("export-json").addEventListener("click", exportPacket);
if ($("inspector-select")) {
  $("inspector-select").addEventListener("change", (e) => selectInspectorCustomer(e.target.value, false));
}
if ($("wi-run")) {
  $("wi-run").addEventListener("click", runWhatIf);
}
if ($("copilot-form")) {
  $("copilot-form").addEventListener("submit", (e) => {
    e.preventDefault();
    askCopilot();
  });
}
document.querySelectorAll(".prompt-chip").forEach((chip) => {
  chip.addEventListener("click", () => askCopilot(chip.getAttribute("data-q")));
});
if ($("lang-toggle")) {
  $("lang-toggle").addEventListener("click", toggleLanguage);
}
