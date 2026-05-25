const fields = {
  status: document.querySelector("#status-line"),
  sessionPhase: document.querySelector("#session-phase"),
  voiceMode: document.querySelector("#voice-mode"),
  muted: document.querySelector("#muted"),
  sttStatus: document.querySelector("#stt-status"),
  ttsStatus: document.querySelector("#tts-status"),
  pixelStatus: document.querySelector("#pixel-status"),
  position: document.querySelector("#position"),
  lap: document.querySelector("#lap"),
  raceDuration: document.querySelector("#race-duration"),
  remainingLabel: document.querySelector("#remaining-label"),
  raceRemaining: document.querySelector("#race-remaining"),
  lastLap: document.querySelector("#last-lap"),
  bestLap: document.querySelector("#best-lap"),
  averageLap: document.querySelector("#average-lap"),
  fuelLevel: document.querySelector("#fuel-level"),
  fuelLaps: document.querySelector("#fuel-laps"),
  fuelMargin: document.querySelector("#fuel-margin"),
  pit: document.querySelector("#pit-recommendation"),
  speed: document.querySelector("#speed"),
  rpm: document.querySelector("#rpm"),
  gear: document.querySelector("#gear"),
  tireHot: document.querySelector("#tire-hot"),
  tireSpread: document.querySelector("#tire-spread"),
  tireWear: document.querySelector("#tire-wear"),
  incident: document.querySelector("#incident"),
  wheelspin: document.querySelector("#wheelspin"),
  lockups: document.querySelector("#lockups"),
  lastTranscript: document.querySelector("#last-transcript"),
  lastIntent: document.querySelector("#last-intent"),
  lastConfidence: document.querySelector("#last-confidence"),
  lastRepair: document.querySelector("#last-repair"),
  alerts: document.querySelector("#alerts"),
  form: document.querySelector("#chat-form"),
  input: document.querySelector("#chat-input"),
  response: document.querySelector("#chat-response"),
};

function fmt(value, suffix = "", digits = 0) {
  if (value === null || value === undefined) return "--";
  return `${Number(value).toFixed(digits)}${suffix}`;
}

function durationFromMinutes(value) {
  if (value === null || value === undefined || value === "") return "--:--";
  const totalSeconds = Math.max(0, Math.round(Number(value) * 60));
  if (!Number.isFinite(totalSeconds)) return "--:--";
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function wheelValues(values) {
  return ["fl", "fr", "rl", "rr"]
    .map((key) => values?.[key])
    .filter((value) => value !== null && value !== undefined)
    .map(Number);
}

function wheelMax(values) {
  const present = wheelValues(values);
  return present.length ? Math.max(...present) : null;
}

function wheelSpread(values) {
  const present = wheelValues(values);
  return present.length ? Math.max(...present) - Math.min(...present) : null;
}

function render(data) {
  const snap = data.snapshot || {};
  fields.status.textContent = snap.connected
    ? `Telemetry live · ${fmt(snap.packet_rate_hz, " Hz", 1)} · ${snap.session_phase || "unknown"}`
    : "Waiting for telemetry";
  fields.sessionPhase.textContent = snap.session_phase || "unknown";
  fields.voiceMode.textContent = data.voice?.mode || "quiet_driver";
  fields.muted.textContent = data.voice?.muted ? "muted" : "live";
  fields.sttStatus.textContent = data.audio?.stt?.enabled ? "stt on" : "stt off";
  fields.ttsStatus.textContent = data.audio?.tts?.engine || data.config?.tts?.engine || "tts";
  const pixel = data.pixel_display || {};
  if (!pixel.enabled) {
    fields.pixelStatus.textContent = "pixel off";
  } else if (pixel.connected) {
    const size = pixel.device_width && pixel.device_height
      ? ` ${pixel.device_width}x${pixel.device_height}`
      : "";
    fields.pixelStatus.textContent = `pixel live${size}`;
  } else {
    fields.pixelStatus.textContent = pixel.last_error ? "pixel warn" : "pixel wait";
  }
  fields.position.textContent = snap.current_position ? `P${snap.current_position}` : "--";
  fields.lap.textContent = snap.current_lap
    ? snap.total_laps
      ? `${snap.current_lap}/${snap.total_laps}`
      : `${snap.current_lap}`
    : "--";
  fields.raceDuration.textContent =
    snap.race_duration && snap.race_duration !== "--:--"
      ? snap.race_duration
      : durationFromMinutes(data.config?.race_duration_minutes);
  if (snap.race_mode === "timed") {
    fields.remainingLabel.textContent = "Time Left";
    fields.raceRemaining.textContent = snap.race_time_remaining || "--:--";
  } else {
    fields.remainingLabel.textContent = "Laps Left";
    fields.raceRemaining.textContent = snap.laps_left ?? "--";
  }
  fields.lastLap.textContent = snap.last_lap_time || "--:--.---";
  fields.bestLap.textContent = snap.best_lap_time || "--:--.---";
  fields.averageLap.textContent = snap.average_lap_time || "--:--.---";
  fields.fuelLevel.textContent = fmt(snap.fuel_level_percent ?? snap.fuel_level, "%", 1);
  fields.fuelLaps.textContent = fmt(snap.fuel_laps_remaining, "", 1);
  fields.fuelMargin.textContent = fmt(snap.fuel_margin_laps, "", 1);
  fields.pit.textContent = snap.pit_recommendation || "No fuel data yet.";
  fields.speed.textContent = fmt(snap.speed_kph, " kph", 0);
  fields.rpm.textContent = fmt(snap.engine_rpm, "", 0);
  fields.gear.textContent = snap.current_gear ?? "--";
  fields.tireHot.textContent = fmt(wheelMax(snap.tire_temps), "°", 0);
  fields.tireSpread.textContent = fmt(wheelSpread(snap.tire_temps), "°", 0);
  fields.tireWear.textContent = fmt(wheelMax(snap.tire_wear_percent), "%", 0);
  fields.incident.textContent = snap.incident_status || "--";
  fields.wheelspin.textContent = snap.driving_style?.wheelspin_events ?? 0;
  fields.lockups.textContent = snap.driving_style?.lockup_events ?? 0;
  const voiceLast = data.voice?.last || {};
  const repair = voiceLast.repair || null;
  fields.lastTranscript.textContent = voiceLast.text || "--";
  fields.lastIntent.textContent = voiceLast.intent
    ? `${voiceLast.intent}${voiceLast.ignored ? " (ignored)" : ""}`
    : "--";
  fields.lastConfidence.textContent =
    voiceLast.confidence === null || voiceLast.confidence === undefined
      ? "--"
      : Number(voiceLast.confidence).toFixed(2);
  fields.lastRepair.textContent = repair
    ? `${repair.intent} · ${Number(repair.confidence).toFixed(2)}`
    : "--";
  fields.alerts.replaceChildren(
    ...(data.alerts || []).slice(-12).reverse().map((alert) => {
      const item = document.createElement("li");
      item.textContent = alert.message;
      return item;
    })
  );
}

async function poll() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    render(await response.json());
  } catch (error) {
    fields.status.textContent = "HUD disconnected";
  }
}

fields.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = fields.input.value.trim();
  if (!text) return;
  fields.input.value = "";
    const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, source: "hud" }),
  });
  const data = await response.json();
  fields.response.textContent = data.response || "Ignored.";
  await poll();
});

poll();
setInterval(poll, 1000);
