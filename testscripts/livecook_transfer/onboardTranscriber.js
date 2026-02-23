export class OnboardTranscriber {
  constructor({ onTranscript, onError, onModeChange, onStateChange, onDebug } = {}) {
    this.onTranscript = onTranscript || (() => {});
    this.onError = onError || (() => {});
    this.onModeChange = onModeChange || (() => {});
    this.onStateChange = onStateChange || (() => {});
    this.onDebug = onDebug || (() => {});
    this.recognition = null;
    this.active = false;
    this.wakeWord = "record";
    this.mode = "inactive";
  }

  emitDebug(event, detail = "") {
    this.onDebug({ event, detail, mode: this.mode, active: this.active });
  }

  start({ wakeWord = "record" } = {}) {
    this.wakeWord = wakeWord;

    // Before: app could fail at import-time if this file was missing.
    // After: app always has a transcriber class and falls back to browser STT.
    const SpeechRecognition = globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      const reason = "SpeechRecognition is unavailable in this browser.";
      this.onError(reason);
      return { ok: false, reason };
    }

    this.recognition = new SpeechRecognition();
    this.recognition.lang = "en-US";
    this.recognition.continuous = true;
    this.recognition.interimResults = false;

    this.recognition.onstart = () => {
      this.active = true;
      this.onStateChange("listening");
      this.emitDebug("started", `wake=${this.wakeWord}`);
    };

    this.recognition.onerror = (event) => {
      const errorText = event?.error || "unknown speech recognition error";
      this.onStateChange("restarting");
      this.onError(errorText);
      this.emitDebug("error", errorText);
    };

    this.recognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (!result.isFinal) {
          continue;
        }

        const transcript = result[0]?.transcript || "";
        if (transcript.trim()) {
          this.onTranscript(transcript.trim());
          this.emitDebug("transcript", transcript.trim());
        }
      }
    };

    this.recognition.onend = () => {
      if (!this.active) {
        this.onStateChange("idle");
        return;
      }

      this.onStateChange("restart-pending");
      setTimeout(() => {
        if (!this.active) {
          return;
        }

        try {
          this.recognition.start();
        } catch {
          // Browser may still be tearing down previous STT session.
        }
      }, 250);
    };

    this.mode = "browser";
    this.onModeChange("browser", {
      previousMode: "inactive",
      reason: "fallback"
    });

    try {
      this.recognition.start();
    } catch {
      // Ignore duplicate start() calls while restarting.
    }

    return { ok: true, mode: "browser" };
  }

  stop() {
    this.active = false;
    this.mode = "inactive";

    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch {
        // Ignore stop race with browser STT lifecycle.
      }
    }

    this.onStateChange("idle");
    this.emitDebug("stopped");
  }
}
