const fields = {
  status: document.querySelector("#status-line"),
  sessionPhase: document.querySelector("#session-phase"),
  voiceMode: document.querySelector("#voice-mode"),
  muted: document.querySelector("#muted"),
  sttStatus: document.querySelector("#stt-status"),
  ttsStatus: document.querySelector("#tts-status"),
  pixelStatus: document.querySelector("#pixel-status"),
  secondDisplayStatus: document.querySelector("#second-display-status"),
  windStatus: document.querySelector("#wind-status"),
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
  suggestedGear: document.querySelector("#suggested-gear"),
  tireHot: document.querySelector("#tire-hot"),
  tireSpread: document.querySelector("#tire-spread"),
  tireAge: document.querySelector("#tire-age"),
  incident: document.querySelector("#incident"),
  wheelspin: document.querySelector("#wheelspin"),
  lockups: document.querySelector("#lockups"),
  lastTranscript: document.querySelector("#last-transcript"),
  lastIntent: document.querySelector("#last-intent"),
  lastConfidence: document.querySelector("#last-confidence"),
  lastRepair: document.querySelector("#last-repair"),
  controlStatus: document.querySelector("#control-status"),
  bridgeProcess: document.querySelector("#bridge-process"),
  bridgeChannel: document.querySelector("#bridge-channel"),
  bridgePackets: document.querySelector("#bridge-packets"),
  bridgeError: document.querySelector("#bridge-error"),
  bridgeRestartNote: document.querySelector("#bridge-restart-note"),
  windCurrentLevel: document.querySelector("#wind-current-level"),
  windTargetLevel: document.querySelector("#wind-target-level"),
  windLastLevel: document.querySelector("#wind-last-level"),
  windError: document.querySelector("#wind-error"),
  alerts: document.querySelector("#alerts"),
  form: document.querySelector("#chat-form"),
  input: document.querySelector("#chat-input"),
  response: document.querySelector("#chat-response"),
};

const controls = {
  settingsForm: document.querySelector("#settings-form"),
  preset: document.querySelector("#settings-preset"),
  voiceMode: document.querySelector("#settings-voice-mode"),
  muted: document.querySelector("#settings-muted"),
  verbosityForm: document.querySelector("#verbosity-form"),
  verbosityControls: document.querySelector("#verbosity-controls"),
  sttForm: document.querySelector("#stt-form"),
  sttEnabled: document.querySelector("#stt-enabled-control"),
  sttModel: document.querySelector("#stt-model-control"),
  sttDevice: document.querySelector("#stt-device-control"),
  sttConfidence: document.querySelector("#stt-confidence-control"),
  discordStt: document.querySelector("#discord-stt-control"),
  bridgeStart: document.querySelector("#bridge-start"),
  bridgeStop: document.querySelector("#bridge-stop"),
  bridgeRestart: document.querySelector("#bridge-restart"),
  pixelForm: document.querySelector("#pixel-form"),
  pixelStart: document.querySelector("#pixel-start"),
  pixelStop: document.querySelector("#pixel-stop"),
  pixelPreview: document.querySelector("#pixel-preview"),
  secondDisplayForm: document.querySelector("#second-display-form"),
  secondDisplayStart: document.querySelector("#second-display-start"),
  secondDisplayStop: document.querySelector("#second-display-stop"),
  secondDisplayPreview: document.querySelector("#second-display-preview"),
  windForm: document.querySelector("#wind-form"),
  windStart: document.querySelector("#wind-start"),
  windStop: document.querySelector("#wind-stop"),
};

const pixelFields = {
  enabled: document.querySelector("#pixel-enabled-control"),
  address: document.querySelector("#pixel-address-control"),
  color_theme: document.querySelector("#pixel-theme-control"),
  brightness: document.querySelector("#pixel-brightness-control"),
  dim_brightness: document.querySelector("#pixel-dim-control"),
  orientation: document.querySelector("#pixel-orientation-control"),
  update_hz: document.querySelector("#pixel-update-control"),
  size_source: document.querySelector("#pixel-size-source-control"),
  width: document.querySelector("#pixel-width-control"),
  height: document.querySelector("#pixel-height-control"),
  gear_layout: document.querySelector("#pixel-gear-layout-control"),
  rev_position: document.querySelector("#pixel-rev-position-control"),
  rev_scale: document.querySelector("#pixel-rev-scale-control"),
  rev_start_percent: document.querySelector("#pixel-rev-start-control"),
  shift_mode: document.querySelector("#pixel-shift-mode-control"),
  shift_percent: document.querySelector("#pixel-shift-percent-control"),
  flash_hz: document.querySelector("#pixel-flash-control"),
  fuel_enabled: document.querySelector("#pixel-fuel-enabled-control"),
  gear_color: document.querySelector("#pixel-gear-color-control"),
  rev_low_color: document.querySelector("#pixel-rev-low-control"),
  rev_mid_color: document.querySelector("#pixel-rev-mid-control"),
  rev_high_color: document.querySelector("#pixel-rev-high-control"),
  shift_color: document.querySelector("#pixel-shift-color-control"),
  fuel_safe_color: document.querySelector("#pixel-fuel-safe-control"),
  fuel_warn_color: document.querySelector("#pixel-fuel-warn-control"),
  fuel_danger_color: document.querySelector("#pixel-fuel-danger-control"),
  fuel_critical_color: document.querySelector("#pixel-fuel-critical-control"),
  rpm_min: document.querySelector("#pixel-rpm-min-control"),
  rpm_max: document.querySelector("#pixel-rpm-max-control"),
};

const secondDisplayFields = {
  enabled: document.querySelector("#second-display-enabled-control"),
  address: document.querySelector("#second-display-address-control"),
  brightness: document.querySelector("#second-display-brightness-control"),
  dim_brightness: document.querySelector("#second-display-dim-control"),
  orientation: document.querySelector("#second-display-orientation-control"),
  update_hz: document.querySelector("#second-display-update-control"),
  size_source: document.querySelector("#second-display-size-source-control"),
  width: document.querySelector("#second-display-width-control"),
  height: document.querySelector("#second-display-height-control"),
  alert_hold_seconds: document.querySelector("#second-display-alert-hold-control"),
  flash_hold_seconds: document.querySelector("#second-display-flash-hold-control"),
  label_color: document.querySelector("#second-display-label-color-control"),
  count_color: document.querySelector("#second-display-count-color-control"),
  active_color: document.querySelector("#second-display-active-color-control"),
  alert_color: document.querySelector("#second-display-alert-color-control"),
  dim_color: document.querySelector("#second-display-dim-color-control"),
  tire_normal_color: document.querySelector("#second-display-tire-normal-control"),
  tire_warm_color: document.querySelector("#second-display-tire-warm-control"),
  tire_hot_color: document.querySelector("#second-display-tire-hot-control"),
};

const windFields = {
  enabled: document.querySelector("#wind-enabled-control"),
  ha_base_url: document.querySelector("#wind-ha-base-url-control"),
  ha_entity_id: document.querySelector("#wind-entity-control"),
  update_hz: document.querySelector("#wind-update-control"),
  max_speed_kph: document.querySelector("#wind-max-speed-control"),
  deadband_kph: document.querySelector("#wind-deadband-control"),
  curve_exponent: document.querySelector("#wind-curve-control"),
  off_level: document.querySelector("#wind-off-level-control"),
  min_active_level: document.querySelector("#wind-min-active-level-control"),
  max_level: document.querySelector("#wind-max-level-control"),
  smoothing_seconds: document.querySelector("#wind-smoothing-control"),
  hysteresis_levels: document.querySelector("#wind-hysteresis-control"),
  timeout_seconds: document.querySelector("#wind-timeout-control"),
};

let controlsInitialized = false;
let controlsDirty = false;

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

function lapsText(value) {
  if (value === null || value === undefined) return "--";
  const count = Number(value);
  if (!Number.isFinite(count)) return "--";
  return `${count} ${count === 1 ? "lap" : "laps"}`;
}

function fillOptions(select, options) {
  if (!select || !Array.isArray(options)) return;
  const current = Array.from(select.options).map((option) => option.value).join(",");
  if (current === options.join(",")) return;
  select.replaceChildren(
    ...options.map((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      return option;
    })
  );
}

function setValue(element, value) {
  if (!element || document.activeElement === element) return;
  if (element.type === "checkbox") {
    element.checked = Boolean(value);
  } else {
    element.value = value === null || value === undefined ? "" : String(value);
  }
}

function setControlsEnabled(allowed) {
  document.querySelectorAll("[data-control]").forEach((element) => {
    element.disabled = !allowed;
  });
}

function render(data, { forceControls = false } = {}) {
  const snap = data.snapshot || {};
  fields.status.textContent = snap.connected
    ? `Telemetry live · ${fmt(snap.packet_rate_hz, " Hz", 1)} · ${snap.session_phase || "unknown"}`
    : "Waiting for telemetry";
  fields.sessionPhase.textContent = snap.session_phase || "unknown";
  fields.voiceMode.textContent = data.voice?.mode || "quiet_driver";
  fields.muted.textContent = data.voice?.muted ? "muted" : "live";
  fields.sttStatus.textContent = data.audio?.stt?.enabled ? "stt on" : "stt off";
  fields.ttsStatus.textContent = data.audio?.tts?.engine || data.config?.tts?.engine || "tts";
  renderPixelStatus(data);
  renderSecondDisplayStatus(data);
  renderWindStatus(data);
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
  fields.suggestedGear.textContent = snap.suggested_gear ?? "--";
  fields.tireHot.textContent = fmt(wheelMax(snap.tire_temps), "°", 0);
  fields.tireSpread.textContent = fmt(wheelSpread(snap.tire_temps), "°", 0);
  fields.tireAge.textContent = lapsText(snap.tire_age_laps);
  fields.incident.textContent = snap.incident_status || "--";
  fields.wheelspin.textContent = snap.driving_style?.wheelspin_events ?? 0;
  fields.lockups.textContent = snap.driving_style?.lockup_events ?? 0;
  renderVoiceDebug(data);
  renderBridge(data);
  renderWind(data);
  renderControls(data, { force: forceControls });
  fields.alerts.replaceChildren(
    ...(data.alerts || []).slice(-12).reverse().map((alert) => {
      const item = document.createElement("li");
      item.textContent = alert.message;
      return item;
    })
  );
}

function renderWindStatus(data) {
  const wind = data.wind || {};
  const windConfig = data.config?.wind || {};
  const enabled = Boolean(wind.enabled || windConfig.enabled);
  if (!enabled) {
    fields.windStatus.textContent = "wind off";
  } else if (wind.last_error) {
    fields.windStatus.textContent = "wind warn";
  } else if (wind.connected) {
    fields.windStatus.textContent = "wind live";
  } else {
    fields.windStatus.textContent = "wind wait";
  }
}

function renderPixelStatus(data) {
  const pixel = data.pixel_display || {};
  const pixelConfig = data.config?.pixel_display || {};
  const pixelEnabled = Boolean(pixel.enabled || pixelConfig.enabled);
  if (!pixelEnabled) {
    fields.pixelStatus.textContent = "pixel off";
  } else if (pixel.connected) {
    const size = pixel.device_width && pixel.device_height
      ? ` ${pixel.device_width}x${pixel.device_height}`
      : "";
    fields.pixelStatus.textContent = `pixel live${size}`;
  } else {
    fields.pixelStatus.textContent = pixel.last_error ? "pixel warn" : "pixel wait";
  }
}

function renderSecondDisplayStatus(data) {
  const display = data.second_display || {};
  const config = data.config?.second_display || {};
  const enabled = Boolean(display.enabled || config.enabled);
  if (!enabled) {
    fields.secondDisplayStatus.textContent = "coach off";
  } else if (display.connected) {
    const size = display.device_width && display.device_height
      ? ` ${display.device_width}x${display.device_height}`
      : "";
    fields.secondDisplayStatus.textContent = `coach live${size}`;
  } else {
    fields.secondDisplayStatus.textContent = display.last_error ? "coach warn" : "coach wait";
  }
}

function renderVoiceDebug(data) {
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
}

function renderBridge(data) {
  const bridge = data.discord_bridge || {};
  const heartbeat = bridge.heartbeat?.payload || {};
  const state = bridge.restart_required ? `${bridge.state} · restart needed` : bridge.state || "--";
  fields.bridgeProcess.textContent = bridge.pid ? `${state} (${bridge.pid})` : state;
  fields.bridgeChannel.textContent = heartbeat.voiceChannelId || "--";
  fields.bridgePackets.textContent = heartbeat.driverAudioPackets ?? "--";
  fields.bridgeError.textContent = heartbeat.lastError || bridge.last_error || "--";
  fields.bridgeRestartNote.textContent = bridge.restart_required
    ? "Restart the bridge to apply bridge-side settings."
    : "";
}

function renderWind(data) {
  const wind = data.wind || {};
  fields.windCurrentLevel.textContent = wind.current_level ?? "--";
  fields.windTargetLevel.textContent = wind.target_level ?? "--";
  fields.windLastLevel.textContent = wind.last_sent_level ?? "--";
  fields.windError.textContent = wind.last_error || "--";
}

function renderControls(data, { force = false } = {}) {
  const allowed = Boolean(data.control_allowed ?? data.control?.allowed);
  fields.controlStatus.textContent = allowed
    ? "Controls enabled on localhost. Saves update .env."
    : data.control?.reason || "Controls are local only.";
  setControlsEnabled(allowed);
  initializeControls(data);
  setControlsEnabled(allowed);
  if (controlsDirty && !force) return;

  const config = data.config || {};
  const stt = data.audio?.stt || {};
  setValue(controls.preset, config.preset || "endurance");
  setValue(controls.voiceMode, data.voice?.mode || config.voice_mode || "quiet_driver");
  setValue(controls.muted, Boolean(data.voice?.muted));
  setValue(controls.sttEnabled, Boolean(stt.enabled));
  setValue(controls.sttModel, stt.model || config.stt?.model || "tiny.en");
  setValue(controls.sttDevice, stt.device || config.stt?.device || "auto");
  setValue(controls.sttConfidence, stt.min_confidence ?? 0.55);
  setValue(controls.discordStt, Boolean(config.discord_stt_enabled));

  const verbosity = config.verbosity || {};
  for (const [category, select] of Object.entries(verbosityControls())) {
    setValue(select, verbosity[category] || "off");
  }

  const pixel = config.pixel_display || {};
  for (const [name, element] of Object.entries(pixelFields)) {
    setValue(element, pixel[name]);
  }
  const secondDisplay = config.second_display || {};
  for (const [name, element] of Object.entries(secondDisplayFields)) {
    setValue(element, secondDisplay[name]);
  }
  const wind = config.wind || {};
  for (const [name, element] of Object.entries(windFields)) {
    setValue(element, wind[name]);
  }
  controls.pixelPreview.src = allowed ? `/api/control/pixel-display/preview.png?t=${Date.now()}` : "";
  controls.secondDisplayPreview.src = allowed ? `/api/control/second-display/preview.png?t=${Date.now()}` : "";
}

function initializeControls(data) {
  if (controlsInitialized) return;
  const options = data.options || {};
  fillOptions(controls.preset, options.presets || []);
  fillOptions(controls.voiceMode, options.voice_modes || []);
  fillOptions(controls.sttDevice, options.stt_devices || []);
  fillOptions(pixelFields.color_theme, options.pixel?.color_themes || []);
  fillOptions(pixelFields.size_source, options.pixel?.size_sources || []);
  fillOptions(pixelFields.gear_layout, options.pixel?.gear_layouts || []);
  fillOptions(pixelFields.rev_position, options.pixel?.rev_positions || []);
  fillOptions(pixelFields.rev_scale, options.pixel?.rev_scales || []);
  fillOptions(pixelFields.shift_mode, options.pixel?.shift_modes || []);
  fillOptions(secondDisplayFields.size_source, options.second_display?.size_sources || []);

  controls.verbosityControls.replaceChildren(
    ...(options.verbosity_categories || []).map((category) => {
      const label = document.createElement("label");
      label.textContent = category;
      const select = document.createElement("select");
      select.dataset.control = "";
      select.dataset.category = category;
      fillOptions(select, options.verbosity_levels || []);
      label.appendChild(select);
      return label;
    })
  );
  watchControlChanges();
  controlsInitialized = true;
}

function verbosityControls() {
  return Object.fromEntries(
    Array.from(controls.verbosityControls.querySelectorAll("select")).map((select) => [
      select.dataset.category,
      select,
    ])
  );
}

function watchControlChanges() {
  document.querySelectorAll("[data-control]").forEach((element) => {
    element.addEventListener("input", () => {
      controlsDirty = true;
    });
    element.addEventListener("change", () => {
      controlsDirty = true;
    });
  });
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed with HTTP ${response.status}`);
  }
  return payload;
}

async function saveControl(url, body) {
  try {
    const payload = await requestJson(url, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    controlsDirty = false;
    render(payload.status || (await fetchStatus()), { forceControls: true });
  } catch (error) {
    fields.controlStatus.textContent = error.message;
  }
}

async function postControl(url) {
  try {
    const payload = await requestJson(url, { method: "POST" });
    controlsDirty = false;
    render(payload.status || (await fetchStatus()), { forceControls: true });
  } catch (error) {
    fields.controlStatus.textContent = error.message;
  }
}

async function fetchStatus() {
  const response = await fetch("/api/status", { cache: "no-store" });
  return response.json();
}

async function poll(options = {}) {
  try {
    render(await fetchStatus(), options);
  } catch (error) {
    fields.status.textContent = "HUD disconnected";
  }
}

controls.settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await saveControl("/api/control/settings", {
    preset: controls.preset.value,
    voice_mode: controls.voiceMode.value,
    muted: controls.muted.checked,
  });
});

controls.verbosityForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const verbosity = Object.fromEntries(
    Object.entries(verbosityControls()).map(([category, select]) => [category, select.value])
  );
  await saveControl("/api/control/settings", { verbosity });
});

controls.sttForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await saveControl("/api/control/stt", {
    enabled: controls.sttEnabled.checked,
    model: controls.sttModel.value,
    device: controls.sttDevice.value,
    min_confidence: Number(controls.sttConfidence.value),
    discord_enabled: controls.discordStt.checked,
  });
});

controls.pixelForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await saveControl("/api/control/pixel-display", readPixelPayload());
});

controls.secondDisplayForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await saveControl("/api/control/second-display", readSecondDisplayPayload());
});

controls.windForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await saveControl("/api/control/wind", readWindPayload());
});

controls.bridgeStart.addEventListener("click", () => postControl("/api/control/discord-bridge/start"));
controls.bridgeStop.addEventListener("click", () => postControl("/api/control/discord-bridge/stop"));
controls.bridgeRestart.addEventListener("click", () => postControl("/api/control/discord-bridge/restart"));
controls.pixelStart.addEventListener("click", () => postControl("/api/control/pixel-display/start"));
controls.pixelStop.addEventListener("click", () => postControl("/api/control/pixel-display/stop"));
controls.secondDisplayStart.addEventListener("click", () => postControl("/api/control/second-display/start"));
controls.secondDisplayStop.addEventListener("click", () => postControl("/api/control/second-display/stop"));
controls.windStart.addEventListener("click", () => postControl("/api/control/wind/start"));
controls.windStop.addEventListener("click", () => postControl("/api/control/wind/stop"));

function readPixelPayload() {
  const payload = {};
  for (const [name, element] of Object.entries(pixelFields)) {
    payload[name] = element.type === "checkbox" ? element.checked : element.value;
  }
  return payload;
}

function readSecondDisplayPayload() {
  const payload = {};
  for (const [name, element] of Object.entries(secondDisplayFields)) {
    payload[name] = element.type === "checkbox" ? element.checked : element.value;
  }
  return payload;
}

function readWindPayload() {
  const payload = {};
  for (const [name, element] of Object.entries(windFields)) {
    payload[name] = element.type === "checkbox" ? element.checked : element.value;
  }
  return payload;
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

poll({ forceControls: true });
setInterval(() => poll(), 1000);
