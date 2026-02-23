import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const baseUrl = process.env.LIVECOOK_URL || "http://127.0.0.1:4173";
const stamp = new Date().toISOString().replace(/[.:]/g, "-");
const shotsDir = path.join("/workspaces/chevdev/testscripts/livecook/logs", `shots-${stamp}`);

async function ensureServer() {
  const res = await fetch(`${baseUrl}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed at ${baseUrl}/health`);
  }
}

async function main() {
  await fs.mkdir(shotsDir, { recursive: true });
  await ensureServer();

  const browser = await chromium.launch({
    headless: true,
    args: [
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
      "--autoplay-policy=no-user-gesture-required"
    ]
  });

  const context = await browser.newContext({
    acceptDownloads: true,
    permissions: ["camera", "microphone"]
  });

  const page = await context.newPage();
  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => Boolean(window.__liveCookTest));

  await page.screenshot({ path: path.join(shotsDir, "01-idle.png"), fullPage: true });

  await page.evaluate(() => {
    window.__liveCookTest.setLowResSegmentDurationMs(3000);
    window.__liveCookTest.setHighResDurationMs(2500);
  });

  await page.click("#toggleLowResBtn");
  await page.waitForTimeout(1600);
  await page.screenshot({ path: path.join(shotsDir, "02-lowres-started.png"), fullPage: true });

  await page.waitForTimeout(4200);
  await page.click("#simulateWakeBtn");
  await page.waitForTimeout(3200);
  await page.screenshot({ path: path.join(shotsDir, "03-highres-triggered.png"), fullPage: true });

  await page.waitForTimeout(2200);
  await page.click("#toggleLowResBtn");
  await page.waitForTimeout(1400);
  await page.screenshot({ path: path.join(shotsDir, "04-stopped-with-clips.png"), fullPage: true });

  const result = await page.evaluate(() => {
    const low = document.querySelectorAll("#lowResClips a").length;
    const high = document.querySelectorAll("#highResClips a").length;
    const lowStatus = document.querySelector("#lowResStatus")?.textContent || "";
    const highStatus = document.querySelector("#highResStatus")?.textContent || "";
    const diag = Array.from(document.querySelectorAll("#diagnosticsLog li")).map((el) => el.textContent || "");
    return {
      low,
      high,
      lowStatus,
      highStatus,
      mongoUploadOkCount: diag.filter((line) => line.includes("mongo-upload-ok")).length,
      diagnosticsTail: diag.slice(0, 10)
    };
  });

  await fs.writeFile(path.join(shotsDir, "result.json"), JSON.stringify({ baseUrl, shotsDir, ...result }, null, 2));

  await context.close();
  await browser.close();

  console.log(JSON.stringify({
    ok: result.low >= 1 && result.high >= 1,
    shotsDir,
    lowClips: result.low,
    highClips: result.high,
    mongoUploadOkCount: result.mongoUploadOkCount
  }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
