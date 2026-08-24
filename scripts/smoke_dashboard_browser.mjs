// Headless-browser acceptance cho bon kich ban tat dinh cua dashboard.
// Trinh duyet tim qua scripts/find_chrome.mjs nen chay duoc ca tren CI Linux.
import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";
import { pathToFileURL } from "node:url";
import { mkdtempSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { findChrome } from "./find_chrome.mjs";

const run = promisify(execFile);
const repo = path.resolve(import.meta.dirname, "..");
const html = path.join(repo, "output", "product", "dashboard.html");
const screenshotDir = mkdtempSync(path.join(tmpdir(), "causal-uplift-dashboard-smoke-"));
const screenshot = path.join(screenshotDir, "dashboard_screenshot.png");
const edge = findChrome();
const baseUrl = pathToFileURL(html).href;

async function dump(scenario) {
  const url = scenario ? `${baseUrl}?scenario=${scenario}` : baseUrl;
  const { stdout, stderr } = await run(
    edge,
    [
      "--headless=new",
      "--disable-gpu",
      "--disable-software-rasterizer",
      "--disable-gpu-shader-disk-cache",
      "--disable-features=Vulkan,WebGPU,Dawn",
      "--no-sandbox",
      "--no-first-run",
      "--dump-dom",
      "--virtual-time-budget=1500",
      url,
    ],
    { maxBuffer: 8 * 1024 * 1024, windowsHide: true },
  );
  if (!stdout.includes("Causal Targeting Lab")) {
    throw new Error(`Dashboard did not render for scenario=${scenario || "default"}: ${stderr}`);
  }
  return stdout;
}

const initial = await dump("");
const low = await dump("low");
const high = await dump("high");
const none = await dump("none");
await run(
  edge,
  [
    "--headless=new",
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--disable-gpu-shader-disk-cache",
    "--disable-features=Vulkan,WebGPU,Dawn",
    "--no-sandbox",
    "--no-first-run",
    "--window-size=1440,1100",
    `--screenshot=${screenshot}`,
    "--virtual-time-budget=1500",
    baseUrl,
  ],
  { windowsHide: true },
);

const checks = [
  [initial.includes("Champion: Response"), "validation-selected champion"],
  [initial.includes('id="budgetText">10</span>'), "default 10% budget"],
  [initial.includes('class="card"'), "dashboard cards"],
  [!initial.includes('class="seg '), "no individual principal-strata cards"],
  [low.includes("<b>Scenario dương.</b>"), "low-cost positive scenario"],
  [high.includes("<b>Scenario âm.</b>"), "high-cost negative scenario"],
  [high.includes("<b>Cảnh báo:</b>"), "out-of-grid warning"],
  [
    high.includes('id="netKpi" class="value bad"')
      || high.includes('class="value bad" id="netKpi"'),
    "negative net warning style",
  ],
  [none.includes('id="budgetText">0</span>'), "treat-none budget"],
  [none.includes("<b>Treat-none:</b>"), "treat-none explanation"],
  [initial.includes("CAUSAL FOREST PENDING"), "Causal Forest status guard"],
  [statSync(screenshot).size > 0, "fresh screenshot written"],
];
const failed = checks.filter(([passed]) => !passed).map(([, label]) => label);
console.log(JSON.stringify({
  passed: checks.length - failed.length,
  total: checks.length,
  failed,
  screenshot,
}, null, 2));
rmSync(screenshotDir, { recursive: true, force: true });
if (failed.length) process.exitCode = 1;
