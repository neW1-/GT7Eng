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
  - [x] Runs deterministic monitors for fuel, pit timing, laps, position, tire/car health, and connection health.
  - [x] Add richer pace and incident monitors for lockups, wheelspin, spins, and impact-like events.
  - [ ] Add off-track and corner-loss monitors if GT7 exposes reliable signals.
  - [x] Provides local HTTP/WebSocket APIs for HUD, Discord bridge, replay, and testing.
- Discord voice bridge:
  - [x] Node sidecar using `discord.js` + `@discordjs/voice`.
  - [x] Joins a configured private Discord voice channel.
  - [x] Monitors only the configured driver user’s audio stream.
  - [x] Decode Discord Opus audio to PCM and feed Python STT/VAD.
  - [x] Sends driver audio segments to Python, where transcripts/intents are handled.
  - [x] Plays proactive calls and answers back into Discord through the voice-job/TTS contract.
- Web HUD:
  - [x] Browser dashboard for laptop, iPad, phone, or second monitor.
  - [x] Shows live telemetry, fuel strategy, lap history, alerts, and voice status.
  - [ ] Add HUD settings for verbosity presets and voice mode.
  - [x] Includes typed chat only for test/debug use.

## Telemetry And Race State
- [x] Use `gt-telem` as the ingestion adapter, wrapped behind our own `TelemetrySource`.
- Normalize key GT7 fields:
  - [x] Speed, RPM, gear, throttle, brake, clutch.
  - [x] Current lap, total laps, laps left, last lap, best lap.
  - [x] Current position and total cars.
  - [x] Fuel level, fuel capacity, fuel used per lap, projected laps remaining.
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
  - [x] Lap-end summaries: lap time, delta to best, laps left.
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

## Discord Bot
- [ ] Private server/channel setup with real credentials.
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

## Implementation Phases
- [x] Project scaffold: Python package, Node Discord bridge, shared config, CLI, dev scripts.
- [x] Telemetry core: `gt-telem` adapter, normalized frame model, race state, replay/capture.
- [x] Race monitors: lap, position, fuel, pit advice, tire/car health, connection status.
- [x] Web HUD: FastAPI/WebSocket backend and live browser dashboard.
- [x] Discord bridge spike: bot joins voice, monitors driver audio, plays test TTS response.
- [x] Voice commands: VAD/STT endpoint, wake phrase mode, quiet-driver mode, Discord audio loop.
- [x] LLM adapter: OpenAI-compatible race-state Q&A and summaries.
- [x] Integration hardening: reconnects, stale telemetry edge cases, bot errors, config validation, logging.
- [ ] Live GT7 validation: short race, endurance-style race, replay comparison, alert tuning.

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
  - [x] Config and Python client unit tests.
  - [x] Driver-user audio monitoring implementation.
  - [x] PCM-to-WAV audio segment unit test.
  - [ ] Audio receive/playback smoke test in a real Discord channel.
  - [ ] Bot ignores its own speech.
- LLM tests:
  - [ ] Fixed race-state questions.
  - [ ] Unsupported-data answers.
  - [ ] Timeout/fallback behavior.
- Live acceptance:
  - [ ] PS5 auto-discovered.
  - [ ] Telemetry packet rate stable.
  - [ ] HUD updates live from GT7.
  - [ ] Discord bot speaks proactive lap/fuel/position updates.
  - [ ] Driver can ask fuel/pit/lap questions hands-free.

## Assumptions
- Main race audio path is Discord voice.
- You race with a headset connected through PS5/Discord.
- You usually drive quietly, so `quiet_driver` mode is useful, but `wake_phrase` remains available.
- The app is GPL-compatible because `gt-telem` appears GPL-licensed.
- Opponent gaps and nearby-car spotter calls are not promised unless GT7 exposes a reliable data source later.
- This plan is saved as `plan.md` at the repo root and updated as implementation progresses.
