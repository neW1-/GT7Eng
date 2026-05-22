import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

const TRUE_VALUES = new Set(["1", "true", "yes", "on"]);
const FALSE_VALUES = new Set(["0", "false", "no", "off"]);

export function parseBoolean(value, defaultValue = false) {
  if (value === undefined || value === null || value === "") return defaultValue;
  const normalized = String(value).trim().toLowerCase();
  if (TRUE_VALUES.has(normalized)) return true;
  if (FALSE_VALUES.has(normalized)) return false;
  throw new Error(`Invalid boolean value: ${value}`);
}

export function parseInteger(value, defaultValue, name) {
  if (value === undefined || value === null || value === "") return defaultValue;
  const parsed = Number.parseInt(String(value), 10);
  if (!Number.isFinite(parsed) || parsed < 0) {
    throw new Error(`${name} must be a non-negative integer`);
  }
  return parsed;
}

export function readConfig(env = process.env) {
  const source = env === process.env ? { ...readDotEnv(), ...env } : env;
  const mode = source.DEFAULT_AUDIO_MODE || "quiet_driver";
  if (!["wake_phrase", "quiet_driver", "silent"].includes(mode)) {
    throw new Error("DEFAULT_AUDIO_MODE must be one of: wake_phrase, quiet_driver, silent");
  }

  return {
    discord: {
      token: source.DISCORD_TOKEN || "",
      clientId: source.DISCORD_CLIENT_ID || "",
      guildId: source.DISCORD_GUILD_ID || "",
      voiceChannelId: source.DISCORD_VOICE_CHANNEL_ID || "",
      driverUserId: source.DISCORD_DRIVER_USER_ID || ""
    },
    python: {
      baseUrl: stripTrailingSlash(source.PYTHON_SERVICE_URL || "http://127.0.0.1:8000"),
      token: source.PYTHON_SERVICE_TOKEN || "",
      statusTimeoutMs: parseInteger(source.STATUS_POLL_TIMEOUT_MS, 3000, "STATUS_POLL_TIMEOUT_MS")
    },
    commands: {
      registerScope: source.COMMAND_REGISTER_SCOPE || "guild"
    },
    audio: {
      jobPollIntervalMs: parseInteger(source.JOB_POLL_INTERVAL_MS, 1000, "JOB_POLL_INTERVAL_MS"),
      defaultEngineerMuted: parseBoolean(source.DEFAULT_ENGINEER_MUTED, false),
      defaultMode: mode,
      autoJoinOnReady: parseBoolean(source.AUTO_JOIN_ON_READY, false),
      receiveWatchdogMs: parseInteger(source.RECEIVE_WATCHDOG_MS, 120000, "RECEIVE_WATCHDOG_MS")
    },
    stt: {
      enabled: parseBoolean(source.DISCORD_STT_ENABLED, false),
      minSegmentMs: parseInteger(source.DISCORD_STT_MIN_SEGMENT_MS, 450, "DISCORD_STT_MIN_SEGMENT_MS"),
      maxSegmentMs: parseInteger(source.DISCORD_STT_MAX_SEGMENT_MS, 6000, "DISCORD_STT_MAX_SEGMENT_MS"),
      sampleRate: parseInteger(source.DISCORD_STT_SAMPLE_RATE, 48000, "DISCORD_STT_SAMPLE_RATE"),
      channels: parseInteger(source.DISCORD_STT_CHANNELS, 2, "DISCORD_STT_CHANNELS")
    },
    logLevel: source.LOG_LEVEL || "info"
  };
}

export function assertRuntimeConfig(config) {
  const missing = [];
  if (!config.discord.token) missing.push("DISCORD_TOKEN");
  if (!config.discord.clientId) missing.push("DISCORD_CLIENT_ID");
  if (!config.discord.guildId && config.commands.registerScope === "guild") {
    missing.push("DISCORD_GUILD_ID");
  }
  if (missing.length > 0) {
    throw new Error(`Missing required environment variables: ${missing.join(", ")}`);
  }
}

function stripTrailingSlash(value) {
  return value.replace(/\/+$/, "");
}

function readDotEnv() {
  const file = path.join(process.cwd(), ".env");
  if (!existsSync(file)) return {};
  const values = {};
  for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) continue;
    const [, key, rawValue] = match;
    values[key] = rawValue.replace(/^['"]|['"]$/g, "");
  }
  return values;
}
