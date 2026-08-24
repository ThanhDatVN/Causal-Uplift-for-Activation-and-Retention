// Tim mot trinh duyet Chromium chay duoc, tren bat ky he dieu hanh nao.
//
// Truoc day hai script acceptance moi cai hardcode duong dan Windows rieng, nen chung
// khong chay duoc tren CI. Gom vao mot cho de them mot he dieu hanh chi phai sua mot lan.
//
// Thu tu uu tien:
//   1. bien moi truong CHROME_PATH  — cach CI va nguoi dung ghi de
//   2. danh sach ung vien theo he dieu hanh
//
// Nem loi co liet ke day du nhung cho da thu, thay vi bao "khong tim thay".

import { existsSync } from "node:fs";
import { platform } from "node:process";

const CANDIDATES = {
  win32: [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  ],
  linux: [
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
  ],
  darwin: [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
  ],
};

/** Duong dan toi trinh duyet, hoac nem loi neu khong co cai nao. */
export function findChrome() {
  const fromEnv = process.env.CHROME_PATH;
  if (fromEnv) {
    if (existsSync(fromEnv)) return fromEnv;
    throw new Error(`CHROME_PATH tro toi mot file khong ton tai: ${fromEnv}`);
  }

  const candidates = CANDIDATES[platform] ?? [];
  const found = candidates.find((candidate) => existsSync(candidate));
  if (found) return found;

  throw new Error(
    `Khong tim thay Chrome hay Edge tren nen tang "${platform}".\n` +
      `Da thu:\n${candidates.map((c) => `  ${c}`).join("\n") || "  (khong co ung vien nao cho nen tang nay)"}\n` +
      `Dat bien moi truong CHROME_PATH de chi ro duong dan.`,
  );
}

/** Co tim duoc trinh duyet khong — dung de bo qua mem thay vi lam do CI. */
export function hasChrome() {
  try {
    findChrome();
    return true;
  } catch {
    return false;
  }
}
