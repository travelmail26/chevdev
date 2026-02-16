import http from "node:http";
import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import os from "node:os";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import { MongoClient } from "mongodb";
import { cert, getApps, initializeApp } from "firebase-admin/app";
import { getStorage } from "firebase-admin/storage";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const HOST = process.env.HOST || "127.0.0.1";
const PORT = Number(process.env.PORT || 4173);
const MONGODB_URI = process.env.MONGODB_URI || "";
const MONGODB_DB_NAME = process.env.MONGODB_DB_NAME || "chef";
const MONGODB_COLLECTION_NAME = "livecook";
const FIREBASE_STORAGE_BUCKET = process.env.FIREBASE_STORAGE_BUCKET || "cheftest-f174c";
const LIVECOOK_STORAGE_PREFIX = process.env.LIVECOOK_STORAGE_PREFIX || "livecook_videos";
const LIVECOOK_TRANSCODE_CRF = Number(process.env.LIVECOOK_TRANSCODE_CRF || "28");
const LIVECOOK_AUDIO_BITRATE = process.env.LIVECOOK_AUDIO_BITRATE || "96k";
const LIVECOOK_AUDIO_FILTER = process.env.LIVECOOK_AUDIO_FILTER || "loudnorm=I=-16:TP=-1.5:LRA=11";
const LIVECOOK_TRANSCRIBE_MODEL = process.env.LIVECOOK_TRANSCRIBE_MODEL || "gpt-4o-mini-transcribe";
const OPENAI_AUDIO_TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions";
const MAX_BODY_BYTES = 80 * 1024 * 1024;
const LOG_DIR = path.join(__dirname, "logs");
const SERVER_LOG_FILE = path.join(LOG_DIR, "livecook-server.log");

let mongoClientPromise = null;
let firebaseBucket = null;

function logServer(event, detail = "") {
  try {
    fsSync.mkdirSync(LOG_DIR, { recursive: true });
    const timestamp = new Date().toISOString();
    const text = String(detail || "").trim();
    const line = text ? `[${timestamp}] ${event} ${text}\n` : `[${timestamp}] ${event}\n`;
    fsSync.appendFileSync(SERVER_LOG_FILE, line, "utf8");
  } catch {
    // Ignore logging failures so upload flow stays available.
  }
}

function getContentType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === ".html") return "text/html; charset=utf-8";
  if (ext === ".js") return "text/javascript; charset=utf-8";
  if (ext === ".css") return "text/css; charset=utf-8";
  if (ext === ".json") return "application/json; charset=utf-8";
  if (ext === ".svg") return "image/svg+xml";
  return "application/octet-stream";
}

async function getMongoCollection() {
  if (!MONGODB_URI) {
    logServer("mongo-config-error", "Missing MONGODB_URI env var");
    throw new Error("Missing MONGODB_URI env var.");
  }

  if (!mongoClientPromise) {
    mongoClientPromise = MongoClient.connect(MONGODB_URI, {
      maxPoolSize: 5,
      serverSelectionTimeoutMS: 6000
    });
  }

  const client = await mongoClientPromise;
  return client.db(MONGODB_DB_NAME).collection(MONGODB_COLLECTION_NAME);
}

function normalizeFirebaseJson() {
  const raw = process.env.FIREBASEJSON || "";
  if (!raw) {
    throw new Error("Missing FIREBASEJSON env var.");
  }
  try {
    return JSON.parse(raw);
  } catch {
    throw new Error("FIREBASEJSON is not valid JSON.");
  }
}

function getFirebaseBucket() {
  if (firebaseBucket) {
    return firebaseBucket;
  }

  let app;
  const apps = getApps();
  if (apps.length > 0) {
    app = apps[0];
  } else {
    const serviceAccount = normalizeFirebaseJson();
    app = initializeApp({
      credential: cert(serviceAccount),
      storageBucket: FIREBASE_STORAGE_BUCKET
    });
  }

  firebaseBucket = getStorage(app).bucket(FIREBASE_STORAGE_BUCKET);
  return firebaseBucket;
}

function sanitizePathSegment(value, fallback = "unknown") {
  const cleaned = String(value || "")
    .trim()
    .replace(/[^a-zA-Z0-9._-]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return cleaned || fallback;
}

function runCommand(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stderr = "";
    child.stderr.on("data", (chunk) => {
      stderr += String(chunk);
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`${command} exited with code ${code}: ${stderr.slice(0, 500)}`));
    });
  });
}

function replaceExtensionWithMp4(filename) {
  const base = String(filename || "clip.webm").replace(/\.[^/.]+$/, "");
  return `${base}.mp4`;
}

async function transcodeClipBuffer({
  inputBuffer,
  inputFilename
}) {
  const tempId = `${Date.now()}-${crypto.randomUUID()}`;
  const inputPath = path.join(os.tmpdir(), `livecook-in-${tempId}-${sanitizePathSegment(inputFilename, "clip.webm")}`);
  const outputPath = path.join(os.tmpdir(), `livecook-out-${tempId}.mp4`);

  try {
    await fs.writeFile(inputPath, inputBuffer);
    await runCommand("ffmpeg", [
      "-y",
      "-hide_banner",
      "-loglevel",
      "error",
      "-i",
      inputPath,
      "-c:v",
      "libx264",
      "-preset",
      "veryfast",
      "-crf",
      String(LIVECOOK_TRANSCODE_CRF),
      "-pix_fmt",
      "yuv420p",
      "-movflags",
      "+faststart",
      "-c:a",
      "aac",
      "-b:a",
      LIVECOOK_AUDIO_BITRATE,
      "-ac",
      "1",
      "-af",
      LIVECOOK_AUDIO_FILTER,
      "-ar",
      "48000",
      outputPath
    ]);
    const outputBuffer = await fs.readFile(outputPath);
    return {
      clipBuffer: outputBuffer,
      clipName: replaceExtensionWithMp4(inputFilename),
      mimeType: "video/mp4"
    };
  } catch (error) {
    logServer("transcode-failed", error?.message || "unknown");
    return {
      clipBuffer: inputBuffer,
      clipName: inputFilename,
      mimeType: "video/webm"
    };
  } finally {
    await fs.rm(inputPath, { force: true }).catch(() => {});
    await fs.rm(outputPath, { force: true }).catch(() => {});
  }
}

async function transcribeClipWithOpenAI({
  clipBuffer,
  clipName,
  mimeType
}) {
  const apiKey = process.env.OPENAI_API_KEY || "";
  if (!apiKey) {
    return {
      transcriptText: "",
      transcriptSource: "none_missing_openai_key",
      transcriptModel: ""
    };
  }

  try {
    const formData = new FormData();
    formData.append("model", LIVECOOK_TRANSCRIBE_MODEL);
    formData.append("file", new Blob([clipBuffer], { type: mimeType }), clipName);

    const response = await fetch(OPENAI_AUDIO_TRANSCRIBE_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`
      },
      body: formData
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`status=${response.status} body=${errorText.slice(0, 300)}`);
    }

    const payload = await response.json();
    const transcriptText = String(payload?.text || "").trim();
    return {
      transcriptText,
      transcriptSource: "openai_audio_transcription",
      transcriptModel: LIVECOOK_TRANSCRIBE_MODEL
    };
  } catch (error) {
    logServer("transcribe-failed", error?.message || "unknown");
    return {
      transcriptText: "",
      transcriptSource: "openai_transcribe_failed",
      transcriptModel: LIVECOOK_TRANSCRIBE_MODEL
    };
  }
}

async function uploadClipBufferToFirebase({
  clipBuffer,
  sessionId,
  clipName,
  mimeType,
  capturedAt
}) {
  const bucket = getFirebaseBucket();
  const safeSessionId = sanitizePathSegment(sessionId, "unknown-session");
  const safeClipName = sanitizePathSegment(clipName, "clip.webm");
  const timestamp = new Date(capturedAt || Date.now()).toISOString().replace(/[.:]/g, "-");
  const objectPath = `${LIVECOOK_STORAGE_PREFIX}/${safeSessionId}/${timestamp}-${Date.now()}-${safeClipName}`;
  const file = bucket.file(objectPath);

  await file.save(clipBuffer, {
    contentType: mimeType || "video/webm",
    metadata: {
      metadata: {
        sessionId: String(sessionId || "unknown"),
        source: "livecook",
        capturedAt: String(capturedAt || "")
      }
    }
  });
  await file.makePublic();

  return {
    url: file.publicUrl(),
    firebasePath: objectPath,
    firebaseBucket: bucket.name
  };
}

function normalizeTranscriptEntries(entries) {
  if (!Array.isArray(entries)) {
    return [];
  }

  return entries
    .slice(0, 500)
    .map((entry) => ({
      text: String(entry?.text || "").trim(),
      source: String(entry?.source || "unknown"),
      receivedAtIso: String(entry?.receivedAtIso || ""),
      elapsedLabel: String(entry?.elapsedLabel || "")
    }))
    .filter((entry) => Boolean(entry.text));
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    let bodySize = 0;

    req.on("data", (chunk) => {
      bodySize += chunk.length;
      if (bodySize > MAX_BODY_BYTES) {
        reject(new Error("Payload too large."));
        req.destroy();
        return;
      }
      body += chunk;
    });

    req.on("end", () => {
      try {
        resolve(JSON.parse(body || "{}"));
      } catch {
        reject(new Error("Invalid JSON body."));
      }
    });

    req.on("error", (error) => reject(error));
  });
}

function sendJson(res, statusCode, payload) {
  res.writeHead(statusCode, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(payload));
}

async function handleClipUpload(req, res) {
  try {
    const payload = await readJsonBody(req);
    const {
      sessionId = "unknown",
      clipName = "clip.webm",
      clipType = "unknown",
      reason = "unknown",
      mimeType = "video/webm",
      sizeBytes = 0,
      dataBase64 = "",
      capturedAt = null,
      clipStartedAt = null,
      clipEndedAt = null
    } = payload;

    if (!dataBase64) {
      logServer("upload-rejected", "missing dataBase64");
      sendJson(res, 400, { ok: false, error: "dataBase64 is required." });
      return;
    }

    const originalClipBuffer = Buffer.from(dataBase64, "base64");
    logServer(
      "upload-received",
      `session=${sessionId} clip=${clipName} type=${clipType} bytes=${originalClipBuffer.length}`
    );
    const transcoded = await transcodeClipBuffer({
      inputBuffer: originalClipBuffer,
      inputFilename: clipName
    });
    const transcriptResult = await transcribeClipWithOpenAI({
      clipBuffer: transcoded.clipBuffer,
      clipName: transcoded.clipName,
      mimeType: transcoded.mimeType
    });

    const firebaseUpload = await uploadClipBufferToFirebase({
      clipBuffer: transcoded.clipBuffer,
      sessionId,
      clipName: transcoded.clipName,
      mimeType: transcoded.mimeType,
      capturedAt
    });
    logServer("firebase-uploaded", `clip=${clipName} path=${firebaseUpload.firebasePath}`);
    const indexedAt = new Date().toISOString();
    const collection = await getMongoCollection();

    const document = {
      sessionId,
      clipName: transcoded.clipName,
      clipNameOriginal: clipName,
      clipType,
      reason,
      mimeType: transcoded.mimeType,
      mimeTypeOriginal: mimeType,
      sizeBytes,
      sizeBytesOriginal: originalClipBuffer.length,
      sizeBytesEncoded: transcoded.clipBuffer.length,
      capturedAt,
      clipStartedAt,
      clipEndedAt,
      uploadedAt: indexedAt,
      indexed_at: indexedAt,
      source: "livecook",
      url: firebaseUpload.url,
      firebase: {
        bucket: firebaseUpload.firebaseBucket,
        path: firebaseUpload.firebasePath
      },
      transcript_full_text: transcriptResult.transcriptText,
      transcript_entries: [],
      transcript_entry_count: transcriptResult.transcriptText ? 1 : 0,
      transcript_source: transcriptResult.transcriptSource,
      transcript_model: transcriptResult.transcriptModel
    };

    const result = await collection.insertOne(document);
    logServer("upload-inserted", `id=${String(result.insertedId)} collection=${MONGODB_COLLECTION_NAME}`);
    sendJson(res, 201, {
      ok: true,
      collection: MONGODB_COLLECTION_NAME,
      documentId: String(result.insertedId),
      url: firebaseUpload.url,
      transcriptChars: transcriptResult.transcriptText.length
    });
  } catch (error) {
    logServer("upload-error", error?.message || "Upload failed");
    sendJson(res, 500, {
      ok: false,
      error: error?.message || "Upload failed."
    });
  }
}

async function handleClientLog(req, res) {
  try {
    const payload = await readJsonBody(req);
    const event = payload?.event || "client-log";
    const detail = payload?.detail || payload?.line || "";
    logServer("client-log", `${event} ${String(detail).slice(0, 200)}`);
    sendJson(res, 200, { ok: true });
  } catch (error) {
    logServer("client-log-error", error?.message || "invalid client log payload");
    sendJson(res, 400, { ok: false });
  }
}

async function handleStaticFile(req, res) {
  let reqPath = req.url || "/";
  if (reqPath === "/") {
    reqPath = "/index.html";
  }

  const decodedPath = decodeURIComponent(reqPath.split("?")[0]);
  const filePath = path.join(__dirname, decodedPath);

  if (!filePath.startsWith(__dirname)) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }

  try {
    const data = await fs.readFile(filePath);
    res.writeHead(200, { "Content-Type": getContentType(filePath) });
    res.end(data);
  } catch {
    res.writeHead(404);
    res.end("Not found");
  }
}

const server = http.createServer(async (req, res) => {
  if (req.method === "POST" && req.url && req.url.startsWith("/api/clips")) {
    await handleClipUpload(req, res);
    return;
  }

  if (req.method === "POST" && req.url && req.url.startsWith("/client-log-v2")) {
    await handleClientLog(req, res);
    return;
  }

  if (req.method === "GET" && req.url && req.url.startsWith("/health")) {
    logServer("health-check", `db=${MONGODB_DB_NAME} collection=${MONGODB_COLLECTION_NAME}`);
    sendJson(res, 200, {
      ok: true,
      collection: MONGODB_COLLECTION_NAME,
      db: MONGODB_DB_NAME,
      hasMongoUri: Boolean(MONGODB_URI),
      hasFirebaseJson: Boolean(process.env.FIREBASEJSON),
      firebaseBucket: FIREBASE_STORAGE_BUCKET
    });
    return;
  }

  await handleStaticFile(req, res);
});

server.listen(PORT, HOST, () => {
  logServer("server-start", `http://${HOST}:${PORT} db=${MONGODB_DB_NAME} collection=${MONGODB_COLLECTION_NAME}`);
  console.log(`livecook running at http://${HOST}:${PORT}`);
  console.log(`mongo target: db=${MONGODB_DB_NAME} collection=${MONGODB_COLLECTION_NAME}`);
  console.log(`firebase target: bucket=${FIREBASE_STORAGE_BUCKET} prefix=${LIVECOOK_STORAGE_PREFIX}`);
});
