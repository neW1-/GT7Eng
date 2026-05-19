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

## Todo

- [ ] Wire Discord received audio into STT/VAD instead of only monitoring driver audio packets.
- [ ] Add wake-phrase detection for `wake_phrase` mode.
- [ ] Add stricter command grammar and confidence thresholds for `quiet_driver` mode.
- [ ] Add live Discord end-to-end test with a private server, configured driver user, and headset.
- [ ] Add live GT7 validation with PS5 auto-discovery, packet-rate monitoring, and short-race telemetry.
- [ ] Add local/LAN OpenAI-compatible LLM smoke tests and model setup docs.
- [ ] Add richer incident/coaching monitors for lockups, wheelspin, spins, and off-track events.
- [ ] Add HUD controls for verbosity presets and voice mode.
- [ ] Add persistent session/debrief output beyond JSONL capture.
- [ ] Package a macOS-friendly launcher once the live path is stable.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
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
- [ ] Opus decode to PCM and stream into STT/VAD.
- [ ] Transcribe spoken commands and post transcripts to `/api/discord/transcript`.
- [ ] Verify bot ignores its own TTS during live voice use.
