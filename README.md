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

## Suggested 16 GB Apple Silicon Setup

For a MacBook Air M4 with 16 GB RAM, try an MLX/oMLX 4-bit 8B model first. The LLM is only used for phrasing and flexible Q&A; fuel, pit, lap, and alert logic stays deterministic.

Recommended starting point:

```bash
GT7ENG_LLM_BASE_URL=http://127.0.0.1:8000/v1
GT7ENG_LLM_MODEL=mlx-community/Qwen3-8B-4bit
GT7ENG_LLM_API_KEY=local
GT7ENG_LLM_TIMEOUT=4
GT7ENG_LLM_MAX_TOKENS=80
```

Keep STT light while Discord, the HUD, TTS, and telemetry are all running:

```bash
GT7ENG_STT_ENABLED=true
GT7ENG_STT_MODEL=tiny.en
GT7ENG_STT_DEVICE=cpu
DISCORD_STT_ENABLED=true
```

If the 8B model feels sluggish during live racing, try a 4B MLX model. If STT accuracy is poor, try `base.en` before moving to larger Whisper models. Avoid 20B-class models for live race use on 16 GB unless STT is off or latency does not matter.

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

PYTHON_SERVICE_URL=http://127.0.0.1:8765
DEFAULT_AUDIO_MODE=quiet_driver
AUTO_JOIN_ON_READY=true
DISCORD_STT_ENABLED=true
```

Register slash commands once:

```bash
npm run register
```

Start order for a live test:

```bash
# Terminal 1
. .venv/bin/activate
gt7eng run --host 0.0.0.0 --port 8765

# Terminal 2
cd bridge/discord
npm start
```

Then run `/join`, `/radio_check`, and `/status` in Discord. `/status` should show Python reachable, and `driver_audio_packets` should increase when the configured driver speaks.

For PS5 headset use, join or transfer the Discord voice call to the PS5 and keep using the headset you already race with. The bot should sit in the same private voice channel. If you use Discord on the Mac instead, confirm the Mac microphone is receiving your voice.

Quick troubleshooting:

- PS5 not found: confirm same LAN, GT7 running, firewall allows UDP `33740`, or set `GT7ENG_PS_IP`.
- Bot joins but does not speak: confirm `PYTHON_SERVICE_URL`, run `/radio_check`, and check Python logs.
- Bot does not hear you: confirm `DISCORD_DRIVER_USER_ID`, `DISCORD_STT_ENABLED=true`, and that you are in the configured voice channel.
- STT does not work: confirm `GT7ENG_STT_ENABLED=true` and install with `pip install -e ".[dev,voice]"`.
- LLM answers are slow: try a 4B MLX model or lower `GT7ENG_LLM_MAX_TOKENS`.
