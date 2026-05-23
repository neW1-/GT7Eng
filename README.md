# GT7 Race Engineer

Local Gran Turismo 7 race engineer for macOS. It auto-discovers the PS5 via `gt-telem`, maintains race state, serves a live web HUD, and exposes bridge endpoints for a Discord voice bot.

## Current MVP

- [x] Python race-engineer core with normalized telemetry frames.
- [x] Replay/capture JSONL format.
- [x] Deterministic lap, position, fuel, pit, tire, and car-health alerts.
- [x] FastAPI HUD/API scaffold.
- [x] CLI commands: `doctor`, `run`, `replay`, `capture`.
- [x] Discord bridge API endpoints and a Node sidecar under `bridge/discord`.
- [x] macOS `say` TTS endpoint for Discord playback.
- [x] Replay fixture and automated tests for the core race logic.
- [x] Optional Discord audio-to-STT path with deterministic command handling.
- [x] Optional Piper/radio-style TTS provider with `say` fallback.
- [x] Session phase, incident, tire-wear, and driving-style monitors.
- [x] Live PS5 auto-discovery, HUD, and on-track GT7 telemetry smoke test.
- [x] Live Discord voice join, radio-check playback, and proactive position-alert playback.
- [x] Live Discord driver-audio receive, `tiny.en` STT, and spoken position Q&A round trip.
- [x] Treat GT7 fuel as percent-based telemetry, not liters.
- [x] Pit advice separates “pit required eventually” from “box this lap” urgency.
- [x] Coalesce rapid position changes into one net alert before speaking.
- [x] Timed/endurance race mode avoids “lap X of 0” and supports time-remaining voice responses.
- [x] Timed/endurance countdown freezes while GT7 telemetry reports the session is paused.
- [x] Retry/new-session detection resets stale fuel history before the next race stint.
- [x] Spoken lap/best-lap alerts use completed-lap history instead of unstable raw packet best-lap data.
- [x] Voice debug HUD shows transcript, confidence, intent, and LLM repair status.
- [x] Optional LLM intent repair maps noisy voice transcripts to deterministic commands.
- [x] `quiet_driver_ai` conversational mode keeps strict commands first, then uses the local LLM for high-confidence free-form questions.
- [x] Deterministic fuel-burn answers for “fuel burn rate” and “fuel used last lap.”
- [x] LLM/STT/TTS calls run off the FastAPI event loop so slow local generation does not starve telemetry ingestion.

## Todo

- [x] Add Discord STT/audio input from the configured driver user.
- [x] Add optional local `faster-whisper` transcription.
- [x] Add Piper/radio-style TTS while keeping macOS `say` as fallback.
- [x] Add race lifecycle handling for loading/menu/paused/finished states.
- [x] Normalize richer telemetry fields for motion, tire radius, and driving aids.
- [x] Add lap delta, final-lap, tire-wear, incident, and driving-style monitors.
- [x] Add HUD and `doctor` status for STT, TTS, session phase, and Discord receive health.
- [x] Wire Discord received audio into STT/VAD instead of only monitoring driver audio packets.
- [x] Add wake-phrase detection for `wake_phrase` mode.
- [x] Add stricter command grammar and confidence thresholds for `quiet_driver` mode.
- [x] Add `quiet_driver_ai` mode for conversational local-LLM Q&A without a wake phrase.
- [x] Add live Discord end-to-end STT test with a private server, configured driver user, and headset.
- [x] Add live GT7 validation with PS5 auto-discovery, packet-rate monitoring, and on-track telemetry.
- [x] Update fuel/pit strategy wording so negative finish margin does not always mean “box this lap.”
- [x] Guard urgent fuel calls until the projection has enough clean lap samples, unless fuel is genuinely low.
- [x] Keep HUD best-lap timing tied to completed lap history once laps are recorded.
- [ ] Add full short-race/endurance validation, replay comparison, and alert tuning.
- [ ] Validate spoken fuel, pit, lap, tire, and update commands during an active stint.
- [ ] Tune Discord STT confidence, segment timing, and false-positive suppression from more headset samples.
- [ ] Add local/LAN OpenAI-compatible LLM smoke tests and model setup docs.
- [x] Add LLM intent repair for noisy Discord STT transcripts.
- [x] Throttle spoken telemetry-stale alerts and keep telemetry-connected alerts silent to avoid voice loops during packet flaps.
- [x] Add richer incident/coaching monitors for lockups, wheelspin, spins, and impact-like events.
- [ ] Add off-track detection if GT7 exposes a reliable signal.
- [ ] Add HUD controls for verbosity presets and voice mode.
- [ ] Add persistent session/debrief output beyond JSONL capture.
- [ ] Package a macOS-friendly launcher once the live path is stable.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Optional local voice input/output dependencies:

```bash
pip install -e ".[dev,voice]"
```

## Run

```bash
gt7eng doctor
gt7eng run --host 0.0.0.0 --port 8001
```

Open `http://localhost:8001` for the HUD. Live GT7 telemetry requires GT7 telemetry enabled, PS5 and Mac on the same LAN, and inbound UDP `33740` allowed by macOS firewall.

Fuel note: GT7 fuel is treated as percentage. `fuel_level=100.0` means a full tank, not 100 liters; fuel-per-lap is percentage points consumed per lap.

Fuel strategy note: the HUD separates current-stint range from finish margin:

- `Stint` is how many laps the current fuel load is projected to last.
- `To Finish` is the projected fuel margin versus the remaining race distance.
- A negative `To Finish` means a stop is required before the end, not necessarily this lap.
- `Box this lap` is reserved for genuinely urgent fuel range, currently when projected stint range is about one lap or less.

For example, `Stint 4.4` and `To Finish -4.6` means the current fuel can last about 4.4 laps but is 4.6 laps short of finishing. The recommendation should be `Pit required. Box within 3 laps.`, not `Box this lap.`

Position note: rapid position changes are coalesced before being shown/spoken. By default, the engineer waits `1.5s` for the position to settle, so a quick move from P13 to P10 becomes “Gained 3 places, now P10.” Tune with `GT7ENG_POSITION_COALESCE_SECONDS`.

Timed race note: GT7 reports `total_laps=0` for timed/endurance events. The engineer treats that as timed race mode and says `Lap X` instead of `Lap X of 0`. Set the event length with `GT7ENG_RACE_DURATION_MINUTES` so the engineer can compute time remaining from its race-session clock, for example:

```bash
GT7ENG_RACE_DURATION_MINUTES=30 gt7eng run --host 0.0.0.0 --port 8001
```

In timed race mode, the HUD Race card shows race duration and time left. “How many laps?” returns lap plus time remaining, and “how much time left?” returns the remaining race time. The timer only counts while the session phase is `racing`; it freezes while GT7 reports `paused`.
You can also set the duration at runtime by voice or typed chat, for example: “set race duration to 30 minutes.”

## Replay

```bash
gt7eng replay tests/fixtures/simple_race.jsonl
```

## Discord

The primary race audio path is Discord voice. The Node bridge joins a private voice channel, forwards recognized commands to the Python service, and plays the service responses back into Discord.

See `bridge/discord/README.md` after installing the bridge dependencies.

Current Discord status:

- [x] Slash commands and voice-channel join/leave/status controls.
- [x] Proactive engineer alert queue exposed to the bridge.
- [x] TTS job playback contract from Python to Discord bridge.
- [x] Configured driver audio receive monitoring without storing raw audio.
- [x] Opus decode to PCM and stream into Python STT/VAD via `/api/discord/audio`.
- [x] Transcribe spoken commands and route transcripts through the deterministic command parser.
- [x] Pause receive streams while bot TTS is playing.
- [ ] Verify bot ignores its own TTS during live voice use.

Discord setup status:

- [x] Create a private Discord server for race radio.
- [x] Create the Discord Developer Portal application and bot user.
- [x] Invite the bot with `bot` and `applications.commands` scopes.
- [x] Copy Discord IDs into `bridge/discord/.env`.
- [x] Register slash commands with `npm run register`.
- [x] Start the Discord bridge with `npm start`.
- [x] Run `/join`, `/radio_check`, and `/status`.
- [x] Confirm proactive position alerts are spoken through Discord.
- [x] Confirm driver speech increments `driver_audio_packets`.
- [x] Confirm a spoken position question works hands-free.
- [ ] Confirm spoken fuel/pit/lap questions work hands-free.

Live validation notes from 2026-05-22:

- PS5 was auto-discovered on the LAN and live GT7 telemetry reached roughly 60 Hz.
- HUD/API showed on-track telemetry, race phase, position, tires, fuel, and alerts.
- Discord bot joined the private voice channel after updating Discord voice dependencies and installing encryption support.
- `/radio_check` played through Discord, and proactive position-loss alerts were spoken by the bot.
- Driver headset audio incremented `driver_audio_packets`.
- `faster-whisper` `tiny.en` on CPU transcribed “What position am I?” and the deterministic `position` intent played a spoken answer.
- `GT7ENG_STT_MIN_CONFIDENCE=0.45` worked better than the default `0.55` for this Discord headset test.
- Timed/endurance race testing confirmed `total_laps=0` is handled as timed mode, the HUD shows duration/time left, and the countdown freezes while paused.

Live validation notes from 2026-05-23:

- `faster-whisper` `base.en` was downloaded, preloaded, and configured for local Discord STT testing on the 16 GB M4 Mac.
- Fuel strategy now resets stale fuel history when retry/new-session telemetry rewinds to lap 1 or fuel jumps back up.
- Fuel strategy now suppresses urgent “box this lap” calls when the projection is based on only one high-fuel sample.
- Lap alerts were confirmed in the alert feed and Discord voice job acknowledgements.
- Lap/best-lap logic now prefers completed-lap history, so spoken deltas and HUD best-lap data are not thrown off by unstable raw GT7 best-lap packets.

## Audio Configuration

STT is optional and off by default:

```bash
GT7ENG_STT_ENABLED=true
GT7ENG_STT_MODEL=base.en
GT7ENG_STT_DEVICE=auto
DISCORD_STT_ENABLED=true
```

Piper is optional. Without it, macOS `say` remains the fallback:

```bash
GT7ENG_TTS_ENGINE=auto
GT7ENG_PIPER_MODEL=/path/to/en_GB-alba-medium.onnx
GT7ENG_RADIO_EFFECTS=true
```

Voice modes:

- `quiet_driver`: no wake phrase; strict deterministic commands only. Unknown speech is ignored except for optional LLM intent repair.
- `quiet_driver_ai`: no wake phrase; strict deterministic commands and intent repair run first, then high-confidence unknown speech can use the configured local LLM for conversational race-state Q&A.
- `wake_phrase`: requires the configured wake phrase, then supports deterministic commands and LLM fallback.

Deterministic answers still own race math. Questions like “what’s my fuel burn rate?” and “how much fuel did I use last lap?” are answered from completed-lap telemetry in percent, not by the LLM. Free-form LLM answers receive only current race state plus request date/time context and must say unavailable for missing telemetry.

Discord driver requests are prioritized over pending alert playback. The bridge clears queued local audio and pauses voice-job polling while Python handles a driver utterance, and Python drops queued system connection alerts for Discord requests. LLM, STT, and TTS work runs in worker threads so slow local generation does not block telemetry ingestion.

Telemetry connection alerts are intentionally restrained: `Telemetry connected` stays visible in logs/HUD but is not spoken, and spoken `Telemetry stale` alerts are throttled to avoid stale/connected voice loops if packets briefly flap around the stale threshold.

## Suggested 16 GB Apple Silicon Setup

For a MacBook Air M4 with 16 GB RAM, `gemma-4-e4b-it-4bit` has tested better for live conversational Q&A than the earlier 9B Qwen setup because it responds faster while STT, TTS, Discord, HUD, and telemetry are all running. The LLM is used for intent repair, phrasing, and flexible Q&A; fuel, pit, lap, and alert logic stays deterministic.

Recommended starting point:

```bash
GT7ENG_LLM_BASE_URL=http://127.0.0.1:8000/v1
GT7ENG_LLM_MODEL=gemma-4-e4b-it-4bit
GT7ENG_LLM_API_KEY=your_omlx_key
GT7ENG_LLM_TIMEOUT=20
GT7ENG_LLM_MAX_TOKENS=80
GT7ENG_LLM_DISABLE_THINKING=true
GT7ENG_LLM_INTENT_REPAIR=true
GT7ENG_LLM_INTENT_REPAIR_MIN_CONFIDENCE=0.55
```

`Qwen3.5-9B-OptiQ-4bit` remains usable, but it was slower in live testing. Larger models can improve broad reasoning or richer summaries, but they are usually worse for driving if first-token latency climbs above a few seconds.

Keep STT reasonably light while Discord, the HUD, TTS, and telemetry are all running. On the current 16 GB M4 test machine, `base.en` is the next model to try for better headset transcription; drop back to `tiny.en` if latency becomes noticeable:

```bash
GT7ENG_STT_ENABLED=true
GT7ENG_STT_MODEL=base.en
GT7ENG_STT_DEVICE=cpu
GT7ENG_STT_MIN_CONFIDENCE=0.45
DISCORD_STT_ENABLED=true
```

If `gemma-4-e4b-it-4bit` still feels sluggish during live racing, lower `GT7ENG_LLM_MAX_TOKENS` before moving to a larger model. If STT accuracy is poor, try `base.en` before moving to larger Whisper models. Avoid 20B-class models for live race use on 16 GB unless STT is off or latency does not matter.

## Full Discord And Local Audio Setup Notes

Use this section when setting up the full hands-free race-radio path.

1. Create a Discord application in the Discord Developer Portal.
2. Open **Bot**, create or reset the bot token, and put it in `bridge/discord/.env` as `DISCORD_TOKEN`.
3. Open **OAuth2 > URL Generator** and select scopes `bot` and `applications.commands`.
4. Select bot permissions `View Channels`, `Connect`, `Speak`, and `Use Voice Activity`.
5. Invite the bot to your private server with the generated URL.
6. Enable Developer Mode in Discord and copy IDs for `DISCORD_CLIENT_ID`, `DISCORD_GUILD_ID`, `DISCORD_VOICE_CHANNEL_ID`, and `DISCORD_DRIVER_USER_ID`.

Bridge setup:

```bash
cd bridge/discord
npm install
cp .env.example .env
```

Minimum useful `bridge/discord/.env`:

```bash
DISCORD_TOKEN=your_bot_token
DISCORD_CLIENT_ID=your_application_id
DISCORD_GUILD_ID=your_server_id
DISCORD_VOICE_CHANNEL_ID=your_private_voice_channel_id
DISCORD_DRIVER_USER_ID=your_discord_user_id

PYTHON_SERVICE_URL=http://127.0.0.1:8001
DEFAULT_AUDIO_MODE=quiet_driver_ai
AUTO_JOIN_ON_READY=true
DISCORD_STT_ENABLED=false
```

Register slash commands once:

```bash
npm run register
```

For day-to-day use, start and stop the GT7 service plus Discord bridge from the repo root:

```bash
./start_gt7eng.sh
./stop_gt7eng.sh
```

The start script loads `.env`, starts the Python HUD/service on `8001`, checks the configured oMLX/OpenAI-compatible endpoint, and starts the Discord bridge. Logs and PID files are written to `.gt7eng-run/`. The stop script stops the Python service and Discord bridge only; it intentionally leaves oMLX running.

Manual start is still useful while debugging:

```bash
# Terminal 1
. .venv/bin/activate
gt7eng run --host 0.0.0.0 --port 8001

# Terminal 2
cd bridge/discord
npm start
```

Then run `/join`, `/radio_check`, and `/status` in Discord. `/status` should show Python reachable. Keep `DISCORD_STT_ENABLED=false` until radio-check playback and proactive alerts are audible; then enable STT and confirm `driver_audio_packets` increases when the configured driver speaks.

Next live tests:

- Complete a short race and verify lap-end spoken summaries, final-lap handling, and position changes.
- Run an endurance-style stint long enough to validate fuel burn, pit advice, and fuel-margin calls.
- Test spoken commands for fuel, pit, laps left, last lap, best lap, tires, and “give me an update.”
- Tune alert cooldowns and STT thresholds from real headset behavior.
- Add HUD controls for preset/verbosity and voice mode so fewer settings require env edits.

For PS5 headset use, join or transfer the Discord voice call to the PS5 and keep using the headset you already race with. The bot should sit in the same private voice channel. If you use Discord on the Mac instead, confirm the Mac microphone is receiving your voice.

Quick troubleshooting:

- PS5 not found: confirm same LAN, GT7 running, firewall allows UDP `33740`, or set `GT7ENG_PS_IP`.
- Bot joins but does not speak: confirm `PYTHON_SERVICE_URL`, run `/radio_check`, check Python logs, and rerun `npm install` so the current Discord voice/encryption dependencies are installed.
- Bot does not hear you: confirm `DISCORD_DRIVER_USER_ID`, `DISCORD_STT_ENABLED=true`, and that you are in the configured voice channel.
- STT does not work: confirm `GT7ENG_STT_ENABLED=true` and install with `pip install -e ".[dev,voice]"`.
- LLM answers are slow: use `gemma-4-e4b-it-4bit`, keep `GT7ENG_LLM_MAX_TOKENS` low, and confirm the Python service plus Discord bridge were restarted after changing `.env`.
