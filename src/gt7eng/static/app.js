const fields = {
  status: document.querySelector("#status-line"),
  voiceMode: document.querySelector("#voice-mode"),
  muted: document.querySelector("#muted"),
  position: document.querySelector("#position"),
  lap: document.querySelector("#lap"),
  lapsLeft: document.querySelector("#laps-left"),
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
  alerts: document.querySelector("#alerts"),
  form: document.querySelector("#chat-form"),
  input: document.querySelector("#chat-input"),
  response: document.querySelector("#chat-response"),
};

function fmt(value, suffix = "", digits = 0) {
  if (value === null || value === undefined) return "--";
  return `${Number(value).toFixed(digits)}${suffix}`;
}

function render(data) {
  const snap = data.snapshot || {};
  fields.status.textContent = snap.connected
    ? `Telemetry live · ${fmt(snap.packet_rate_hz, " Hz", 1)}`
    : "Waiting for telemetry";
  fields.voiceMode.textContent = data.voice?.mode || "quiet_driver";
  fields.muted.textContent = data.voice?.muted ? "muted" : "live";
  fields.position.textContent = snap.current_position ? `P${snap.current_position}` : "--";
  fields.lap.textContent =
    snap.current_lap && snap.total_laps ? `${snap.current_lap}/${snap.total_laps}` : "--";
  fields.lapsLeft.textContent = snap.laps_left ?? "--";
  fields.lastLap.textContent = snap.last_lap_time || "--:--.---";
  fields.bestLap.textContent = snap.best_lap_time || "--:--.---";
  fields.averageLap.textContent = snap.average_lap_time || "--:--.---";
  fields.fuelLevel.textContent = fmt(snap.fuel_level, " L", 1);
  fields.fuelLaps.textContent = fmt(snap.fuel_laps_remaining, "", 1);
  fields.fuelMargin.textContent = fmt(snap.fuel_margin_laps, "", 1);
  fields.pit.textContent = snap.pit_recommendation || "No fuel data yet.";
  fields.speed.textContent = fmt(snap.speed_kph, " kph", 0);
  fields.rpm.textContent = fmt(snap.engine_rpm, "", 0);
  fields.gear.textContent = snap.current_gear ?? "--";
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
    const response = await fetch("/api/status");
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
