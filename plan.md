# GT7 Race Engineer Full Plan

## Summary
Build a local macOS GT7 race engineer that auto-discovers the PS5, reads GT7 telemetry through `gt-telem`, runs deterministic race-engineer logic locally, displays a web HUD, and uses a Discord voice bot as the main hands-free audio interface.

The Discord bot is the race radio: it listens to your headset in a private Discord voice channel and speaks proactive updates plus answers back through the same channel. Text chat remains only for testing, debugging, and fallback.

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
  - [x] Runs deterministic monitors for fuel, pit timing, laps, position, tire/car health, and connection health.
  - [x] Add richer pace and incident monitors for lockups, wheelspin, spins, and impact-like events.
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
  - [x] Live proactive position-alert playback confirmed through Discord.
  - [x] Live driver-audio receive, STT transcription, and spoken position Q&A confirmed.
- Web HUD:
  - [x] Browser dashboard for laptop, iPad, phone, or second monitor.
  - [x] Shows live telemetry, fuel strategy, lap history, alerts, and voice status.
  - [x] Shows timed race duration and time left for endurance debugging.
  - [ ] Add HUD settings for verbosity presets and voice mode.
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
  - [x] Tire temps, wheel speeds, suspension height, engine/oil/water data.
  - [x] Motion, rotation, angular velocity, tire radius, TCS/ASM, handbrake, rev-limit, and in-gear flags.
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
  - [x] Timed/endurance race updates: lap plus time remaining instead of “lap X of 0.”
  - [x] Timed/endurance countdown uses active racing time and stops while paused.
  - [x] Fuel: laps remaining, fuel margin, fuel critical.
  - [ ] Fuel-save target calls.
  - [x] Pit advice: “Box this lap,” “Fuel to the end is safe.”
  - [x] Tire/car health: tire temp imbalance, overheating, oil/water warnings.
  - [x] System status: telemetry connected/lost, packet stale.
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
  - [x] Add live STT confidence thresholds for `quiet_driver` mode.
- Supported questions:
  - [x] “How’s my fuel?”
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
- [x] Urgent/proactive calls do not require a question.
- [x] LLM adapter exists for natural phrasing, summaries, and flexible questions.
- [ ] Add live local/LAN LLM smoke tests and prompt regression coverage.
- [ ] Validate spoken fuel, pit, lap, tire, and update commands during live driving.
- [ ] Tune STT confidence and segmentation from more Discord headset samples.

## Discord Bot
- [x] Private server/channel setup with real credentials.
- Slash commands:
  - [x] `/join`
  - [x] `/leave`
  - [x] `/status`
  - [x] `/mode wake_phrase`
  - [x] `/mode quiet_driver`
  - [x] `/mute_engineer`
  - [x] `/unmute_engineer`
  - [x] `/radio_check`
- Bot behavior:
  - [x] Filters/monitors to the configured driver user.
  - [x] Pauses receive streams while TTS is playing to avoid self-transcription.
  - [ ] Verify bot ignores its own TTS output during live Discord use.
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
  - [x] Fuel laps remaining, fuel margin, pit recommendation.
  - [x] Tire temps and car health via API; compact car panel in HUD.
  - [x] Session phase, STT/TTS status, tire wear estimate, incident, and driving-style panels.
  - [x] Alert feed.
  - [x] Voice mode status.
  - [ ] Discord bot status in HUD.
  - [ ] Settings for verbosity presets.

## Current Live Validation
- [x] 2026-05-22: PS5 auto-discovered on the LAN.
- [x] 2026-05-22: GT7 on-track telemetry reached the service at roughly 60 Hz.
- [x] 2026-05-22: HUD/API showed live race phase, position, speed, fuel, tires, and alerts.
- [x] 2026-05-22: Discord bot joined the private voice channel and played `/radio_check`.
- [x] 2026-05-22: Proactive position alerts played through Discord voice without an LLM.
- [x] 2026-05-22: Driver headset audio incremented Discord receive packet counters.
- [x] 2026-05-22: `faster-whisper` `tiny.en` transcribed a spoken position question and the bot answered through Discord.
- [ ] Full short-race validation with lap summaries, final lap, and finish behavior.
- [ ] Endurance-style stint validation with fuel burn, pit advice, and fuel-margin calls.
- [ ] Live validation of every supported spoken command.

## Next Work Plan
- [ ] Run a full short race and capture/replay it to tune lap, position, and finish alerts.
- [ ] Run a longer fuel-burning stint and tune fuel-per-lap, fuel margin, and pit-call wording.
- [ ] Test all spoken command intents over Discord: fuel, pit, laps left, last lap, best lap, tires, update, quiet, and more fuel updates.
- [ ] Add HUD controls for preset, category verbosity, voice mode, mute, and STT status.
- [ ] Add Discord bridge status to the HUD, including connected channel, packet counter, last transcript, and last intent.
- [ ] Add post-session debrief output summarizing laps, incidents, fuel trend, tire trend, and notable alerts.
- [ ] Add local/LAN LLM smoke tests with the recommended 16 GB Mac model setup.
- [ ] Package a macOS-friendly launcher once live validation is stable.

## Implementation Phases
- [x] Project scaffold: Python package, Node Discord bridge, shared config, CLI, dev scripts.
- [x] Telemetry core: `gt-telem` adapter, normalized frame model, race state, replay/capture.
- [x] Race monitors: lap, position, fuel, pit advice, tire/car health, connection status.
- [x] Web HUD: FastAPI/WebSocket backend and live browser dashboard.
- [x] Discord bridge spike: bot joins voice, monitors driver audio, plays test TTS response.
- [x] Voice commands: VAD/STT endpoint, wake phrase mode, quiet-driver mode, Discord audio loop.
- [x] LLM adapter: OpenAI-compatible race-state Q&A and summaries.
- [x] Integration hardening: reconnects, stale telemetry edge cases, bot errors, config validation, logging.
- [x] Live GT7 smoke validation: PS5 discovery, stable packet rate, HUD/API on-track updates.
- [ ] Live GT7 validation: full short race, endurance-style race, replay comparison, alert tuning.

## Test Plan
- Unit tests:
  - [x] Telemetry normalization.
  - [x] Lap/laps-left logic.
  - [x] Position-change detection.
  - [x] Fuel burn and pit recommendation.
  - [x] Alert cooldowns and verbosity.
  - [x] Session phase, tire wear, incident, driving-style, STT transcript, and audio-status API behavior.
- Replay tests:
  - [x] Synthetic race sessions.
  - [ ] Captured GT7 sessions once available.
  - [x] Fuel-critical, lap-change, and position-change scenarios.
  - [ ] Connection-loss replay scenarios.
- Discord tests:
  - [ ] Join/leave/reconnect live test.
  - [x] Live join and radio-check playback smoke test in a real Discord channel.
  - [x] Config and Python client unit tests.
  - [x] Driver-user audio monitoring implementation.
  - [x] PCM-to-WAV audio segment unit test.
  - [x] Live driver audio receive/STT smoke test in a real Discord channel.
  - [x] Live spoken position-command round trip through Discord.
  - [ ] Live spoken fuel/pit/lap command round trips through Discord.
  - [ ] Bot ignores its own speech.
- LLM tests:
  - [ ] Fixed race-state questions.
  - [ ] Unsupported-data answers.
  - [ ] Timeout/fallback behavior.
- Live acceptance:
  - [x] PS5 auto-discovered.
  - [x] Telemetry packet rate stable.
  - [x] HUD updates live from GT7.
  - [x] Discord bot speaks proactive position updates.
  - [ ] Discord bot speaks proactive lap/fuel updates in a completed race stint.
  - [x] Driver can ask a position question hands-free.
  - [ ] Driver can ask fuel/pit/lap questions hands-free.

## Assumptions
- Main race audio path is Discord voice.
- You race with a headset connected through PS5/Discord.
- You usually drive quietly, so `quiet_driver` mode is useful, but `wake_phrase` remains available.
- The app is GPL-compatible because `gt-telem` appears GPL-licensed.
- Opponent gaps and nearby-car spotter calls are not promised unless GT7 exposes a reliable data source later.
- This plan is saved as `plan.md` at the repo root and updated as implementation progresses.
