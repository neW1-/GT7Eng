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
- [ ] Add live Discord end-to-end test with a private server, configured driver user, and headset.
- [ ] Add live GT7 validation with PS5 auto-discovery, packet-rate monitoring, and short-race telemetry.
- [ ] Add local/LAN OpenAI-compatible LLM smoke tests and model setup docs.
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
gt7eng run --host 0.0.0.0 --port 8765
```

Open `http://localhost:8765` for the HUD. Live GT7 telemetry requires GT7 telemetry enabled, PS5 and Mac on the same LAN, and inbound UDP `33740` allowed by macOS firewall.

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

## Audio Configuration

STT is optional and off by default:

```bash
GT7ENG_STT_ENABLED=true
GT7ENG_STT_MODEL=tiny.en
GT7ENG_STT_DEVICE=auto
DISCORD_STT_ENABLED=true
```

Piper is optional. Without it, macOS `say` remains the fallback:

```bash
GT7ENG_TTS_ENGINE=auto
GT7ENG_PIPER_MODEL=/path/to/en_GB-alba-medium.onnx
GT7ENG_RADIO_EFFECTS=true
```

`quiet_driver` mode ignores unknown transcripts instead of sending them to the LLM. `wake_phrase` mode can fall back to the configured LLM after the wake phrase.
