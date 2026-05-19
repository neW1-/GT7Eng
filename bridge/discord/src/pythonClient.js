export class PythonServiceClient {
  constructor({ baseUrl, token, statusTimeoutMs = 3000, fetchImpl = globalThis.fetch }) {
    this.baseUrl = baseUrl;
    this.token = token;
    this.statusTimeoutMs = statusTimeoutMs;
    this.fetch = fetchImpl;
  }

  async health() {
    const response = await this.request("/health", { method: "GET", timeoutMs: this.statusTimeoutMs });
    return { ok: response.ok, status: response.status };
  }

  async nextVoiceJob() {
    const response = await this.request("/discord/voice/jobs?limit=1", { method: "GET" });
    if (!response.ok) throw new Error(`Python job poll failed with HTTP ${response.status}`);
    const payload = await response.json();
    return Array.isArray(payload.jobs) ? payload.jobs[0] : null;
  }

  async acknowledgeJob(id, status, detail) {
    if (!id) return;
    await this.request(`/discord/voice/jobs/${encodeURIComponent(id)}/ack`, {
      method: "POST",
      body: { status, detail }
    });
  }

  async synthesizeSpeech(text) {
    const response = await this.request("/discord/tts", {
      method: "POST",
      body: { text }
    });
    if (!response.ok) throw new Error(`Python TTS failed with HTTP ${response.status}`);
    return response.json();
  }

  async setEngineerMuted(muted) {
    await this.request("/discord/engineer/mute", {
      method: "POST",
      body: { muted }
    });
  }

  async setMode(mode) {
    await this.request("/discord/mode", {
      method: "POST",
      body: { mode }
    });
  }

  async request(path, { method, body, timeoutMs } = {}) {
    if (!this.fetch) throw new Error("global fetch is not available; use Node 20 or newer");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs ?? 10000);
    try {
      return await this.fetch(`${this.baseUrl}${path}`, {
        method,
        signal: controller.signal,
        headers: this.headers(body),
        body: body ? JSON.stringify(body) : undefined
      });
    } finally {
      clearTimeout(timer);
    }
  }

  headers(body) {
    const headers = {};
    if (body) headers["content-type"] = "application/json";
    if (this.token) headers.authorization = `Bearer ${this.token}`;
    return headers;
  }
}
