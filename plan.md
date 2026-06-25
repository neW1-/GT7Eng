# GT7 Race Engineer Full Plan

## Summary
Build a local macOS GT7 race engineer that auto-discovers the PS5, reads GT7 telemetry through `gt-telem`, runs deterministic race-engineer logic locally, displays a web HUD, and uses a Discord voice bot as the main hands-free audio interface.

The Discord bot is the race radio: it listens to your headset in a private Discord voice channel and speaks proactive updates plus answers back through the same channel. Text chat remains only for testing, debugging, and fallback.

The live voice path now supports short-turn conversational memory. Deterministic race answers store one structured fact for 60 seconds, so immediate follow-ups like “which lap was that?” or “why?” can reference the previous answer without making the LLM infer telemetry.

The rig display path now supports two BLE matrices: a primary gear/rev display and a second coaching display for driver assists, lap/fuel/tire-age summaries, tire pages, and compact alerts.

## Baruta-Inspired Improvement TODOs
- [x] Add Discord STT/audio input from the configured driver user.
- [x] Add optional local `faster-whisper` transcription.
- [x] Add Piper/radio-style TTS while keeping macOS `say` as fallback.
- [x] Add race lifecycle handling for loading/menu/paused/finished states.
- [x] Normalize richer telemetry fields for motion, tire radius, and driving aids.
- [x] Add lap delta, final-lap, tire-wear, incident, and driving-style monitors.
- [x] Add HUD and `doctor` status for STT, TTS, session phase, and Discord receive health.

## Core Architecture
- Python race-engineer service:
  - [x] Auto-discovers PS5 via `gt-telem`; manual IP is fallback.
  - [x] Receives GT7 UDP telemetry, normalizes it, and maintains race state.
  - [x] Live PS5 auto-discovery and on-track GT7 telemetry smoke test passed.
  - [x] Runs deterministic monitors for fuel, pit timing, laps, position, tire age, tire/car health, and connection health.
  - [x] Add richer pace and incident monitors for lockups, wheelspin, spins, and impact-like events.
  - [x] Maintains short, in-process conversational memory for one recent deterministic answer.
  - [x] Publishes snapshots and alert pages to primary and second BLE display managers without blocking telemetry.
  - [ ] Add off-track and corner-loss monitors if GT7 exposes reliable signals.
  - [x] Provides local HTTP/WebSocket APIs for HUD, Discord bridge, replay, and testing.
- Discord voice bridge:
  - [x] Node sidecar using `discord.js` + `@discordjs/voice`.
  - [x] Joins a configured private Discord voice channel.
  - [x] Live Discord voice join and radio-check playback confirmed.
  - [x] Monitors only the configured driver user’s audio stream.
  - [x] Decode Discord Opus audio to PCM and feed Python STT/VAD.
  - [x] Sends driver audio segments to Python, where transcripts/intents are handled.
  - [x] Plays proactive calls and answers back into Discord through the voice-job/TTS contract.
  - [x] Gives driver-requested answers priority over pending alert playback while a command is being handled.
  - [x] Live proactive position-alert playback confirmed through Discord.
  - [x] Live driver-audio receive, STT transcription, and spoken position Q&A confirmed.
- Web HUD:
  - [x] Browser dashboard for laptop, iPad, phone, or second monitor.
  - [x] Shows live telemetry, fuel strategy, lap history, alerts, and voice status.
  - [x] Shows timed race duration and time left for endurance debugging.
  - [x] Shows last transcript, confidence, intent, and LLM repair result for voice debugging.
  - [x] Add local-only HUD settings for preset, category verbosity, voice mode, mute, and STT status.
  - [x] Persist HUD settings changes back to `.env` while preserving comments/order and keeping secrets out of editable forms.
  - [x] Add local-only HUD controls for Discord bridge start/stop/restart and BLE pixel display start/stop/config.
  - [x] Add second BLE coaching display status, start/stop/config, and software preview.
  - [x] Includes typed chat only for test/debug use.

## Telemetry And Race State
- [x] Use `gt-telem` as the ingestion adapter, wrapped behind our own `TelemetrySource`.
- Normalize key GT7 fields:
  - [x] Speed, RPM, gear, throttle, brake, clutch.
  - [x] Current lap, total laps, laps left, last lap, best lap.
  - [x] Timed race mode when GT7 reports `total_laps=0`, with lap plus time remaining.
  - [x] Timed race clock freezes while GT7 telemetry reports the session is paused.
  - [x] Current position and total cars.
  - [x] Fuel level, fuel capacity, fuel used per lap, projected laps remaining.
  - [x] Treat GT7 fuel as percent-based telemetry, not liters.
  - [x] Reset stale fuel history immediately when retry/new-session telemetry rewinds to lap 1 or fuel jumps back up.
  - [x] Guard urgent fuel warnings until enough clean lap samples exist, unless fuel level is genuinely low.
  - [x] Split fuel range into current-stint range and finish margin for pit strategy.
  - [x] Tire temps, wheel speeds, suspension height, engine/oil/water data.
  - [x] Motion, rotation, angular velocity, tire radius, TCS/ASM, handbrake, rev-limit, and in-gear flags.
  - [x] Live wheelspin and lockup flags plus per-lap TC/ASM/WS/LCK event counts.
  - [x] Tire age in completed laps from race start, reset by likely pit service or tire replacement.
  - [x] Tire replacement is inferred from estimated worst tire wear dropping by at least 5 percentage points; tire compound and explicit tire-change state are not available from the current telemetry.
  - [x] Track ID/name once detected.
- Store session state:
  - [x] Rolling frame buffer.
  - [x] Lap history.
  - [x] Stint fuel trend.
  - [x] Alert history.
  - [x] Replay/capture files for offline testing.
  - [ ] Persistent post-session debrief files beyond raw JSONL capture.

## Spoken Updates
- Proactive Discord calls stay in scope:
  - [x] Position changes: “P3.” / “Lost one, now P4.”
  - [x] Coalesce rapid position changes into one net alert, e.g. “Gained 3 places, now P10.”
  - [x] Lap-end summaries: lap time, delta to best, laps left.
  - [x] Spoken lap alerts compare against completed-lap history, not unstable raw GT7 best-lap packet data.
  - [x] Timed/endurance race updates: lap plus time remaining instead of “lap X of 0.”
  - [x] Timed/endurance countdown uses active racing time and stops while paused.
  - [x] Fuel: stint laps remaining, finish margin, fuel critical.
  - [x] Tire age after each completed lap when tire verbosity is balanced or higher.
  - [x] Pit-service reset: “Pit service detected. Tire age reset.” when refuel or tire-replacement inference resets the stint.
  - [ ] Fuel-save target calls.
  - [x] Pit advice distinguishes “pit required eventually” from “box this lap” urgency.
  - [x] Driving-style coaching alerts use the completed lap's events, so stale cumulative wheelspin/lockup cannot mask current-lap TC/ASM behavior.
  - [x] Tire/car health: tire temp imbalance, overheating, oil/water warnings.
  - [x] System status: telemetry stale is spoken with cooldown; telemetry connected is logged/HUD-only to avoid voice loops.
  - [ ] PS5-not-found spoken setup guidance during live startup.
- Alert categories have verbosity levels:
  - [x] `off`, `critical`, `balanced`, `detailed`.
- Presets:
  - [x] `quick race`: fewer fuel calls, position/lap focus.
  - [x] `endurance`: fuel/pit/stint heavy.
  - [x] `practice`: pace/coaching heavy.
  - [x] `custom`: user-controlled category levels.

## Voice Interaction
- [x] Discord is the v1 primary voice route.
- Voice modes:
  - [x] `wake_phrase`: commands start with “Engineer” or a configured phrase in the command parser.
  - [x] Add wake-phrase detection from live Discord STT transcripts.
  - [x] `quiet_driver`: no wake phrase, but only strict race command grammar is accepted in the command parser.
  - [x] `quiet_driver_ai`: no wake phrase, strict commands first, then high-confidence unknown speech can use LLM Q&A.
  - [x] Add live STT confidence thresholds for `quiet_driver` mode.
- Supported questions:
  - [x] “How’s my fuel?”
  - [x] “What’s my fuel burn rate?”
  - [x] “How much fuel did I use last lap?”
  - [x] “Do I need to pit?”
  - [x] “How many laps left?”
  - [x] “How much time left?”
  - [x] “Set race duration to 30 minutes.”
  - [x] “What was my last lap?”
  - [x] “What’s my best lap?”
  - [x] “What position am I?”
  - [x] “How are the tires?”
  - [x] “Give me an update.”
  - [x] “Keep quiet.”
  - [x] “More fuel updates.”
- Supported short-turn follow-ups:
  - [x] “Which lap was that?”
  - [x] “What lap was that?”
  - [x] “When was that?”
  - [x] “How much was that?”
  - [x] “What was that again?”
  - [x] “How many laps is that based on?”
  - [x] “Was that faster than my best?”
  - [x] “How many cars are in the race?”
  - [x] “Why?” with recent context for the LLM when deterministic handling cannot answer directly.
- [x] Urgent/proactive calls do not require a question.
- [x] LLM adapter exists for natural phrasing, summaries, and flexible questions.
- [x] LLM intent-repair path maps noisy transcripts to known deterministic commands.
- [x] Free-form LLM answers receive current race state plus request date/time context.
- [x] Short-turn memory stores structured deterministic facts for 60 seconds and resolves immediate follow-ups before LLM fallback.
- [x] Recent memory is included in free-form LLM payloads after deterministic follow-up resolution fails.
- [x] LLM/STT/TTS calls run off the FastAPI event loop so slow local generation does not block telemetry ingestion.
- [ ] Add live local/LAN LLM smoke tests and prompt regression coverage.
- [x] Validate spoken fuel, pit, lap, tire, and update commands during live driving.
- [ ] Tune STT confidence and segmentation from more Discord headset samples.

## Discord Bot
- [x] Private server/channel setup with real credentials.
- Slash commands:
  - [x] `/join`
  - [x] `/leave`
  - [x] `/status`
  - [x] `/mode wake_phrase`
  - [x] `/mode quiet_driver`
  - [x] `/mode quiet_driver_ai`
  - [x] `/mute_engineer`
  - [x] `/unmute_engineer`
  - [x] `/radio_check`
- Bot behavior:
  - [x] Filters/monitors to the configured driver user.
  - [x] Pauses receive streams while TTS is playing to avoid self-transcription.
  - [x] Verify bot ignores its own TTS output during live Discord use.
  - [x] Reconnects on voice disconnect.
  - [x] Logs recognized intent, confidence, and response text on the Python side.
  - [x] Does not store raw audio by default.

## LLM Integration
- [x] Default adapter: OpenAI-compatible HTTP endpoint.
- [x] Works with Ollama `/v1`, LM Studio/MLX-style servers, and LAN-hosted compatible servers by URL/model config.
- Configurable:
  - [x] Base URL.
  - [x] Model.
  - [x] API key optional.
  - [x] Timeout.
  - [x] Max response length.
- LLM guardrails:
  - [x] Must answer from current race state.
  - [x] Must say unavailable for unsupported data like opponent gaps or nearby-car spotter info.
  - [x] Must not invent telemetry.
  - [x] Request context includes current date/time for general questions.
  - [x] Recent conversational memory is limited to one structured fact and expires after 60 seconds.
  - [x] Deterministic follow-up parsing runs before LLM fallback.
  - [x] `gemma-4-e4b-it-4bit` is the recommended live local model on the 16 GB M4 test setup.
  - [ ] Add automated LLM regression tests with a stub OpenAI-compatible server.

## HUD And CLI
- CLI:
  - [x] `gt7eng doctor`: checks installed dependencies and optional PS5 discovery.
  - [x] Expand `doctor` to check UDP port bind, Discord config, LLM config, TTS, and STT.
  - [ ] Add live LLM endpoint smoke checks to `doctor`.
  - [x] `gt7eng run`: starts full service.
  - [x] `gt7eng replay <file>`: replays captured telemetry.
  - [x] `gt7eng capture`: records a session.
- HUD:
  - [x] Live connection status and packet rate.
  - [x] Current lap, laps left, position, last/best lap.
  - [x] Fuel stint range, finish margin, and pit recommendation.
  - [x] Tire temps and car health via API; compact car panel in HUD.
  - [x] Session phase, STT/TTS status, tire wear estimate, incident, and driving-style panels.
  - [x] Alert feed.
  - [x] Voice mode status.
  - [x] Discord bridge process and heartbeat status in HUD.
  - [x] Settings for preset, category verbosity, voice mode, mute, STT, and primary/second pixel display configuration.
  - [x] Local-only write guard so LAN/iPad/phone views remain read-only while localhost can mutate runtime settings.

## BLE Pixel Gear Indicator
- [x] Add optional `pixel-display` dependency extra for `pypixelcolor` so BLE packages are not required for normal GT7Eng installs.
- [x] Add centralized `.env` config for enabling/disabling the display, BLE address, update rate, brightness, orientation, rev bar position, shift flash behavior, color themes, custom hex colors, and optional RPM fallback values.
- [x] Configure the local `.env` to connect to `LED_BLE_F16C3591` using CoreBluetooth UUID `7D157B3A-F9F5-06B7-DEC5-A962DAAB7E72`.
- [x] Keep a persistent `pypixelcolor.AsyncClient` BLE connection open while GT7Eng is running.
- [x] Render a large gear indicator with configurable top/bottom rev bar, defaulting to bottom.
- [x] Use BLE-reported render dimensions by default, with configurable width/height fallback or explicit override for unusual panels.
- [x] Add configurable pixel gear layouts for current gear only or current gear with GT7's suggested gear.
- [x] Support `simdt_blue`, `warm_amber`, `race_gyr`, and `custom` color themes so night stints can use amber/orange/red instead of blue.
- [x] Normalize GT7 `min_alert_rpm` and `max_alert_rpm` into telemetry snapshots and use `max_alert_rpm` for the default wide rev-bar sweep before falling back to configured RPM values.
- [x] Flash the gear at shift point when GT7 reports `rev_limit` by default, with optional percent-trigger mode still configurable.
- [x] Add rev-bar tuning config for wide/alert-window scale, start percent, and shift trigger mode after rig feedback showed the alert-window bar was too compressed.
- [x] Add optional `GT7ENG_PIXEL_DISPLAY_FUEL_ENABLED` fuel bar that renders only when GT7 fuel drops below 100%, so fuel-free races keep the display clean.
- [x] Render the fuel bar as a 1-pixel edge indicator opposite the rev bar, preserving the existing gear layout and using otherwise free edge pixels.
- [x] Map fuel bar width to remaining fuel percentage and use alert-aligned color zones: safe above 50%, warn at 50%, danger at 20%, critical at 10%.
- [x] Add fuel color defaults for `simdt_blue`, `warm_amber`, and `race_gyr`, plus custom fuel hex overrides for exact tuning.
- [x] Show dim `--` when telemetry is stale, idle, loading, paused, or not racing.
- [x] Cap display sends at 10 Hz by default, dedupe identical frames, and use latest-snapshot rendering to avoid BLE backlog.
- [x] Reconnect with capped backoff if BLE drops while keeping telemetry, HUD, and Discord running.
- [x] Send a black frame on shutdown instead of calling `pypixelcolor.clear()`, because the upstream clear command erases stored device content.
- [x] Add pixel display state to `/api/status`, the HUD topbar, and `gt7eng doctor`.
- [x] Add `gt7eng pixel-preview <output.png>` for hardware-free layout, color-theme, rev-bar, suggested-gear, and fuel-bar verification.
- [x] Add HUD pixel display controls for enable/disable, BLE address, brightness, dim brightness, orientation, update Hz, size, layout, rev bar, shift flash, theme, custom colors, fuel bar, and RPM fallback settings.
- [x] Add a HUD pixel preview image endpoint using the software renderer so layout/theme changes can be checked without BLE hardware.
- [ ] Live-test the BLE display on the rig and tune brightness/theme/update rate after real driving feedback.
- [ ] Live-test fuel bar readability on the 32x32 BLE display during fuel-enabled races.
- [ ] Tune fuel bar theme colors after night-stint and daylight rig feedback.
- [ ] Consider configurable fuel warning thresholds if the alert-aligned 50/20/10 zones feel too aggressive or too subtle.
- [ ] Consider adding fuel bar state to the HUD topbar tooltip/details if `/api/status.pixel_display.fuel` is not enough during debugging.

## Second BLE Coaching Display
- [x] Add optional second `pypixelcolor` BLE output with independent address, update Hz, brightness, orientation, size source, alert hold, flash hold, status, and start/stop controls.
- [x] Keep the second display color theme synchronized with the primary pixel display theme, including HUD-driven changes.
- [x] Render a default coaching page with `TC`, `ASM`, `WS`, and `LCK`; TC/ASM get the largest screen space and support counts beyond `99`.
- [x] Flash live interventions and briefly hold flashes so short TCS/ASM/wheelspin/lockup events are visible at BLE refresh rates.
- [x] Queue alert override pages instead of replacing pages immediately, so lap, fuel, and driving coaching pages can all be seen after lap completion.
- [x] Render lap-completion pages with lap number/total, lap time, and delta versus the previous lap with theme-green faster/equal deltas and red slower deltas.
- [x] Render lap fuel pages after each completed lap with remaining fuel and fuel used on that lap; fuel-used color compares against the previous lap and omits the unsupported `%` glyph.
- [x] Render tire-age pages after lap/fuel pages with completed-lap tire age plus tire temperature colors.
- [x] Render tire alert pages as `FL FR / RL RR` blocks colored by current tire temperature.
- [x] Render compact position, fuel/pit, incident, and telemetry-stale pages while intentionally ignoring oil/water car-health pages for this display.
- [x] Add `/api/status`, `/api/control/second-display`, start/stop, and preview coverage plus HUD controls and `.env` persistence.
- [ ] Live-test the second BLE display on the rig and tune alert hold, flash hold, brightness, and layout after real driving feedback.

## Home Assistant Wind Simulation
- [x] Add optional wind output as a sibling manager to the BLE pixel display manager.
- [x] Use `RaceSnapshot.speed_kph` as the v1 control signal, gated to connected `racing` sessions only.
- [x] Map speed to Home Assistant level `0..14` for `number.zhimi_cpa4_cee4_favorite_level`.
- [x] Split wind off level from minimum active level so stopped telemetry can use `0` while moving airflow starts at `2`.
- [x] Use a curved 280 kph speed map with a 10 kph deadband, 1 second smoothing, and 1-level hysteresis.
- [x] Cap Home Assistant command attempts at 2 Hz instead of following GT7's roughly 60 Hz telemetry rate.
- [x] Call Home Assistant's REST service endpoint `POST /api/services/number/set_value` instead of writing `/api/states`.
- [x] Keep the Home Assistant token in `.env` only and exclude it from HUD/status payloads.
- [x] Add HUD topbar status plus local-only wind start/stop/config controls for non-secret settings.
- [x] Add `gt7eng doctor` wind readiness output without printing the token.
- [ ] Live-test `number.zhimi_cpa4_cee4_favorite_level` on the rig and confirm level `0` is acceptable as the POC idle/off level.
- [ ] Tune the curve, deadband, smoothing, and max speed after real fan ramp behavior is observed.
- [ ] Consider a separate Home Assistant power-off entity or service if level `0` still produces too much airflow.
- [ ] Consider v2 throttle, braking, or acceleration effects only after speed-only feedback is validated.

## Current Live Validation
- [x] 2026-05-22: PS5 auto-discovered on the LAN.
- [x] 2026-05-22: GT7 on-track telemetry reached the service at roughly 60 Hz.
- [x] 2026-05-22: HUD/API showed live race phase, position, speed, fuel, tires, and alerts.
- [x] 2026-05-22: Discord bot joined the private voice channel and played `/radio_check`.
- [x] 2026-05-22: Proactive position alerts played through Discord voice without an LLM.
- [x] 2026-05-22: Driver headset audio incremented Discord receive packet counters.
- [x] 2026-05-22: `faster-whisper` `tiny.en` transcribed a spoken position question and the bot answered through Discord.
- [x] 2026-05-23: `faster-whisper` `base.en` was downloaded, preloaded, and configured for live Discord STT testing.
- [x] 2026-05-23: Retry/new-session fuel reset and unstable-projection fuel guard were implemented for rapid retry testing.
- [x] 2026-05-23: Lap alerts were confirmed in the alert feed and Discord bridge acknowledgements.
- [x] 2026-05-23: Lap/best-lap alerts were fixed to use completed-lap history for spoken deltas and HUD best-lap consistency.
- [x] 2026-05-23: `quiet_driver_ai` was added for conversational local-LLM Q&A without a wake phrase.
- [x] 2026-05-23: Deterministic fuel-burn and last-lap fuel-used questions were added.
- [x] 2026-05-23: `gemma-4-e4b-it-4bit` tested better than the earlier Qwen 9B setup for live response latency.
- [x] 2026-05-23: Slow LLM/STT/TTS work was moved off the FastAPI event loop to prevent false telemetry-stale flaps.
- [x] 2026-05-23: Spoken telemetry connection alerts were throttled/silenced to stop stale/connected voice loops.
- [x] 2026-05-24: Short-turn follow-up memory worked in initial live tests for recent deterministic answers.
- [x] 2026-05-24: Follow-up context is now passed to the local LLM for conversational explanations after deterministic handling fails.
- [x] 2026-05-28: Full short-race validation covered lap summaries, final-lap handling, and finish behavior acceptably for now.
- [x] 2026-05-28: Endurance-style stint validation covered fuel burn, pit advice, and fuel-margin calls acceptably for now.
- [x] 2026-05-28: Spoken Discord commands for fuel, pit, lap, tire, update, quiet, and more fuel updates worked acceptably for now.
- [x] 2026-05-28: Discord self-TTS suppression was confirmed in live voice use.
- [x] 2026-05-28: Local-only HUD control plane was implemented and smoke-tested on localhost, including `.env` persistence, Discord bridge status/control, and pixel display config/preview.

## Next Work Plan
- [ ] Capture/replay completed GT7 sessions to compare live behavior and tune lap, position, fuel, pit, and finish alerts.
- [ ] Add post-session debrief output summarizing laps, incidents, fuel trend, tire trend, and notable alerts.
- [ ] Add local/LAN LLM smoke tests with the recommended 16 GB Mac model setup.
- [ ] Add live LLM endpoint smoke checks to `gt7eng doctor`.
- [ ] Live-test HUD Discord bridge controls during real voice use and tune any restart/status edge cases.
- [ ] Live-test HUD pixel display controls on BLE hardware and tune display defaults from rig feedback.
- [ ] Package a macOS-friendly launcher once live validation is stable.

## Implementation Phases
- [x] Project scaffold: Python package, Node Discord bridge, shared config, CLI, dev scripts.
- [x] Telemetry core: `gt-telem` adapter, normalized frame model, race state, replay/capture.
- [x] Race monitors: lap, position, fuel, pit advice, tire/car health, connection status.
- [x] Web HUD: FastAPI/WebSocket backend and live browser dashboard.
- [x] Discord bridge spike: bot joins voice, monitors driver audio, plays test TTS response.
- [x] Voice commands: VAD/STT endpoint, wake phrase mode, quiet-driver mode, Discord audio loop.
- [x] LLM adapter: OpenAI-compatible race-state Q&A and summaries.
- [x] Conversational mode hardening: response priority, non-blocking LLM calls, request date/time context, and connection-alert throttling.
- [x] Short-turn memory: structured deterministic facts, 60-second expiry, deterministic follow-ups, and LLM context handoff.
- [x] Integration hardening: reconnects, stale telemetry edge cases, bot errors, config validation, logging.
- [x] Live GT7 smoke validation: PS5 discovery, stable packet rate, HUD/API on-track updates.
- [x] Live GT7 validation: full short race, endurance-style race, supported spoken commands, and self-TTS suppression.
- [x] HUD control plane: local-only settings writes, `.env` persistence, STT reload, Discord bridge process control/status, pixel display controls, and software preview.
- [ ] Replay/tuning follow-up: captured GT7 replay comparison and alert tuning.

## Test Plan
- Unit tests:
  - [x] Telemetry normalization.
  - [x] Lap/laps-left logic.
  - [x] Position-change detection.
  - [x] Fuel burn and pit recommendation.
  - [x] Pit urgency rules for “pit required,” “box within 1 lap,” and “box this lap.”
  - [x] Retry/new-session fuel-history reset and unstable fuel-projection suppression.
  - [x] Tire-age incrementing, refuel/tire-wear reset detection, and tire-age voice/display alerts.
  - [x] Spoken lap delta logic against completed-lap history.
  - [x] Per-lap driving coaching alerts do not reuse stale cumulative wheelspin/lockup counts.
  - [x] Short-turn memory follow-ups for best lap, last lap, fuel burn, last-lap fuel, position, expiry, and LLM context payloads.
  - [x] Alert cooldowns and verbosity.
  - [x] Session phase, tire wear, incident, driving-style, STT transcript, and audio-status API behavior.
  - [x] `.env` writer preserves comments/order, updates known keys, appends missing keys, and writes atomically.
  - [x] Local-only control guard allows loopback clients and rejects LAN clients.
  - [x] HUD control endpoints persist settings and update runtime config for preset, verbosity, voice mode, mute, STT, and primary/second pixel display settings.
  - [x] Discord bridge process manager handles missing setup, stale PID files, start/stop/restart paths, and heartbeat status.
  - [x] Pixel display preview endpoints return rendered PNGs without BLE hardware.
  - [x] Second display renderer covers TC/ASM/WS/LCK counts, flashing, alert queueing, lap/fuel/tire-age pages, tire pages, and Night Vision delta colors.
- Replay tests:
  - [x] Synthetic race sessions.
  - [ ] Captured GT7 sessions once available.
  - [x] Fuel-critical, lap-change, and position-change scenarios.
  - [ ] Connection-loss replay scenarios.
- Discord tests:
  - [ ] Join/leave/reconnect live test.
  - [x] Live join and radio-check playback smoke test in a real Discord channel.
  - [x] Config and Python client unit tests.
  - [x] Bridge heartbeat payload unit test.
  - [x] Driver-user audio monitoring implementation.
  - [x] PCM-to-WAV audio segment unit test.
  - [x] Live driver audio receive/STT smoke test in a real Discord channel.
  - [x] Live spoken position-command round trip through Discord.
  - [x] Live spoken fuel/pit/lap command round trips through Discord.
  - [x] Bot ignores its own speech.
- LLM tests:
  - [x] Request-context payload includes current date/time for free-form questions.
  - [x] Conversation-context payload includes recent short-turn memory when available.
  - [ ] Fixed race-state questions.
  - [ ] Unsupported-data answers.
  - [ ] Timeout/fallback behavior.
- Live acceptance:
  - [x] PS5 auto-discovered.
  - [x] Telemetry packet rate stable.
  - [x] HUD updates live from GT7.
  - [x] Discord bot speaks proactive position updates.
  - [x] Discord bot speaks proactive lap/fuel updates in a completed race stint.
  - [x] Driver can ask a position question hands-free.
  - [x] Driver can ask fuel/pit/lap questions hands-free.

## Assumptions
- Main race audio path is Discord voice.
- You race with a headset connected through PS5/Discord.
- You usually drive quietly, so `quiet_driver` mode is useful, but `wake_phrase` remains available.
- The app is GPL-compatible because `gt-telem` appears GPL-licensed.
- Opponent gaps and nearby-car spotter calls are not promised unless GT7 exposes a reliable data source later.
- This plan is saved as `plan.md` at the repo root and updated as implementation progresses.
