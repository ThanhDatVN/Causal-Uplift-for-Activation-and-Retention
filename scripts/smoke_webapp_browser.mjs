// Headless-browser acceptance cho web app Causal Targeting Lab.
//
// Script khởi động uvicorn trên một cổng tự do, chờ /api/health, rồi render trang
// bằng headless Chrome và kiểm tra nội dung đã render. Mọi panel đều nằm trong DOM
// ngay sau khi boot (chỉ ẩn bằng CSS), nên một lần dump là đủ để kiểm tra hết.
import { spawn, execFile } from "node:child_process";
import { createServer } from "node:net";
import path from "node:path";
import { promisify } from "node:util";
import { existsSync, mkdtempSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";

const run = promisify(execFile);
const repo = path.resolve(import.meta.dirname, "..");
const screenshotDir = mkdtempSync(path.join(tmpdir(), "causal-uplift-web-smoke-"));
const python = path.join(repo, ".venv", "Scripts", "python.exe");
const chromeCandidates = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
];
const chrome = chromeCandidates.find((candidate) => existsSync(candidate));
if (!chrome) {
  console.error("No headless Chrome/Edge binary found in the known locations.");
  process.exit(2);
}

function freePort() {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

async function waitForHealth(port, timeoutMs = 90000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/api/health`);
      if (response.ok) return await response.json();
    } catch {
      /* server chưa sẵn sàng */
    }
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
  throw new Error(`Server did not become healthy within ${timeoutMs} ms`);
}

async function dumpDom(url) {
  const { stdout } = await run(
    chrome,
    [
      "--headless=new",
      "--disable-gpu",
      "--disable-software-rasterizer",
      "--disable-features=Vulkan,WebGPU,Dawn",
      "--no-sandbox",
      "--no-first-run",
      "--dump-dom",
      "--virtual-time-budget=6000",
      url,
    ],
    { maxBuffer: 32 * 1024 * 1024, windowsHide: true },
  );
  return stdout;
}

async function screenshot(url, file) {
  await run(
    chrome,
    [
      "--headless=new",
      "--disable-gpu",
      "--disable-software-rasterizer",
      "--disable-features=Vulkan,WebGPU,Dawn",
      "--no-sandbox",
      "--no-first-run",
      "--window-size=1400,2400",
      "--virtual-time-budget=6000",
      `--screenshot=${file}`,
      url,
    ],
    { maxBuffer: 32 * 1024 * 1024, windowsHide: true },
  );
}

const checks = [];
function check(name, condition, detail = "") {
  checks.push({ name, pass: Boolean(condition), detail });
}

const port = await freePort();
const server = spawn(
  python,
  ["-m", "uvicorn", "webapp.api:app", "--host", "127.0.0.1", "--port", String(port), "--log-level", "warning"],
  { cwd: repo, windowsHide: true },
);
server.stderr.on("data", (chunk) => {
  const text = String(chunk);
  if (text.includes("Traceback")) console.error(text);
});

let exitCode = 0;
try {
  const health = await waitForHealth(port);
  check("health endpoint responds", health.status === "ok" || health.status === "degraded", health.status);
  check("health lists artifacts", Array.isArray(health.artifacts) && health.artifacts.length > 5);

  const base = `http://127.0.0.1:${port}/`;
  const dom = await dumpDom(base);

  check("page title rendered", dom.includes("Causal Targeting Lab"));
  check("scope banner present", dom.includes("mô phỏng policy offline"));
  check("champion resolved in subtitle", /Champion \S+/.test(dom) && !dom.includes("Đang tải artifact"));
  check("overview stat tiles rendered", (dom.match(/class="stat /g) || []).length >= 4);
  check("evidence hierarchy table filled", dom.includes("retrospective_confirmation"));
  check("model table rendered", dom.includes("policy_area_dr") || dom.includes("Qini"));
  check("pairwise CI verdicts rendered", dom.includes("CI chứa 0") || dom.includes("CI &gt; 0") || dom.includes("CI &lt; 0"));
  check("budget curve table rendered", dom.includes("Chi phí hòa vốn"));
  check("decile table rendered", dom.includes("Incremental tích lũy"));
  check("balance diagnostics rendered", dom.includes("Mean treated"));
  check("registry table rendered", dom.includes("Conv. control"));
  check("limitations listed", dom.includes("principal stratum"));
  check("export buttons rendered", dom.includes("/api/export/"));
  check("no unresolved placeholders", !dom.includes("Chưa tải được dữ liệu"));
  // Ba khoi giai thich ket luan. Chung sinh tu du lieu nen de hong am tham khi
  // schema doi, va khi hong thi trang van "chay duoc" — dung loai loi ma
  // acceptance phai bat.
  check("verdict block states the champion", /class="verdict"[\s\S]*?Champion giữ nguyên \S+/.test(dom));
  check("pairwise forest plot present", dom.includes('id="pairwiseForest"'));
  check("resolution block quantifies the gap", dom.includes("Ngưỡng phân biệt được"));
  check("concentration block quantifies targeting value", dom.includes("Decile 1 chiếm"));
  check("promotion rule renders nested checks", !dom.includes("[object Object]"));

  const simulate = await fetch(`http://127.0.0.1:${port}/api/policy/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      budget_fraction: 0.1,
      audience: 1000000,
      value_per_conversion: 1,
      contact_cost: 0.0005,
    }),
  }).then((r) => r.json());
  check("simulate returns a gross value", Number.isFinite(simulate.gross_incremental_conversions_per_customer));
  check("simulate flags scenario, not revenue", simulate.is_monetary_observation === false);

  const low = await fetch(`http://127.0.0.1:${port}/api/policy/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ budget_fraction: 0.2, contact_cost: 0.00025 }),
  }).then((r) => r.json());
  const high = await fetch(`http://127.0.0.1:${port}/api/policy/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ budget_fraction: 0.05, contact_cost: 0.001 }),
  }).then((r) => r.json());
  check(
    "low-cost scenario has higher net value than high-cost scenario",
    low.net_scenario_value_per_customer > high.net_scenario_value_per_customer,
    `${low.net_scenario_value_per_customer} vs ${high.net_scenario_value_per_customer}`,
  );
  const none = await fetch(`http://127.0.0.1:${port}/api/policy/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ budget_fraction: 0 }),
  }).then((r) => r.json());
  check("treat-none scenario is exactly zero", none.total_incremental_conversions === 0);

  // Deep link phải mở đúng tab; đây cũng là cách chụp từng panel vì panel không
  // hoạt động bị ẩn bằng CSS chứ không bị gỡ khỏi DOM.
  const modelsDom = await dumpDom(`${base}?tab=models`);
  check(
    "deep link opens the requested tab",
    /id="panel-models"[^>]*class="panel is-active"/.test(modelsDom) ||
      modelsDom.includes('class="panel is-active" id="panel-models"'),
  );

  const mainScreenshot = path.join(screenshotDir, "webapp_screenshot.png");
  await screenshot(base, mainScreenshot);
  for (const tab of ["models", "policy", "segments", "scoring", "evidence"]) {
    await screenshot(
      `${base}?tab=${tab}`,
      path.join(screenshotDir, `webapp_screenshot_${tab}.png`),
    );
  }
  check("screenshot written", existsSync(mainScreenshot) && statSync(mainScreenshot).size > 0);
  check(
    "per-tab screenshots written",
    ["models", "policy", "segments", "evidence"].every((tab) =>
      {
        const file = path.join(screenshotDir, `webapp_screenshot_${tab}.png`);
        return existsSync(file) && statSync(file).size > 0;
      },
    ),
  );
} catch (error) {
  check("acceptance run completed without exception", false, String(error));
} finally {
  server.kill();
  rmSync(screenshotDir, { recursive: true, force: true });
}

const passed = checks.filter((c) => c.pass).length;
for (const item of checks) {
  console.log(`${item.pass ? "PASS" : "FAIL"}  ${item.name}${item.detail ? ` — ${item.detail}` : ""}`);
}
console.log(`\n${passed}/${checks.length} checks passed`);
if (passed !== checks.length) exitCode = 1;
process.exit(exitCode);
