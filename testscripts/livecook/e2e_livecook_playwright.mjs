import { chromium } from "playwright";
import { MongoClient } from "mongodb";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";

const cwd = "/workspaces/chevdev/testscripts/livecook";
const logsDir = path.join(cwd, "logs");
const downloadsDir = path.join(cwd, "downloads");
const stamp = new Date().toISOString().replace(/[.:]/g, "-");
const runLogPath = path.join(logsDir, `e2e-${stamp}.log`);
const e2ePort = process.env.LIVECOOK_E2E_PORT || "4174";
const baseUrl = `http://127.0.0.1:${e2ePort}`;
const fakeVideoPath = process.env.LIVECOOK_FAKE_VIDEO_FILE || "";
const fakeAudioPath = process.env.LIVECOOK_FAKE_AUDIO_FILE || "";

function buildBrowserArgs() {
  const args = [
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    "--autoplay-policy=no-user-gesture-required"
  ];

  if (fakeVideoPath) {
    args.push(`--use-file-for-fake-video-capture=${fakeVideoPath}`);
  }
  if (fakeAudioPath) {
    args.push(`--use-file-for-fake-audio-capture=${fakeAudioPath}`);
  }
  return args;
}

function now() {
  return new Date().toISOString();
}

async function log(line) {
  const full = `[${now()}] ${line}\n`;
  process.stdout.write(full);
  await fs.appendFile(runLogPath, full, "utf8");
}

async function waitForHealth(url, timeoutMs = 20000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) {
        return;
      }
    } catch {
      // Keep polling until timeout.
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  throw new Error(`Health check timed out for ${url}`);
}

async function main() {
  await fs.mkdir(logsDir, { recursive: true });
  await fs.mkdir(downloadsDir, { recursive: true });
  await fs.writeFile(runLogPath, "", "utf8");

  await log(`run log: ${runLogPath}`);

  const env = {
    ...process.env,
    HOST: "127.0.0.1",
    PORT: String(e2ePort)
  };

  const server = spawn("node", ["server.js"], {
    cwd,
    env,
    stdio: ["ignore", "pipe", "pipe"]
  });

  server.stdout.on("data", async (chunk) => {
    await log(`[server:stdout] ${String(chunk).trimEnd()}`);
  });
  server.stderr.on("data", async (chunk) => {
    await log(`[server:stderr] ${String(chunk).trimEnd()}`);
  });

  let browser;
  let context;

  try {
    await waitForHealth(`${baseUrl}/health`);
    await log("health check passed");

    browser = await chromium.launch({
      headless: true,
      args: buildBrowserArgs()
    });

    context = await browser.newContext({
      acceptDownloads: true,
      permissions: ["camera", "microphone"]
    });

    const page = await context.newPage();
    page.on("console", async (msg) => {
      await log(`[browser:${msg.type()}] ${msg.text()}`);
    });

    await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => Boolean(window.__liveCookTest));
    await log("page loaded and test hooks available");

    await page.evaluate(() => {
      window.__liveCookTest.setLowResSegmentDurationMs(3000);
      window.__liveCookTest.setHighResDurationMs(2500);
    });
    await log("recording durations set (low=3s, high=2.5s)");

    await page.click("#toggleLowResBtn");
    await log("clicked Start low-res recording");

    await page.waitForTimeout(900);
    await page.evaluate(() => {
      window.__liveCookTest.injectTranscript("chopping onions and garlic at the prep station");
    });
    await log("injected simulated transcript for low-res segment");

    await page.waitForTimeout(5500);
    await page.evaluate(() => {
      window.__liveCookTest.triggerWakeWord("record now while searing chicken in the pan");
    });
    await log("triggered wake word via test hook transcript");

    await page.waitForTimeout(700);
    await page.evaluate(() => {
      window.__liveCookTest.injectTranscript("searing chicken now and stirring pan sauce");
    });
    await log("injected simulated transcript for high-res segment");

    await page.waitForTimeout(5000);

    const clipCounts = await page.evaluate(() => ({
      low: document.querySelectorAll("#lowResClips a").length,
      high: document.querySelectorAll("#highResClips a").length
    }));
    await log(`clip counts in UI low=${clipCounts.low} high=${clipCounts.high}`);

    if (clipCounts.low < 1 || clipCounts.high < 1) {
      throw new Error(`Expected at least one low+high clip, got low=${clipCounts.low} high=${clipCounts.high}`);
    }

    const lowDownloadPromise = page.waitForEvent("download");
    await page.click("#lowResClips a");
    const lowDownload = await lowDownloadPromise;
    const lowPath = path.join(downloadsDir, `dl-low-${stamp}-${lowDownload.suggestedFilename()}`);
    await lowDownload.saveAs(lowPath);
    await log(`downloaded low clip: ${lowPath}`);

    const highDownloadPromise = page.waitForEvent("download");
    await page.click("#highResClips a");
    const highDownload = await highDownloadPromise;
    const highPath = path.join(downloadsDir, `dl-high-${stamp}-${highDownload.suggestedFilename()}`);
    await highDownload.saveAs(highPath);
    await log(`downloaded high clip: ${highPath}`);

    await page.click("#toggleLowResBtn");
    await log("clicked Stop low-res recording");

    await page.waitForFunction(() => {
      const entries = Array.from(document.querySelectorAll("#diagnosticsLog li"))
        .map((el) => el.textContent || "");
      const okCount = entries.filter((line) => line.includes("mongo-upload-ok")).length;
      return okCount >= 2;
    }, { timeout: 30000 });
    await log("observed at least 2 mongo-upload-ok diagnostics");

    const diagnostics = await page.evaluate(() =>
      Array.from(document.querySelectorAll("#diagnosticsLog li")).map((el) => el.textContent || "")
    );
    await log(`diagnostics entries captured: ${diagnostics.length}`);

    const sessionLine = diagnostics.find((line) => line.includes("app-ready") && line.includes("session="));
    const sessionMatch = sessionLine?.match(/session=([a-zA-Z0-9-]+)/);
    const sessionId = sessionMatch?.[1];
    if (!sessionId) {
      throw new Error("Unable to extract client session id from diagnostics log.");
    }
    await log(`sessionId=${sessionId}`);

    const mongoUri = process.env.MONGODB_URI;
    if (!mongoUri) {
      throw new Error("MONGODB_URI is missing for Mongo verification.");
    }

    const dbName = process.env.MONGODB_DB_NAME || "chef";
    const client = new MongoClient(mongoUri, { serverSelectionTimeoutMS: 10000 });
    await client.connect();
    const collectionName = "livecook";
    const docs = await client
      .db(dbName)
      .collection(collectionName)
      .find({ sessionId })
      .sort({ _id: -1 })
      .limit(20)
      .toArray();
    await client.close();

    await log(`mongo docs found in ${collectionName} for session ${sessionId}: ${docs.length}`);

    const types = new Set(docs.map((d) => d.clipType));
    if (!types.has("low-res") || !types.has("high-res")) {
      throw new Error(`Mongo verification failed. clip types found: ${Array.from(types).join(",")}`);
    }

    const lowDocs = docs.filter((doc) => doc.clipType === "low-res");
    const highDocs = docs.filter((doc) => doc.clipType === "high-res");
    if (!lowDocs.length || !highDocs.length) {
      throw new Error("Expected low-res and high-res docs in Mongo, but one is missing.");
    }

    const docsToCheck = [lowDocs[0], highDocs[0]];
    for (const doc of docsToCheck) {
      const url = String(doc?.url || "");
      const transcript = String(doc?.transcript_full_text || "");
      if (!url.startsWith("https://")) {
        throw new Error(`Mongo doc ${doc._id} missing Firebase URL.`);
      }
      if (!doc?.firebase?.bucket || !doc?.firebase?.path) {
        throw new Error(`Mongo doc ${doc._id} missing firebase.bucket or firebase.path metadata.`);
      }
      if (Object.prototype.hasOwnProperty.call(doc, "clipBinary")) {
        throw new Error(`Mongo doc ${doc._id} still has clipBinary; expected metadata-only storage.`);
      }
      await log(
        `mongo doc ${doc._id} type=${doc.clipType} url=${url} transcriptChars=${transcript.length} transcriptEntries=${doc?.transcript_entry_count || 0}`
      );
    }

    for (const doc of docsToCheck) {
      if (!doc?.clipName?.endsWith(".mp4")) {
        throw new Error(`Expected encoded mp4 clip name, got ${doc?.clipName}`);
      }
      if (String(doc?.mimeType || "") !== "video/mp4") {
        throw new Error(`Expected mimeType=video/mp4, got ${doc?.mimeType}`);
      }
      if (typeof doc?.sizeBytesEncoded !== "number" || doc.sizeBytesEncoded <= 0) {
        throw new Error(`Missing sizeBytesEncoded on doc ${doc?._id}`);
      }
      if (!doc?.transcript_source) {
        throw new Error(`Missing transcript_source on doc ${doc?._id}`);
      }
      await log(
        `transcript source for ${doc._id}: ${doc.transcript_source} model=${doc?.transcript_model || "n/a"} chars=${String(doc?.transcript_full_text || "").length}`
      );
    }

    await log("E2E PASS: recording, UI clip save, Firebase upload, and Mongo metadata+transcript verified.");
  } finally {
    try {
      if (context) {
        await context.close();
      }
    } catch {}

    try {
      if (browser) {
        await browser.close();
      }
    } catch {}

    if (!server.killed) {
      server.kill("SIGTERM");
    }
  }
}

main().catch(async (error) => {
  const msg = error?.stack || error?.message || String(error);
  await fs.mkdir(logsDir, { recursive: true });
  await fs.appendFile(runLogPath, `[${now()}] ERROR ${msg}\n`, "utf8");
  process.stderr.write(`${msg}\n`);
  process.exit(1);
});
