# Discord Voice Bridge Sidecar

Node sidecar for joining a configured Discord voice channel and playing GT7Eng race engineer audio. It uses `discord.js` for slash commands and `@discordjs/voice` for voice playback.

## Commands

- `/join` connects the bot to the configured or caller voice channel.
- `/leave` disconnects from voice.
- `/status` reports voice state, mute state, mode, and Python service health.
- `/mode` sets bridge mode: `wake_phrase`, `quiet_driver`, `quiet_driver_ai`, or `silent`.
- `/mute_engineer` mutes Python/TTS engineer playback.
- `/unmute_engineer` unmutes engineer playback.
- `/radio_check` plays a short generated test tone in voice.

## Setup

```bash
cd bridge/discord
npm install
cp .env.example .env
```

Fill in:

- `DISCORD_TOKEN`: bot token.
- `DISCORD_CLIENT_ID`: Discord application client ID.
- `DISCORD_GUILD_ID`: guild ID for fast guild command registration.
- `DISCORD_VOICE_CHANNEL_ID`: preferred voice channel ID. `/join` can also use the command caller's voice channel.
- `DISCORD_DRIVER_USER_ID`: the only user whose audio is monitored.
- `PYTHON_SERVICE_URL`: Python service base URL.
- `PYTHON_SERVICE_TOKEN`: optional bearer token sent to the Python service.
- `AUTO_JOIN_ON_READY`: set to `true` to join `DISCORD_VOICE_CHANNEL_ID` as soon as Discord is ready.
- `DISCORD_STT_ENABLED`: set to `true` to decode the configured driver's Discord audio and send WAV speech segments to Python.
- `RECEIVE_WATCHDOG_MS`: logs a warning when no driver audio has been observed for this long.

Register slash commands:

```bash
npm run register
```

Run the bridge:

```bash
npm start
```

## Python Service Contract

The MVP polls and posts to these JSON endpoints. Missing endpoints are handled as service errors in `/status`; playback continues for local `/radio_check`.

### `GET /discord/voice/jobs?limit=1`

Expected response:

```json
{
  "jobs": [
    {
      "id": "job-123",
      "kind": "tts",
      "text": "Box this lap.",
      "audio_url": "http://127.0.0.1:8001/audio/job-123.wav"
    }
  ]
}
```

The bridge plays the first job with one of `audio_url`, `audio_file`, or `text`.

### `POST /discord/voice/jobs/{id}/ack`

Request body:

```json
{ "status": "played" }
```

### `POST /discord/tts`

Used when a job contains `text` but no audio. Expected response:

```json
{ "audio_url": "http://127.0.0.1:8001/audio/generated.wav" }
```

### `GET /health`

Used by `/status`. Any 2xx response is considered healthy.

### `POST /discord/engineer/mute`

Request body:

```json
{ "muted": true }
```

### `POST /discord/mode`

Request body:

```json
{ "mode": "quiet_driver_ai" }
```

## Audio Receive

The bridge subscribes to the configured driver's Opus receive stream and exposes packet counters in `/status`. When `DISCORD_STT_ENABLED=true`, it decodes only that user's Opus stream to PCM, wraps each speech segment as WAV, and posts it to:

```http
POST /api/discord/audio
```

The Python service owns transcription and command handling. In `quiet_driver` mode, unknown speech can use the configured LLM only as a structured intent-repair layer that maps noisy transcripts to known deterministic commands. In `quiet_driver_ai` mode, strict commands and intent repair still run first, then high-confidence unknown speech can fall through to the configured LLM for race-state Q&A. Wake-phrase mode can also fall back to the configured LLM after the wake phrase.

Playback pauses active receive streams so the bot does not transcribe its own race-radio output.

Driver requests take priority over queued alerts. When a speech segment is submitted to Python, the bridge clears pending local audio, pauses voice-job polling while the Python service handles the command or LLM request, then immediately polls for the answer. This prevents stale telemetry or other proactive alerts from speaking over a conversational response.

## Testing

Tests do not require Discord credentials or network access:

```bash
npm test
```
