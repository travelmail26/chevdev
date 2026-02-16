import { OnboardTranscriber } from "./onboardTranscriber.js";

const lowResPreview = document.getElementById("lowResPreview");
const highResPreview = document.getElementById("highResPreview");
const toggleLowResBtn = document.getElementById("toggleLowResBtn");
const simulateWakeBtn = document.getElementById("simulateWakeBtn");
const lowResStatus = document.getElementById("lowResStatus");
const wakeStatus = document.getElementById("wakeStatus");
const highResStatus = document.getElementById("highResStatus");
const lowResClips = document.getElementById("lowResClips");
const highResClips = document.getElementById("highResClips");
const audioMeterFill = document.getElementById("audioMeterFill");
const transcriptStatus = document.getElementById("transcriptStatus");
const transcriptLog = document.getElementById("transcriptLog");
const diagnosticsStatus = document.getElementById("diagnosticsStatus");
const diagnosticsLog = document.getElementById("diagnosticsLog");
const clearDiagnosticsBtn = document.getElementById("clearDiagnosticsBtn");

const WAKE_WORD = "record";
const STOP_WORD = "stop";
const LOG_RELAY_ENDPOINT = "/client-log-v2";
const CLIP_UPLOAD_ENDPOINT = "/api/clips";
const CLIENT_SESSION_ID = (typeof crypto !== "undefined" && crypto.randomUUID)
  ? crypto.randomUUID().slice(0, 8)
  : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;

const LOW_RES_CONSTRAINTS = {
  video: {
    width: { ideal: 320, max: 320 },
    height: { ideal: 180, max: 180 },
    frameRate: { ideal: 10, max: 10 }
  },
  audio: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
    sampleRate: { ideal: 48000 },
    sampleSize: { ideal: 16 },
    channelCount: { ideal: 1 }
  }
};

const HIGH_RES_CONSTRAINTS = {
  video: {
    width: { ideal: 1920 },
    height: { ideal: 1080 },
    frameRate: { ideal: 30, max: 30 }
  },
  audio: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
    sampleRate: { ideal: 48000 },
    sampleSize: { ideal: 16 },
    channelCount: { ideal: 1 }
  }
};

const state = {
  lowStream: null,
  highStream: null,
  highRecordingStream: null,
  lowRecorder: null,
  lowRecordingEnabled: false,
  lowRecorderSegmentReason: "rolling-30s",
  lowSegmentTimer: null,
  highRecorder: null,
  lowChunks: [],
  highChunks: [],
  lowClipCount: 0,
  highClipCount: 0,
  wakeListenerActive: false,
  wakeTranscriber: null,
  wakeMode: "inactive",
  highResDurationMs: 10000,
  lowResSegmentDurationMs: 30000,
  lowSegmentStartedAt: 0,
  sessionStartedAt: 0,
  highClipStartedAt: 0,
  highResStopTimer: null,
  meterAnimationId: null,
  meterAudioContext: null,
  meterAnalyser: null,
  meterLastLogAt: 0,
  meterPeakSinceLastLog: 0,
  wakeLastTriggerAt: 0,
  transcriptCount: 0,
  transcriptEvents: [],
  lastRealTranscriptAt: 0,
  diagnosticsCount: 0,
  remoteLogRelayState: "unknown",
  remoteLogFailureCount: 0
};

function setStatus(element, message, warning = false) {
  element.textContent = message;
  element.classList.toggle("warn", warning);
}

function addDiagnosticLog(event, detail = "") {
  const detailText = String(detail || "").trim();
  const line = detailText ? `${event}: ${detailText}` : event;
  const timestamp = new Date().toLocaleTimeString();
  state.diagnosticsCount += 1;
  diagnosticsStatus.textContent = `Latest diagnostic: ${line}`;

  const entry = document.createElement("li");
  entry.textContent = `[${timestamp}] ${line}`;
  diagnosticsLog.prepend(entry);

  const maxEntries = 140;
  while (diagnosticsLog.children.length > maxEntries) {
    diagnosticsLog.removeChild(diagnosticsLog.lastChild);
  }

  relayDiagnosticLog({
    sessionId: CLIENT_SESSION_ID,
    timestamp,
    event,
    detail: detailText,
    line
  });
}

async function relayDiagnosticLog(payload) {
  try {
    const response = await fetch(LOG_RELAY_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload),
      keepalive: true
    });

    if (response.ok) {
      state.remoteLogRelayState = "enabled";
      state.remoteLogFailureCount = 0;
    } else {
      state.remoteLogRelayState = "degraded";
      state.remoteLogFailureCount += 1;
    }
  } catch {
    state.remoteLogRelayState = "degraded";
    state.remoteLogFailureCount += 1;
  }
}

function pickRecorderOptions() {
  if (!window.MediaRecorder) {
    return undefined;
  }

  const mimeCandidates = [
    "video/webm;codecs=vp8,opus",
    "video/webm;codecs=vp9,opus",
    "video/webm"
  ];

  const mimeType = mimeCandidates.find((candidate) => MediaRecorder.isTypeSupported(candidate));
  return mimeType ? { mimeType } : undefined;
}

function appendClip(listElement, blob, labelPrefix, count) {
  const clipUrl = URL.createObjectURL(blob);
  const clipName = `${labelPrefix}-${String(count).padStart(2, "0")}.webm`;
  const item = document.createElement("li");
  const link = document.createElement("a");
  link.href = clipUrl;
  link.download = clipName;
  link.textContent = `Download ${clipName}`;
  item.appendChild(link);
  listElement.appendChild(item);
}

async function blobToBase64(blob) {
  const arrayBuffer = await blob.arrayBuffer();
  const bytes = new Uint8Array(arrayBuffer);
  const chunkSize = 0x8000;
  let binary = "";

  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }

  return btoa(binary);
}

function getTranscriptDataForRange(startMs, endMs) {
  const lower = Number.isFinite(startMs) ? startMs : 0;
  const upper = Number.isFinite(endMs) ? endMs : Date.now();
  const entries = state.transcriptEvents
    .filter((event) => event.receivedAtMs >= lower && event.receivedAtMs <= upper)
    .map((event) => ({
      text: event.text,
      source: event.source,
      receivedAtIso: event.receivedAtIso,
      elapsedLabel: event.elapsedLabel
    }));
  const fullText = entries.map((event) => event.text).join("\n").trim();
  return {
    entries,
    fullText
  };
}

async function uploadClipToMongo({
  blob,
  clipName,
  clipType,
  reason,
  clipStartedAtMs,
  clipEndedAtMs
}) {
  try {
    const dataBase64 = await blobToBase64(blob);
    const transcript = getTranscriptDataForRange(clipStartedAtMs, clipEndedAtMs);
    const payload = {
      sessionId: CLIENT_SESSION_ID,
      clipName,
      clipType,
      reason,
      mimeType: blob.type || "video/webm",
      sizeBytes: blob.size,
      dataBase64,
      capturedAt: new Date().toISOString(),
      clipStartedAt: new Date(clipStartedAtMs).toISOString(),
      clipEndedAt: new Date(clipEndedAtMs).toISOString(),
      transcriptFullText: transcript.fullText,
      transcriptEntries: transcript.entries
    };

    const response = await fetch(CLIP_UPLOAD_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errorText = await response.text();
      addDiagnosticLog("mongo-upload-error", `${clipName} status=${response.status} ${errorText}`.trim());
      return;
    }

    const uploadResult = await response.json();
    const transcriptLength = (uploadResult.transcriptChars || 0);
    addDiagnosticLog(
      "mongo-upload-ok",
      `${clipName} -> livecook (${uploadResult.documentId || "no-id"}) url=${uploadResult.url || "n/a"} transcriptChars=${transcriptLength}`
    );
  } catch (error) {
    addDiagnosticLog("mongo-upload-error", `${clipName} ${error?.message || "unknown error"}`);
  }
}

function getSessionElapsedLabel(at = Date.now()) {
  if (!state.sessionStartedAt) {
    return "00:00";
  }

  const elapsedMs = Math.max(0, at - state.sessionStartedAt);
  const totalSeconds = Math.floor(elapsedMs / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function saveLowResSegment(reason = "rolling") {
  if (!state.lowChunks.length) {
    return;
  }

  const clipEndedAtMs = Date.now();
  const clipStartedAtMs = state.lowSegmentStartedAt || clipEndedAtMs;
  const clipDurationMs = Math.max(0, clipEndedAtMs - clipStartedAtMs);
  const isFullRollingWindow = (
    reason === "rolling-30s" && clipDurationMs >= state.lowResSegmentDurationMs
  );

  // Before: stopping low-res could upload a short tail clip.
  // After: only full rolling windows are persisted/uploaded.
  if (!isFullRollingWindow) {
    addDiagnosticLog(
      "low-res-segment-skipped",
      `${reason} durationMs=${clipDurationMs} thresholdMs=${state.lowResSegmentDurationMs}`
    );
    state.lowChunks = [];
    state.lowSegmentStartedAt = Date.now();
    return;
  }

  const blob = new Blob(state.lowChunks, { type: state.lowChunks[0].type || "video/webm" });
  state.lowClipCount += 1;
  const clipName = `low-res-${String(state.lowClipCount).padStart(2, "0")}.webm`;

  // Before: low-res clips were only added to the "Saved clips" list locally.
  // After: the same clip is still listed locally and also uploaded to MongoDB livecook.
  appendClip(lowResClips, blob, "low-res", state.lowClipCount);
  void uploadClipToMongo({
    blob,
    clipName,
    clipType: "low-res",
    reason,
    clipStartedAtMs,
    clipEndedAtMs
  });

  addDiagnosticLog("low-res-segment-saved", `${reason} #${state.lowClipCount} (${blob.size} bytes)`);
  state.lowChunks = [];
  state.lowSegmentStartedAt = Date.now();
}

function clearLowSegmentTimer() {
  if (state.lowSegmentTimer) {
    clearTimeout(state.lowSegmentTimer);
    state.lowSegmentTimer = null;
  }
}

function startLowResRecorderSegment() {
  if (!state.lowStream || !state.lowRecordingEnabled) {
    return;
  }

  const recorderOptions = pickRecorderOptions();
  state.lowChunks = [];
  state.lowSegmentStartedAt = Date.now();
  state.lowRecorderSegmentReason = "rolling-30s";
  state.lowRecorder = recorderOptions
    ? new MediaRecorder(state.lowStream, recorderOptions)
    : new MediaRecorder(state.lowStream);

  state.lowRecorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) {
      state.lowChunks.push(event.data);
      addDiagnosticLog("low-res-chunk", `${event.data.size} bytes`);
    }
  };

  state.lowRecorder.onstop = () => {
    clearLowSegmentTimer();
    const reason = state.lowRecorderSegmentReason || "rolling-30s";
    saveLowResSegment(reason);
    state.lowRecorder = null;
    state.lowRecorderSegmentReason = "rolling-30s";

    // Before: one long recorder stream was split by chunk arrays (later clips could be invalid).
    // After: each segment restarts MediaRecorder so every uploaded clip is a standalone container.
    if (state.lowRecordingEnabled) {
      startLowResRecorderSegment();
    }
  };

  state.lowRecorder.start(1000);
  clearLowSegmentTimer();
  state.lowSegmentTimer = setTimeout(() => {
    if (state.lowRecorder && state.lowRecorder.state !== "inactive") {
      state.lowRecorderSegmentReason = "rolling-30s";
      state.lowRecorder.stop();
    }
  }, state.lowResSegmentDurationMs);
}

function stopStream(stream) {
  if (!stream) {
    return;
  }

  stream.getTracks().forEach((track) => track.stop());
}

function getLiveAudioTrack(stream) {
  if (!stream) {
    return null;
  }

  const track = stream.getAudioTracks().find((item) => item.readyState === "live");
  return track || null;
}

function buildHighResRecordingStream(highStream) {
  const recordingStream = new MediaStream();
  highStream.getVideoTracks().forEach((track) => recordingStream.addTrack(track.clone()));

  const lowAudioTrack = getLiveAudioTrack(state.lowStream);
  const highAudioTrack = getLiveAudioTrack(highStream);

  if (lowAudioTrack) {
    recordingStream.addTrack(lowAudioTrack.clone());
    addDiagnosticLog("high-res-audio-source", "low-res stream");
  } else if (highAudioTrack) {
    recordingStream.addTrack(highAudioTrack.clone());
    addDiagnosticLog("high-res-audio-source", "high-res stream");
  } else {
    addDiagnosticLog("high-res-audio-source", "none");
  }

  const audioCount = recordingStream.getAudioTracks().length;
  const videoCount = recordingStream.getVideoTracks().length;
  addDiagnosticLog("high-res-track-count", `audio=${audioCount} video=${videoCount}`);
  return recordingStream;
}

function getWakeWord() {
  return WAKE_WORD;
}

function getStopWord() {
  return STOP_WORD;
}

function hasWholeWord(transcript, word) {
  const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`\\b${escaped}\\b`, "i");
  return pattern.test(transcript);
}

function isWakeWordDetected(transcript) {
  const wakeWord = getWakeWord();
  if (!wakeWord) {
    return false;
  }

  return hasWholeWord(transcript, wakeWord);
}

function isStopWordDetected(transcript) {
  const stopWord = getStopWord();
  if (!stopWord) {
    return false;
  }

  return hasWholeWord(transcript, stopWord);
}

function startAudioMeter(stream) {
  stopAudioMeter();
  addDiagnosticLog("mic-meter-start", "initializing audio context");

  try {
    state.meterAudioContext = new AudioContext();
    const source = state.meterAudioContext.createMediaStreamSource(stream);
    state.meterAnalyser = state.meterAudioContext.createAnalyser();
    state.meterAnalyser.fftSize = 2048;
    source.connect(state.meterAnalyser);

    const data = new Uint8Array(state.meterAnalyser.fftSize);

    const update = () => {
      state.meterAnalyser.getByteTimeDomainData(data);
      let sumSquares = 0;
      for (let i = 0; i < data.length; i += 1) {
        const normalized = (data[i] - 128) / 128;
        sumSquares += normalized * normalized;
      }

      const rms = Math.sqrt(sumSquares / data.length);
      if (rms > state.meterPeakSinceLastLog) {
        state.meterPeakSinceLastLog = rms;
      }

      const now = Date.now();
      if (!state.meterLastLogAt || now - state.meterLastLogAt >= 1000) {
        addDiagnosticLog("mic-rms-peak", state.meterPeakSinceLastLog.toFixed(4));
        state.meterPeakSinceLastLog = 0;
        state.meterLastLogAt = now;
      }

      const level = Math.min(100, Math.max(2, Math.round(rms * 300)));
      audioMeterFill.style.width = `${level}%`;
      state.meterAnimationId = requestAnimationFrame(update);
    };

    update();
  } catch {
    setStatus(lowResStatus, "Low-res recording active (audio level meter unavailable).");
    addDiagnosticLog("mic-meter-error", "failed to initialize");
  }
}

function stopAudioMeter() {
  if (state.meterAnimationId) {
    cancelAnimationFrame(state.meterAnimationId);
    state.meterAnimationId = null;
  }

  audioMeterFill.style.width = "2%";

  if (state.meterAudioContext) {
    state.meterAudioContext.close();
    state.meterAudioContext = null;
  }

  state.meterAnalyser = null;
  state.meterLastLogAt = 0;
  state.meterPeakSinceLastLog = 0;
  addDiagnosticLog("mic-meter-stop");
}

function handleWakeTranscript(transcript) {
  if (isStopWordDetected(transcript)) {
    if (state.lowStream || state.highRecorder) {
      addDiagnosticLog("stop-word-detected", transcript);
      stopLowResRecording();
    }
    return;
  }

  if (!isWakeWordDetected(transcript)) {
    return;
  }

  const cooldownMs = 5000;
  if (Date.now() - state.wakeLastTriggerAt < cooldownMs) {
    return;
  }

  state.wakeLastTriggerAt = Date.now();
  triggerHighResRecording(`Wake word detected: "${getWakeWord()}".`);
}

function showTranscript(transcript, source = "recognized") {
  const sourceLabel = source === "simulated" ? "simulated" : "recognized";
  const now = Date.now();
  const wallClock = new Date(now).toLocaleTimeString();
  const elapsed = getSessionElapsedLabel(now);
  state.transcriptCount += 1;
  transcriptStatus.textContent = `Latest transcript (${sourceLabel}) [${elapsed}]: "${transcript}"`;

  const entry = document.createElement("li");
  entry.textContent = `[${wallClock}] [+${elapsed}] (${sourceLabel}) ${transcript}`;
  transcriptLog.prepend(entry);

  const maxEntries = 300;
  while (transcriptLog.children.length > maxEntries) {
    transcriptLog.removeChild(transcriptLog.lastChild);
  }
}

function handleIncomingTranscript(transcript, source = "recognized") {
  const text = transcript.trim();
  if (!text) {
    return;
  }
  const receivedAtMs = Date.now();
  const elapsedLabel = getSessionElapsedLabel(receivedAtMs);
  state.transcriptEvents.push({
    text,
    source,
    receivedAtMs,
    receivedAtIso: new Date(receivedAtMs).toISOString(),
    elapsedLabel
  });
  const maxTranscriptEvents = 1500;
  if (state.transcriptEvents.length > maxTranscriptEvents) {
    state.transcriptEvents.splice(0, state.transcriptEvents.length - maxTranscriptEvents);
  }

  if (source === "recognized") {
    state.lastRealTranscriptAt = receivedAtMs;
  }

  addDiagnosticLog("transcript-received", `${source}: ${text}`);
  showTranscript(text, source);
  handleWakeTranscript(text);
}

function getWakeModeLabel() {
  return state.wakeMode === "on-device" ? "on-device transcription" : "browser transcription";
}

function getHighResDurationLabel() {
  const seconds = state.highResDurationMs / 1000;
  return Number.isInteger(seconds) ? String(seconds) : seconds.toFixed(1);
}

function ensureWakeTranscriber() {
  if (state.wakeTranscriber) {
    return;
  }

  state.wakeTranscriber = new OnboardTranscriber({
    onTranscript: (transcript) => {
      handleIncomingTranscript(transcript, "recognized");
    },
    onError: (errorText) => {
      if (!state.wakeListenerActive) {
        return;
      }

      addDiagnosticLog("wake-error", errorText);
      setStatus(wakeStatus, `Wake listener error: ${errorText}. Restarting...`, true);
    },
    onModeChange: (mode, context = {}) => {
      state.wakeMode = mode;
      addDiagnosticLog("wake-mode", `${context.previousMode || "none"} -> ${mode} (${context.reason || "unspecified"})`);

      if (!state.wakeListenerActive) {
        return;
      }

      if (context.reason === "fallback" && context.previousMode === "on-device" && mode === "browser") {
        setStatus(wakeStatus, `On-device transcription unavailable; using browser transcription for "${getWakeWord()}".`);
      }
    },
    onStateChange: (listenerState) => {
      addDiagnosticLog("wake-state", listenerState);
      if (!state.wakeListenerActive) {
        return;
      }

      if (listenerState === "restarting" || listenerState === "restart-pending") {
        setStatus(wakeStatus, `Listening for wake word: "${getWakeWord()}" (${getWakeModeLabel()}, reconnecting...)`, true);
        return;
      }

      if (listenerState === "listening") {
        setStatus(wakeStatus, `Listening for wake word: "${getWakeWord()}" (${getWakeModeLabel()}).`);
      }
    },
    onDebug: (payload) => {
      addDiagnosticLog(`stt-${payload.event}`, payload.detail || `${payload.mode}/${payload.active ? "active" : "inactive"}`);
    }
  });
}

function startWakeWordListener() {
  if (state.wakeListenerActive) {
    return;
  }

  addDiagnosticLog("wake-start-request", `wake="${getWakeWord()}"`);
  ensureWakeTranscriber();
  const startResult = state.wakeTranscriber.start({ wakeWord: getWakeWord() });
  if (!startResult.ok) {
    state.wakeListenerActive = false;
    state.wakeMode = "inactive";
    addDiagnosticLog("wake-start-failed", startResult.reason);
    setStatus(wakeStatus, startResult.reason, true);
    return;
  }

  state.wakeListenerActive = true;
  state.wakeMode = startResult.mode;
  addDiagnosticLog("wake-started", `mode=${startResult.mode}`);
  setStatus(wakeStatus, `Listening for wake word: "${getWakeWord()}" (${getWakeModeLabel()}).`);
  transcriptStatus.textContent = `Listening for transcription... say "${getWakeWord()}" or "${getStopWord()}".`;
}

function stopWakeWordListener() {
  state.wakeListenerActive = false;
  state.wakeMode = "inactive";
  addDiagnosticLog("wake-stop");

  if (state.wakeTranscriber) {
    state.wakeTranscriber.stop();
  }

  setStatus(wakeStatus, "Wake-word listener idle.");
}

async function triggerHighResRecording(triggerSource = "Manual wake-word trigger.") {
  if (!state.lowStream || state.highRecorder) {
    return;
  }

  addDiagnosticLog("high-res-trigger", triggerSource);
  setStatus(highResStatus, `Starting high-res capture. ${triggerSource}`);

  let highStream;
  try {
    highStream = await navigator.mediaDevices.getUserMedia(HIGH_RES_CONSTRAINTS);
  } catch (error) {
    try {
      highStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      setStatus(highResStatus, "High-res constraints not met; using available camera settings.", true);
      addDiagnosticLog("high-res-stream", "fallback constraints");
    } catch (fallbackError) {
      const primary = `${error?.name || "unknown"}: ${error?.message || "no detail"}`;
      const secondary = `${fallbackError?.name || "unknown"}: ${fallbackError?.message || "no detail"}`;
      addDiagnosticLog("high-res-stream-error", `primary=${primary}; fallback=${secondary}`);
      if (fallbackError?.name === "NotAllowedError" || fallbackError?.name === "PermissionDeniedError") {
        setStatus(highResStatus, "High-res camera/microphone permission blocked. Allow browser access and retry.", true);
      } else {
        setStatus(highResStatus, "Unable to open high-res camera/microphone stream.", true);
      }
      return;
    }
  }

  state.highStream = highStream;
  highResPreview.srcObject = highStream;
  state.highRecordingStream = buildHighResRecordingStream(highStream);

  const recorderOptions = pickRecorderOptions();
  state.highChunks = [];
  state.highClipStartedAt = Date.now();
  state.highRecorder = recorderOptions
    ? new MediaRecorder(state.highRecordingStream, recorderOptions)
    : new MediaRecorder(state.highRecordingStream);

  state.highRecorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) {
      state.highChunks.push(event.data);
      addDiagnosticLog("high-res-chunk", `${event.data.size} bytes`);
    }
  };

  state.highRecorder.onstop = () => {
    const blob = new Blob(state.highChunks, { type: state.highChunks[0]?.type || "video/webm" });
    state.highClipCount += 1;
    const clipName = `high-res-${String(state.highClipCount).padStart(2, "0")}.webm`;
    const clipEndedAtMs = Date.now();
    const clipStartedAtMs = state.highClipStartedAt || clipEndedAtMs;

    // Before: high-res trigger clips were only downloadable in-browser.
    // After: each clip remains downloadable and is also posted to MongoDB livecook.
    appendClip(highResClips, blob, "high-res", state.highClipCount);
    void uploadClipToMongo({
      blob,
      clipName,
      clipType: "high-res",
      reason: "wake-trigger",
      clipStartedAtMs,
      clipEndedAtMs
    });

    stopStream(state.highStream);
    stopStream(state.highRecordingStream);
    state.highStream = null;
    state.highRecordingStream = null;
    highResPreview.srcObject = null;
    state.highRecorder = null;
    state.highClipStartedAt = 0;
    clearTimeout(state.highResStopTimer);
    state.highResStopTimer = null;
    setStatus(highResStatus, "High-res recorder idle.");
  };

  state.highRecorder.start(1000);
  addDiagnosticLog("high-res-started", `${state.highResDurationMs}ms`);
  setStatus(highResStatus, `High-res recording active for ${getHighResDurationLabel()} seconds.`);

  clearTimeout(state.highResStopTimer);
  state.highResStopTimer = setTimeout(() => {
    if (state.highRecorder && state.highRecorder.state !== "inactive") {
      addDiagnosticLog("high-res-stop-timer");
      state.highRecorder.stop();
    }
  }, state.highResDurationMs);
}

async function startLowResRecording() {
  if (!navigator.mediaDevices?.getUserMedia) {
    setStatus(lowResStatus, "Media devices are not available in this browser.", true);
    return;
  }

  if (!window.MediaRecorder) {
    setStatus(lowResStatus, "MediaRecorder is not available in this browser.", true);
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia(LOW_RES_CONSTRAINTS);
    addDiagnosticLog("low-res-stream-opened", "constraints accepted");
    state.lowStream = stream;
    addDiagnosticLog("low-res-track-count", `audio=${stream.getAudioTracks().length} video=${stream.getVideoTracks().length}`);
    lowResPreview.srcObject = stream;
    startAudioMeter(stream);

    const recorderOptions = pickRecorderOptions();
    // Before: one recorder instance streamed forever.
    // After: each 30s window uses a fresh recorder instance.
    state.lowRecordingEnabled = true;
    state.lowSegmentStartedAt = Date.now();
    state.sessionStartedAt = Date.now();
    state.transcriptEvents = [];
    transcriptLog.innerHTML = "";
    void recorderOptions; // picker remains useful for startLowResRecorderSegment
    startLowResRecorderSegment();
    addDiagnosticLog("low-res-started", "recording + wake listener");
    setStatus(lowResStatus, "Low-res recording active (320x180 @ 10fps, auto-saving 30s clips).");
    toggleLowResBtn.textContent = "Stop low-res recording";
    startWakeWordListener();
  } catch (error) {
    const errorText = `${error?.name || "unknown"}: ${error?.message || "no detail"}`;
    addDiagnosticLog("low-res-stream-error", errorText);
    if (error?.name === "NotAllowedError" || error?.name === "PermissionDeniedError") {
      setStatus(lowResStatus, "Camera/microphone permission blocked. Allow access in browser site settings and retry.", true);
    } else {
      setStatus(lowResStatus, "Unable to open low-res camera/microphone stream.", true);
    }
  }
}

function stopLowResRecording() {
  addDiagnosticLog("low-res-stop");
  stopWakeWordListener();
  state.lowRecordingEnabled = false;
  clearLowSegmentTimer();

  if (state.lowRecorder && state.lowRecorder.state !== "inactive") {
    state.lowRecorderSegmentReason = "stop";
    state.lowRecorder.stop();
  }

  if (state.highRecorder && state.highRecorder.state !== "inactive") {
    state.highRecorder.stop();
  }

  clearTimeout(state.highResStopTimer);
  state.highResStopTimer = null;

  stopStream(state.lowStream);
  stopStream(state.highStream);
  stopStream(state.highRecordingStream);
  state.lowStream = null;
  state.highStream = null;
  state.highRecordingStream = null;
  state.lowChunks = [];
  state.lowSegmentStartedAt = 0;
  state.sessionStartedAt = 0;
  state.lowRecorder = null;
  state.highRecorder = null;
  state.highClipStartedAt = 0;

  lowResPreview.srcObject = null;
  highResPreview.srcObject = null;
  stopAudioMeter();

  setStatus(lowResStatus, "Low-res recorder idle.");
  setStatus(highResStatus, "High-res recorder idle.");
  toggleLowResBtn.textContent = "Start low-res recording";
}

toggleLowResBtn.addEventListener("click", () => {
  if (state.lowStream) {
    stopLowResRecording();
  } else {
    startLowResRecording();
  }
});

simulateWakeBtn.addEventListener("click", () => {
  triggerHighResRecording("Manual wake-word trigger.");
});

clearDiagnosticsBtn.addEventListener("click", () => {
  diagnosticsLog.innerHTML = "";
  state.diagnosticsCount = 0;
  diagnosticsStatus.textContent = "Diagnostics cleared.";
});

window.__liveCookTest = {
  triggerWakeWord: (transcript = "record") => {
    handleIncomingTranscript(transcript);
  },
  injectTranscript: (transcript = "simulated transcript") => {
    handleIncomingTranscript(transcript, "simulated");
  },
  setHighResDurationMs: (ms) => {
    if (Number.isFinite(ms) && ms > 0) {
      state.highResDurationMs = ms;
    }
  },
  setLowResSegmentDurationMs: (ms) => {
    if (Number.isFinite(ms) && ms >= 1000) {
      state.lowResSegmentDurationMs = ms;
    }
  },
  getDiagnosticsCount: () => state.diagnosticsCount,
  getState: () => ({
    lowStreamActive: Boolean(state.lowStream),
    lowRecorderState: state.lowRecorder?.state || "inactive",
    highRecorderState: state.highRecorder?.state || "inactive",
    wakeListenerActive: state.wakeListenerActive,
    wakeMode: state.wakeMode,
    wakeWord: getWakeWord(),
    transcriptCount: state.transcriptCount,
    diagnosticsCount: state.diagnosticsCount,
    lowClipCount: state.lowClipCount,
    highClipCount: state.highClipCount,
    highResDurationMs: state.highResDurationMs,
    lowResSegmentDurationMs: state.lowResSegmentDurationMs
  })
};

setStatus(lowResStatus, "Low-res recorder idle.");
setStatus(wakeStatus, "Wake-word listener idle.");
setStatus(highResStatus, "High-res recorder idle.");
transcriptStatus.textContent = "Waiting for transcription...";
diagnosticsStatus.textContent = "Diagnostics ready.";
addDiagnosticLog("app-ready", `session=${CLIENT_SESSION_ID}`);
