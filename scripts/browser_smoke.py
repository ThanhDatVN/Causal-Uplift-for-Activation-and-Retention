"""Exercise the localhost planner in a real browser; requires Playwright and a running API."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


def sample_csv(*, copies: int = 3, change: tuple[str, str] | None = None) -> bytes:
    with Path("data/raw/Telco-Customer-Churn.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [next(reader) for _ in range(copies)]
        fields = list(reader.fieldnames or [])
    if change is not None:
        rows[0][change[0]] = change[1]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def upload(page, contents: bytes) -> None:
    page.locator("#csv-file").set_input_files(
        {"name": "snapshot.csv", "mimeType": "text/csv", "buffer": contents}
    )


def wait_for_api(url: str) -> None:
    target = urlsplit(url)
    ready = f"{target.scheme}://{target.netloc}/health/ready"
    for _ in range(30):
        try:
            with urllib.request.urlopen(ready, timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(1)
    raise RuntimeError(f"Local model API did not become ready: {ready}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/planner/")
    parser.add_argument("--chrome", type=Path, help="Existing Chrome or Edge executable")
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(os.getenv("TELCO_MODEL_PATH", "artifacts/models/champion.joblib")),
    )
    parser.add_argument("--output", type=Path, default=Path("reports/v4/browser_smoke"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    checks: list[str] = []
    errors: list[str] = []
    wait_for_api(args.url)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            **({"executable_path": str(args.chrome)} if args.chrome else {}),
        )
        desktop = browser.new_page(viewport={"width": 1365, "height": 900}, accept_downloads=True)
        desktop.on("pageerror", lambda error: errors.append(str(error)))
        desktop.goto(args.url, wait_until="networkidle")
        desktop.locator("#load-demo").focus()
        desktop.keyboard.press("Enter")
        assert desktop.locator("#snapshot-preview").is_visible()
        assert "8 fictional customers" in desktop.locator("#snapshot-summary").inner_text()
        assert desktop.evaluate("document.activeElement.id") == "snapshot-preview-title"
        checks.append("keyboard demo activation and focus on the snapshot preview")

        desktop.locator("#capacity").fill("25")
        desktop.locator("#save-rate").fill("35")
        desktop.locator("#cooldown-days").fill("30")
        desktop.locator("#total-cost-cap").fill("30")
        desktop.locator("#preview").click()
        desktop.locator("#review-content").wait_for(state="visible")
        assert desktop.evaluate("document.activeElement.id") == "review-title"
        assert "2 selected out of 8" in desktop.locator("#table-caption").inner_text()
        assert "not measured causal uplift" in desktop.locator("#assumption-warning").inner_text()
        desktop.screenshot(path=str(args.output / "desktop.png"), full_page=True)
        checks.append("real-model planner decision and causal warning")

        desktop.evaluate("""() => {
          const original = window.fetch;
          window.fetch = (...args) => original(...args).then((response) =>
            new Promise((resolve) => setTimeout(() => resolve(response), 700)));
        }""")
        desktop.locator("#preview").click()
        desktop.locator("#capacity").fill("20")
        expect(desktop.locator("#model-state")).to_contain_text("Assumptions changed")
        desktop.wait_for_timeout(900)
        assert not desktop.locator("#review-content").is_visible()
        assert desktop.locator("#preview").is_enabled()
        checks.append("late API response cannot restore a draft after assumptions change")

        desktop.route(
            "**/v2/campaigns/preview",
            lambda route: route.fulfill(
                status=503,
                content_type="application/json",
                body=json.dumps({"detail": "Model bundle unavailable"}),
            ),
        )
        desktop.locator("#preview").click()
        expect(desktop.locator("#data-state")).to_contain_text("Model bundle unavailable")
        assert desktop.evaluate("document.activeElement.id") == "data-state"
        assert not desktop.locator("#review-content").is_visible()
        desktop.unroute("**/v2/campaigns/preview")
        checks.append("model unavailable gives a visible, focused error")

        upload(desktop, sample_csv(change=("MonthlyCharges", "")))
        expect(desktop.locator("#data-state")).to_contain_text(
            "CSV line 2: MonthlyCharges is required"
        )
        assert not desktop.locator("#snapshot-preview").is_visible()
        assert desktop.locator("#preview").is_disabled()
        assert desktop.evaluate("document.activeElement.id") == "data-state"
        assert desktop.locator("#csv-file").get_attribute("aria-invalid") == "true"
        assert "data-state" in desktop.locator("#csv-file").get_attribute("aria-describedby")
        checks.append(
            "invalid CSV clears stale draft and identifies line/field for assistive technology"
        )

        upload(desktop, sample_csv(change=("PaymentMethod", "Unknown method")))
        expect(desktop.locator("#data-state")).to_contain_text(
            "PaymentMethod has an unsupported value"
        )
        upload(
            desktop,
            sample_csv().replace(b"Electronic check", b'Electronic check"oops', 1),
        )
        expect(desktop.locator("#data-state")).to_contain_text("quotes must wrap the entire field")
        upload(desktop, sample_csv(change=("MultipleLines", "Yes")))
        expect(desktop.locator("#data-state")).to_contain_text(
            "MultipleLines conflicts with PhoneService"
        )
        checks.append("category and cross-field errors fail before API scoring")

        duplicate = sample_csv(copies=1)
        header, data = (
            duplicate.split(b"\r\n", 1) if b"\r\n" in duplicate else duplicate.split(b"\n", 1)
        )
        newline = b"\r\n" if b"\r\n" in duplicate else b"\n"
        upload(desktop, header + newline + data.rstrip(b"\r\n") + newline + data)
        expect(desktop.locator("#data-state")).to_contain_text("customerID repeats line 2")
        checks.append("duplicate customer ID reports both lines")

        upload(desktop, sample_csv())
        expect(desktop.locator("#snapshot-summary")).to_contain_text("3 CSV customers")
        assert desktop.evaluate("document.activeElement.id") == "snapshot-preview-title"
        assert desktop.locator("#csv-file").get_attribute("aria-invalid") is None
        assert "Ignored extra columns: Churn" in desktop.locator("#snapshot-columns").inner_text()
        desktop.locator("#preview").click()
        desktop.locator("#review-content").wait_for(state="visible")
        assert "0 selected out of 3" in desktop.locator("#table-caption").inner_text()
        with desktop.expect_download() as transfer:
            desktop.locator("#export-json").click()
        packet_path = Path(transfer.value.path())
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        assert packet["packet_version"] == 2
        assert len(packet["input_records"]) == 3
        assert len(packet["model_sha256"]) == 64
        assert packet["score_scope"]["horizon_status"] == "unvalidated"
        assert all("risk_30d" not in row for row in packet["ranked_candidates"])
        assert all("Churn" not in row for row in packet["input_records"])
        replay = subprocess.run(
            [
                sys.executable,
                "-m",
                "telco_churn.replay",
                "--packet",
                str(packet_path),
                "--model",
                str(args.model),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert replay.returncode == 0, replay.stdout + replay.stderr
        assert json.loads(replay.stdout)["status"] == "MATCH"
        checks.append("extra target column ignored, zero-contact draft, browser packet replay")

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.on("pageerror", lambda error: errors.append(str(error)))
        mobile.goto(args.url, wait_until="networkidle")
        mobile.locator("#load-demo").click()
        mobile.locator("#preview").click()
        mobile.locator("#review-content").wait_for(state="visible")
        assert not mobile.evaluate("document.documentElement.scrollWidth > innerWidth")
        mobile.screenshot(path=str(args.output / "mobile.png"), full_page=True)
        checks.append("mobile decision flow without page-level horizontal overflow")

        mobile.locator("#total-cost-cap").fill("0")
        mobile.locator("#preview").click()
        expect(mobile.locator("#table-caption")).to_contain_text("0 selected out of 8")
        checks.append("zero money cap produces an empty draft")

        assert not errors, errors
        report = {
            "checked_at_utc": datetime.now(UTC).isoformat(),
            "url": args.url,
            "browser": browser.version,
            "checks": checks,
            "page_errors": errors,
            "note": "Automated browser smoke only; no screen-reader or first-user session was conducted.",
        }
        (args.output / "result.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        browser.close()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
